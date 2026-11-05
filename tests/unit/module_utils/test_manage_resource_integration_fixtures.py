# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Cisco Systems
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Render integration inputs and validate them without contacting a controller."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from ansible import template as ansible_template
from ansible.module_utils.common.arg_spec import ArgumentSpecValidator
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.conditional import Conditional
from ansible.plugins.filter.core import to_nice_yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2.meta import find_undeclared_variables

from ansible_collections.cisco.nd.plugins.module_utils.models.manage_networks.config_models import NetworkConfigModel, NetworkParentConfigModel
from ansible_collections.cisco.nd.plugins.module_utils.models.manage_vrfs.config_models import VrfConfigModel, VrfParentConfigModel
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.network_argument_specs import network_module_argument_spec
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.vrf_argument_specs import vrf_parent_argument_spec, vrf_standalone_argument_spec

TARGETS = Path(__file__).resolve().parents[2] / "integration/targets"
MODELS = {
    "nd_manage_networks": (NetworkConfigModel, NetworkParentConfigModel),
    "nd_manage_vrfs": (VrfConfigModel, VrfParentConfigModel),
}
TEST_CASES = sorted(path for name in MODELS for path in (TARGETS / name / "tests").glob("*/*.yaml"))


def _load_tasks(path):
    """Trust only the repository-owned YAML for newer Ansible template engines."""
    contents = path.read_text(encoding="utf-8")
    trust = getattr(ansible_template, "trust_as_template", None)
    return DataLoader().load(trust(contents) if trust else contents, file_name=str(path))


def _test_case_tasks(path, tasks=None):
    for task in _load_tasks(path) if tasks is None else tasks:
        if "block" in task:
            for section in ("block", "rescue", "always"):
                yield from _test_case_tasks(path, task.get(section, []))
            continue
        imported = task.get("ansible.builtin.import_tasks")
        if imported:
            assert (path.parent / imported).is_file(), imported
        if imported and not imported.endswith("conf_prep_tasks.yaml"):
            if Path(imported).name != "setup.yaml":
                yield from _test_case_tasks(path.parent / imported)
        else:
            included = task.get("ansible.builtin.include_tasks")
            if included and "{{" not in included:
                assert (path.parent / included).is_file(), included
            yield task


def _template_config(role, resource, config):
    environment = Environment(loader=FileSystemLoader(role / "templates"), undefined=StrictUndefined)
    environment.filters["to_nice_yaml"] = to_nice_yaml
    return yaml.safe_load(environment.get_template(f"nd_{resource}_conf.j2").render(**{f"{resource}_conf": config}))


def _validate_config(resource, config, *, parent=False, state="merged"):
    assert len({entry.get("deploy_type") or "switch" for entry in config}) <= 1, "Integration tasks must use a single deployment scope"
    name = "nd_manage_networks" if resource == "network" else "nd_manage_vrfs"
    options = network_module_argument_spec() if resource == "network" else (vrf_parent_argument_spec() if parent else vrf_standalone_argument_spec())
    result = ArgumentSpecValidator({"config": {"type": "list", "elements": "dict", "options": options}}).validate({"config": config})
    assert not result.error_messages, result.error_messages
    for entry in result.validated_parameters["config"]:
        if resource == "vrf":
            assert len(entry["vrf_name"]) <= 32, "VXLAN integration VRF names must fit the controller/switch limit"
        MODELS[name][parent].from_config(entry, context={"state": state, "defer_omitted_layer": state == "merged"})


def _fixture_variables(role):
    """Supply offline inventory data used only to render repository-owned test inputs."""
    variables = _load_tasks(role / "defaults/main.yaml")
    variables.update(
        ansible_it_fabric="standalone",
        ansible_switch1="192.0.2.10",
        ansible_switch2="192.0.2.11",
        ansible_network_interface1="Ethernet1/1",
        ansible_network_interface2="Ethernet1/2",
        ansible_msd_parent_fabric="group",
        ansible_msd_child_fabric="group-child",
        ansible_mcfg_parent_fabric="multi-cluster",
        ansible_mcfg_child_fabric="multi-cluster-child",
        ansible_mcfg_switch1="192.0.2.20",
        ansible_mcfg_switch2="192.0.2.21",
        ansible_nd_network_vrf_name="BLUE",
        role_path=str(role),
        nd_network_attachment_switches={"jsondata": {"switches": [{"switchId": "SW1", "fabricManagementIp": "192.0.2.10"}]}},
        nd_network_attachment_rows=[{"interfaces": []}],
        nd_network_attachment_vlan_readback={"jsondata": {"attachments": []}},
        nd_network_property_gather={"gathered": []},
        nd_vrf_property_gather={"gathered": []},
        nd_network_pvlan_members={"jsondata": {"fabrics": [{"name": "group-child", "type": "vxlanIbgp"}, {"name": "group-child-2", "type": "vxlanEbgp"}]}},
        nd_network_pvlan_switch_inventory={"jsondata": {"switches": [{"switchId": "SW1", "fabricManagementIp": "192.0.2.10"}]}},
        nd_network_pvlan_binding_query={"jsondata": {"attachments": []}},
        nd_network_pvlan_expect_ports=True,
    )
    return variables


def _prepare_config(role, resource, task, variables):
    """Follow the existing shared template preparation and retain its named output."""
    imported = task.get("ansible.builtin.import_tasks", "")
    if not imported.endswith("conf_prep_tasks.yaml"):
        return None
    prepared = ansible_template.Templar(loader=DataLoader(), variables=variables).template(task["vars"])
    config = prepared[f"{resource}_conf"]
    rendered = _template_config(role, resource, config)
    assert rendered == config, "The integration template must not drop or rewrite supplied intent"
    name = f"nd_{resource}_{prepared['file']}_conf"
    variables[name] = rendered
    return name


def _module_arguments(task, module_name, variables):
    """Render each real module-loop entry with the test's native input types."""
    arguments = task.get(module_name)
    if not arguments:
        return
    items = ansible_template.Templar(loader=DataLoader(), variables=variables).template(task["loop"]) if "loop" in task else [None]
    for item in items:
        context = dict(variables)
        if "loop" in task:
            context[task.get("loop_control", {}).get("loop_var", "item")] = item
        yield ansible_template.Templar(loader=DataLoader(), variables=context).template(arguments)


def _validate_property_cases(role, resource, task, variables):
    """Expand the shared per-property include with its actual supplied loop values."""
    cases = ansible_template.Templar(loader=DataLoader(), variables=variables).template(task["loop"])
    count = 0
    path = role / "tasks" / task["ansible.builtin.include_tasks"]
    for case in cases:
        variables[task["loop_control"]["loop_var"]] = case
        for nested in _test_case_tasks(path):
            facts = nested.get("ansible.builtin.set_fact")
            if facts:
                variables.update(ansible_template.Templar(loader=DataLoader(), variables=variables).template(facts))
            _prepare_config(role, resource, nested, variables)
            for arguments in _module_arguments(nested, f"cisco.nd.{role.name}", variables):
                parent = arguments["fabric_name"] in ("group", "multi-cluster")
                _validate_config(resource, arguments.get("config", []), parent=parent, state=arguments["state"])
                count += 1
    return count


@pytest.mark.parametrize("test_case", TEST_CASES, ids=lambda path: str(path.relative_to(TARGETS)))
def test_integration_inputs_match_current_models(test_case):
    """Check fact ordering, local imports, template fidelity and real model validation."""
    role = test_case.parents[2]
    resource = "network" if role.name == "nd_manage_networks" else "vrf"
    variables = _fixture_variables(role)
    validated = 0
    for task in _test_case_tasks(test_case):
        templar = ansible_template.Templar(loader=DataLoader(), variables=variables)
        facts = task.get("ansible.builtin.set_fact", {})
        if any(key.startswith(f"nd_{resource}_") for key in facts):
            variables.update(templar.template(facts))
        imported = task.get("ansible.builtin.import_tasks")
        if imported:
            _prepare_config(role, resource, task, variables)
        if task.get("ansible.builtin.include_tasks") == "properties_case_tasks.yaml":
            validated += _validate_property_cases(role, resource, task, variables)
        if not task.get("ignore_errors"):
            for arguments in _module_arguments(task, f"cisco.nd.{role.name}", variables):
                parent = arguments["fabric_name"] in ("group", "multi-cluster")
                _validate_config(resource, arguments.get("config", []), parent=parent, state=arguments["state"])
                validated += 1
    assert validated > 0


@pytest.mark.parametrize("resource", ["vrf", "network"])
def test_integration_templates_preserve_sparse_and_explicit_values(resource):
    """Do not filter newly added fields or replace omitted nested fields with defaults."""
    role = TARGETS / ("nd_manage_vrfs" if resource == "vrf" else "nd_manage_networks")
    feature = {"ipv6_trm": False, "v6_rp_external": False} if resource == "vrf" else {"trm_enable": False}
    options = {"import_vpn_rt": []} if resource == "vrf" else {"svi_enabled": False, "switch_route_target_import": []}
    config = [
        {
            f"{resource}_name": "sparse",
            "child_fabric_config": [{"fabric_name": "child", **feature}],
            "attach": [{"ip_address": "192.0.2.10", "freeform_config": "", "attachment_options": options}],
        }
    ]
    assert _template_config(role, resource, config) == config


@pytest.mark.parametrize(
    "relative_path,case_name",
    [("standalone/pvlan.yaml", None), ("msd/pvlan.yaml", None), ("standalone/merged.yaml", "Merged TC5 - Structured Attachment Options")],
)
def test_opt_in_network_cases_consume_jinja_prepared_config(relative_path, case_name):
    """Every feature-module call must consume the same template output as the other state tests."""
    role = TARGETS / "nd_manage_networks"
    path = role / "tests" / relative_path
    tasks = _load_tasks(path) if case_name is None else next(task["block"] for task in _load_tasks(path) if task["name"] == case_name)
    variables = _fixture_variables(role)
    prepared_names = set()
    validated = 0
    for task in _test_case_tasks(path, tasks):
        facts = task.get("ansible.builtin.set_fact", {})
        templar = ansible_template.Templar(loader=DataLoader(), variables=variables)
        if facts:
            variables.update(templar.template(facts))
        name = _prepare_config(role, "network", task, variables)
        if name:
            prepared_names.add(name)
        arguments = task.get("cisco.nd.nd_manage_networks")
        if arguments:
            used_names = find_undeclared_variables(Environment().parse(arguments["config"]))
            assert used_names and used_names <= prepared_names
            for arguments in _module_arguments(task, "cisco.nd.nd_manage_networks", variables):
                _validate_config("network", arguments["config"], parent=arguments["fabric_name"] == "group", state=arguments["state"])
                validated += 1
    assert len(prepared_names) == (5 if case_name is None else 3)
    assert validated >= 7
    if case_name == "Merged TC5 - Structured Attachment Options":
        attachment = variables["nd_network_standalone_merged_attachment_update_conf"][0]["attach"][0]
        assert "interfaces" not in attachment
        assert attachment["attachment_options"] == {"svi_enabled": False, "switch_route_target_import": [], "switch_route_target_export": []}
        assert attachment["freeform_config"] == ""


@pytest.mark.parametrize("topology", ["standalone", "msd"])
@pytest.mark.parametrize("enabled", [False, True])
def test_pvlan_runner_requires_explicit_opt_in(topology, enabled):
    """Selecting PVLAN must never bypass its independent feature opt-in."""
    role = TARGETS / "nd_manage_networks"
    runner = _load_tasks(role / "tasks/main.yaml")[-1]
    variables = _fixture_variables(role)
    variables.update(runner["vars"])
    variables.update(
        nd_network_test_case_to_run=str(role / "tests" / topology / "pvlan.yaml"),
        nd_network_run_pvlan=enabled,
    )
    variables["vars"] = dict(variables)
    condition = Conditional(loader=DataLoader())
    condition.when = runner["when"]
    assert condition.evaluate_conditional(ansible_template.Templar(loader=DataLoader(), variables=variables), variables) is enabled


@pytest.mark.parametrize("resource", ["vrf", "network"])
@pytest.mark.parametrize("topology", ["standalone", "msd", "mcfg"])
@pytest.mark.parametrize("state", ["merged", "staged"])
@pytest.mark.parametrize("enabled", [False, True])
def test_case_runner_evaluates_templated_topology_defaults(resource, topology, state, enabled):
    """Exercise deferred defaults, not only literal run flags, through the real lookup plugin."""
    role = TARGETS / ("nd_manage_vrfs" if resource == "vrf" else "nd_manage_networks")
    runner = _load_tasks(role / "tasks/main.yaml")[-1]
    variables = _fixture_variables(role)
    variables.update(runner["vars"])
    variables[f"nd_{resource}_test_case_to_run"] = str(role / "tests" / topology / f"{state}.yaml")
    if not enabled:
        field = "fabric" if topology == "standalone" else "parent_fabric"
        variables[f"nd_{resource}_{topology}_{field}"] = ""
    condition = Conditional(loader=DataLoader())
    condition.when = runner["when"]
    assert condition.evaluate_conditional(ansible_template.Templar(loader=DataLoader(), variables=variables), variables) is enabled


def _assertions_pass(task, variables):
    condition = Conditional(loader=DataLoader())
    condition.when = task["ansible.builtin.assert"]["that"]
    return condition.evaluate_conditional(ansible_template.Templar(loader=DataLoader(), variables=variables), variables)


@pytest.mark.parametrize("topology", ["standalone", "msd"])
@pytest.mark.parametrize("fabric_type", ["vxlanIbgp", "vxlanEbgp", "vxlanCampus"])
@pytest.mark.parametrize("private_vlan", [True, False, None, "true", "missing"])
def test_pvlan_prerequisites_require_enabled_dc_fabrics(topology, fabric_type, private_vlan):
    """A missing/false/non-boolean setting or Campus member must fail before lifecycle writes."""
    role = TARGETS / "nd_manage_networks"
    task_name = "PVLAN - Require Enabled Data Center VXLAN Fabric" if topology == "standalone" else "PVLAN - Require Private VLAN Enabled on Every Member"
    task = next(task for task in _test_case_tasks(role / "tests" / topology / "pvlan.yaml") if task["name"] == task_name)
    management = {"type": fabric_type}
    if private_vlan != "missing":
        management["privateVlan"] = private_vlan
    result = {"jsondata": {"management": management}}
    variables = {"nd_network_pvlan_fabric": result} if topology == "standalone" else {"item": result}
    assert _assertions_pass(task, variables) is (fabric_type != "vxlanCampus" and private_vlan is True)


@pytest.mark.parametrize("metadata_shape", ["flat", "counts"])
@pytest.mark.parametrize("case", ["valid", "empty", "duplicate", "campus", "external", "truncated", "wrong_child"])
def test_group_pvlan_requires_complete_eligible_membership(metadata_shape, case):
    """Validate every member, not merely the one child named in the inventory."""
    role = TARGETS / "nd_manage_networks"
    tasks = list(_test_case_tasks(role / "tests/msd/pvlan.yaml"))
    retain = next(task for task in tasks if task["name"] == "PVLAN - Retain Discovered Member Scope")
    require = next(task for task in tasks if task["name"] == "PVLAN - Require Complete Data Center VXLAN Membership")
    rows = [{"name": "group-child", "type": "vxlanIbgp"}, {"name": "group-child-2", "type": "vxlanEbgp"}]
    if case == "empty":
        rows = []
    elif case == "duplicate":
        rows[1]["name"] = rows[0]["name"]
    elif case in ("campus", "external"):
        rows[1]["type"] = "vxlanCampus" if case == "campus" else "externalConnectivity"
    elif case == "wrong_child":
        rows[0]["name"] = "other-child"
    counts = {"total": len(rows) + (case == "truncated"), "remaining": int(case == "truncated")}
    metadata = counts if metadata_shape == "flat" else {"counts": counts}
    variables = {"nd_network_pvlan_members": {"jsondata": {"fabrics": rows, "meta": metadata}}, "nd_network_msd_child_fabric": "group-child"}
    variables.update(ansible_template.Templar(loader=DataLoader(), variables=variables).template(retain["ansible.builtin.set_fact"]))
    assert _assertions_pass(require, variables) is (case == "valid")


@pytest.mark.parametrize("vlan_type", ["primary", "community", "isolated"])
@pytest.mark.parametrize("fabric", ["group", "group-child", "group-child-2"])
@pytest.mark.parametrize("valid", [False, True])
@pytest.mark.parametrize("template_vlan", [False, True])
def test_pvlan_readback_checks_each_scope_and_primary_association(vlan_type, fabric, valid, template_vlan):
    """The actual native readback assertions must detect incorrect roles or secondary bindings."""
    role = TARGETS / "nd_manage_networks"
    tasks = list(_test_case_tasks(role / "tasks/pvlan_tasks.yaml"))
    task = next(task for task in tasks if task["name"] == "PVLAN - Assert Parent and Member Types IDs VLANs and Associations")
    config = {"network_name": "test", "network_id": 901350, "vlan_id": 3450, "vlan_network_type": vlan_type, "primary_network_id": 901349}
    response = {"fabricName": fabric, "networkName": "test", "networkId": 901350, "vlanId": 3450, "primaryNetworkId": 901349}
    response["vlanNetworkType"] = {"primary": "privatePrimary", "community": "privateSecondaryCommunity", "isolated": "privateSecondaryIsolated"}[vlan_type]
    if template_vlan:
        response["networkTemplateConfig"] = {"vlanId": str(response.pop("vlanId"))}
    if not valid:
        if vlan_type == "primary":
            response["vlanNetworkType"] = "normal"
        else:
            response["primaryNetworkId"] = 901348
    assert _assertions_pass(task, {"item": {"item": [fabric, config], "jsondata": response}}) is valid


def test_vrf_release_specific_properties_are_separate_opt_in_cases():
    """Ordinary routing inputs must remain valid without ND 4.3-only capabilities."""
    role = TARGETS / "nd_manage_vrfs"
    cases = _load_tasks(role / "tasks/properties_tasks.yaml")[0]["ansible.builtin.set_fact"]["nd_vrf_property_cases"]
    by_name = {case["name"]: case for case in cases}
    assert "enable_vrf_vpn_route_leaking" not in by_name["routing"]["fabric"]
    assert by_name["vpn-leaking"]["requires"] == "nd43"
    assert by_name["rd-zero"]["requires"] == "iosxe43"


@pytest.mark.parametrize("enabled", [False, True])
def test_group_network_deploy_fixture_stages_real_attachments_when_available(enabled):
    """A deploy expectation must be backed by attachments, not just a deploy flag."""
    role = TARGETS / "nd_manage_networks"
    tasks = _load_tasks(role / "tests/msd/merged.yaml")
    variables = _fixture_variables(role)
    variables["nd_network_run_msd_attach"] = enabled
    build = next(task for task in tasks if task["name"] == "MSD Merged - Build Parent and Child Network Config")
    facts = ansible_template.Templar(loader=DataLoader(), variables=variables).template(build["ansible.builtin.set_fact"])
    for phase in ("stage", "deploy"):
        config = facts[f"nd_network_msd_merged_{phase}_config"]
        assert {entry["deploy_type"] for entry in config} == {"switch"}
        _validate_config("network", config, parent=True)
        for entry in config:
            assert len(entry["attach"]) == int(enabled)
            if enabled:
                assert entry["attach"][0]["vlan_id"] == int(entry["vlan_id"])
                assert entry["attach"][0]["deploy"] is (phase == "deploy")
    assertion = next(task for task in tasks if task["name"] == "MSD Merged TC2 - Assert Deploy Result")
    variables["msd_merged_deployed"] = {"changed": enabled, "child_fabrics": [{}]}
    assert _assertions_pass(assertion, variables)


def test_pvlan_cleanup_keeps_secondary_before_primary_order_and_scope():
    """Failure cleanup must not become a fabric-wide or unordered deletion."""
    role = TARGETS / "nd_manage_networks"
    lifecycle = next(task for task in _load_tasks(role / "tasks/pvlan_tasks.yaml") if "always" in task)
    removals = [task["cisco.nd.nd_manage_networks"] for task in lifecycle["always"] if task.get("cisco.nd.nd_manage_networks", {}).get("state") == "deleted"]
    assert [arguments["config"] for arguments in removals] == ["{{ nd_network_pvlan_secondary_conf }}", "{{ nd_network_pvlan_primary_conf }}"]
    assert all(arguments["fabric_name"] == "{{ target_fabric }}" for arguments in removals)


def _pvlan_attachment_variables(topology, with_ports=True):
    role = TARGETS / "nd_manage_networks"
    variables = _fixture_variables(role)
    if with_ports:
        for field, modes, first in (
            ("primary", ("promiscuous", "trunk_promiscuous"), 58),
            ("community", ("pvlan_host",), 60),
            ("isolated", ("pvlan_host", "trunk_secondary"), 62),
        ):
            variables[f"nd_network_pvlan_{field}_interfaces"] = [
                {"mode": mode, "interface_range": f"Ethernet1/{first + offset}"} for offset, mode in enumerate(modes)
            ]
    for task in _test_case_tasks(role / "tests" / topology / "pvlan.yaml"):
        if task["name"] == "PVLAN Attachments - Preview Attachment Creation":
            return variables
        facts = task.get("ansible.builtin.set_fact")
        if facts:
            variables.update(ansible_template.Templar(loader=DataLoader(), variables=variables).template(facts))
        _prepare_config(role, "network", task, variables)
    raise AssertionError("PVLAN attachment lifecycle was not imported")


@pytest.mark.parametrize("topology", ["standalone", "msd"])
@pytest.mark.parametrize("with_ports", [False, True])
def test_pvlan_attachment_intent_preserves_roles_ports_and_sparse_omission(topology, with_ports):
    """Both topologies use real Jinja/model validation without enabling deployment."""
    variables = _pvlan_attachment_variables(topology, with_ports)
    full = variables["nd_network_pvlan_attachment_conf"]
    sparse = variables["nd_network_pvlan_attachment_sparse_conf"]
    assert [entry["vlan_network_type"] for entry in full] == ["primary", "community", "isolated"]
    assert sum(len(entry["attach"][0]["interfaces"]) for entry in full) == (5 if with_ports else 0)
    for config in (full, sparse):
        _validate_config("network", config, parent=topology == "msd")
        assert all(entry["deploy"] is False and entry["attach"][0]["deploy"] is False for entry in config)
        assert all(entry["attach"][0]["ip_address"] == "192.0.2.10" for entry in config)
    assert all(set(entry) == {"network_name", "deploy", "attach"} for entry in sparse)
    assert all(set(entry["attach"][0]) == {"ip_address", "deploy"} for entry in sparse)


@pytest.mark.parametrize("topology", ["standalone", "msd"])
def test_pvlan_attachment_fixture_rejects_community_trunk(topology):
    """Reject a community-trunk boundary input instead of treating it as a positive case."""
    variables = _pvlan_attachment_variables(topology)
    config = deepcopy(variables["nd_network_pvlan_attachment_conf"])
    config[1]["attach"][0]["interfaces"] = [{"mode": "trunk_secondary", "interface_range": "Ethernet1/61"}]
    with pytest.raises(ValueError, match="mode=trunk_secondary is not valid for vlan_network_type=privateSecondaryCommunity"):
        _validate_config("network", config, parent=topology == "msd")


@pytest.mark.parametrize("enabled", [False, True])
def test_pvlan_attachment_lifecycle_is_separately_opted_in(enabled):
    lifecycle = next(task for task in _load_tasks(TARGETS / "nd_manage_networks/tasks/pvlan_tasks.yaml") if "always" in task)
    task = next(task for task in lifecycle["block"] if task.get("ansible.builtin.import_tasks") == "pvlan_attachment_tasks.yaml")
    variables = {"nd_network_run_pvlan_attach": enabled}
    condition = Conditional(loader=DataLoader())
    condition.when = [task["when"]]
    assert condition.evaluate_conditional(ansible_template.Templar(loader=DataLoader(), variables=variables), variables) is enabled
    names = [entry["name"] for entry in lifecycle["block"]]
    assert names.index(task["name"]) < names.index("PVLAN - Read Controller Definitions in the Owning Fabric and Every Member")


@pytest.mark.parametrize("succeeded", [False, True])
def test_pvlan_port_repeats_and_readback_require_the_actual_port_write(succeeded):
    """Failed port writes must not trigger dependent assertions in a continuous run."""
    tasks = _load_tasks(TARGETS / "nd_manage_networks/tasks/pvlan_attachment_tasks.yaml")
    names = {
        "PVLAN Attachments - Read Native Bindings Before Repeats",
        "PVLAN Attachments - Repeat Full Intent in Merged and Replaced Normal and Check Mode",
        "PVLAN Attachments - Verify Bindings Survive All Repeats",
    }
    variables = {"nd_network_pvlan_port_attachment": {"failed": not succeeded}}
    for task in tasks:
        if task["name"] not in names:
            continue
        condition = Conditional(loader=DataLoader())
        condition.when = [task["when"]]
        assert condition.evaluate_conditional(ansible_template.Templar(loader=DataLoader(), variables=variables), variables) is succeeded


@pytest.mark.parametrize("topology", ["standalone", "msd"])
@pytest.mark.parametrize("expect_ports", [False, True])
@pytest.mark.parametrize("wire_style", ["public", "camel", "legacy_host"])
@pytest.mark.parametrize("invalid", [None, "switch", "fabric", "missing", "vlan", "count", "port", "mode", "native"])
def test_pvlan_native_attachment_assertions_validate_saved_bindings(topology, expect_ports, wire_style, invalid):
    """Readback checks must catch incorrect persistence, not merely successful writes."""
    variables = _pvlan_attachment_variables(topology)
    variables["nd_network_pvlan_expect_ports"] = expect_ports
    bindings = []
    for entry in variables["nd_network_pvlan_attachment_conf"]:
        ports = []
        for port in entry["attach"][0]["interfaces"] if expect_ports else []:
            mode = port["mode"]
            if wire_style != "public":
                mode = {"trunk_promiscuous": "trunkPromiscuous", "trunk_secondary": "trunkSecondary", "pvlan_host": "pvlanHost"}.get(mode, mode)
            if wire_style == "legacy_host" and mode == "pvlanHost":
                mode = "host"
            ports.append({"interfaceRange": port["interface_range"], "mode": mode, "nativeVlan": False})
        bindings.append(
            {
                "attach": True,
                "networkName": entry["network_name"],
                "switchId": "SW1",
                "switchFabricName": variables["nd_network_pvlan_switch_fabric"],
                "vlanId": entry["vlan_id"],
                "interfaces": ports,
            }
        )
    if invalid == "switch":
        bindings[0]["switchId"] = "OTHER"
    elif invalid == "fabric":
        bindings[0]["switchFabricName"] = "other-member"
    elif invalid == "missing":
        bindings.pop()
    elif invalid == "vlan":
        bindings[0]["vlanId"] = int(bindings[0]["vlanId"]) + 1
    elif invalid == "count":
        bindings[0]["interfaces"].append({"interfaceRange": "Ethernet1/1", "mode": "trunk"})
    elif expect_ports and invalid in ("port", "mode", "native"):
        key, value = {"port": ("interfaceRange", "Ethernet1/1"), "mode": ("mode", "trunk"), "native": ("nativeVlan", True)}[invalid]
        bindings[0]["interfaces"][0][key] = value
    variables["nd_network_pvlan_binding_query"] = {"jsondata": {"attachments": deepcopy(bindings)}}
    passed = True
    for task in _load_tasks(TARGETS / "nd_manage_networks/tasks/pvlan_attachment_readback_tasks.yaml"):
        facts = task.get("ansible.builtin.set_fact")
        if facts:
            variables.update(ansible_template.Templar(loader=DataLoader(), variables=variables).template(facts))
        if "ansible.builtin.assert" not in task:
            continue
        items = ansible_template.Templar(loader=DataLoader(), variables=variables).template(task["loop"]) if "loop" in task else [None]
        for item in items:
            context = {**variables, "item": item}
            context.update(task.get("vars", {}))
            if not _assertions_pass(task, context):
                passed = False
                break
        if not passed:
            break
    assert passed is (invalid is None or (not expect_ports and invalid in ("port", "mode", "native")))


def test_group_network_deploy_waits_before_idempotence_checks():
    """Asynchronous deploy completion, not initial acceptance, precedes unchanged repeats."""
    tasks = _load_tasks(TARGETS / "nd_manage_networks/tests/msd/merged.yaml")
    query = next(task for task in tasks if task["name"] == "MSD Merged TC2 - Read Deployed Attachments")
    assert query["cisco.nd.nd_rest"]["path"].endswith("/networkAttachments/query?includeAll=true&max=10000&offset=0")
    assert query["until"] and query["retries"] == 30 and query["delay"] == 5
    for name in ("MSD Merged TC4 - Idempotence", "MSD Merged TC4 - Check Repeat Idempotence"):
        repeat = next(task for task in tasks if task["name"] == name)
        assert "not (nd_network_run_msd_attach | bool) or msd_merged_attachment_readback is succeeded" in repeat["when"]


@pytest.mark.parametrize("resource", ["network", "vrf"])
@pytest.mark.parametrize("topology", ["standalone", "msd"])
@pytest.mark.parametrize("invalid", [None, "deployed", "notApplicable"])
def test_staged_readback_uses_gathered_and_accepts_unattached_not_applicable_rows(resource, topology, invalid):
    """Unattached includeAll rows must not be mistaken for deployed staged intent."""
    role = TARGETS / ("nd_manage_networks" if resource == "network" else "nd_manage_vrfs")
    tasks = _load_tasks(role / "tests" / topology / "staged.yaml")
    task = next(task for task in tasks if "Assert Omitted" in task.get("name", ""))
    name_prefix = ("ndnet" if resource == "network" else "ndvrf") + ("msd" if topology == "msd" else "") + "stg"
    names = [name_prefix + suffix for suffix in ("create", "add", "remove", "detach", "omit")]
    rows = []
    for suffix, attached in (("create", True), ("add", True), ("add", True), ("remove", True), ("detach", False), ("omit", False)):
        rows.append({resource + "Name": name_prefix + suffix, "attach": attached, "status": "pending"})
    rows.append({resource + "Name": names[0], "attach": False, "status": "notApplicable"})
    if invalid:
        rows[0]["status"] = invalid
    prefix = "msd_" if topology == "msd" else ""
    gathered_key = "msd_staged_gathered" if topology == "msd" else "staged_gather_result"
    count_key = f"nd_{resource}_" + ("msd_" if topology == "msd" else "") + "staged_both_attach_count"
    variables = {
        gathered_key: {"gathered": [{resource + "_name": names[-1]}], "after": []},
        prefix + "staged_attachment_rows": rows,
        prefix + "staged_repeat_result": {"changed": False},
        f"target_{resource}_names": names,
        count_key: 2,
    }
    assert _assertions_pass(task, variables) is (invalid is None)


@pytest.mark.parametrize("resource", ["network", "vrf"])
@pytest.mark.parametrize("topology", ["standalone", "msd"])
def test_staged_attachment_queries_use_the_rest_output_contract(resource, topology):
    """Normalize the actual nd_rest jsondata envelope, not obsolete current output."""
    role = TARGETS / ("nd_manage_networks" if resource == "network" else "nd_manage_vrfs")
    tasks = _load_tasks(role / "tests" / topology / "staged.yaml")
    normalizers = [task for task in tasks if "Normalize" in task.get("name", "")]
    assert len(normalizers) == 2
    for task in normalizers:
        facts = task["ansible.builtin.set_fact"]
        query = ("msd_" if topology == "msd" else "") + ("staged_create_attachment_query" if "Created" in task["name"] else "staged_attachment_query")
        expected = [{resource + "Name": "fixture", "attach": True, "status": "pending"}]
        variables = {query: {"jsondata": {"attachments": expected}}}
        rendered = ansible_template.Templar(loader=DataLoader(), variables=variables).template(facts)
        assert list(rendered.values()) == [expected]


@pytest.mark.parametrize("resource", ["network", "vrf"])
def test_setup_deletes_only_named_fixtures(resource):
    """No setup may erase an inventory or force a Manage-only fabric lookup."""
    role = TARGETS / ("nd_manage_networks" if resource == "network" else "nd_manage_vrfs")
    tasks = _load_tasks(role / "tasks/setup.yaml")
    names = ["fixture-a", "fixture-b"]
    variables = {
        "target_fabric": "group",
        "target_vrf_names": names,
        "target_network_delete_config": [{"network_name": name} for name in names],
    }
    assert len(tasks) == 1
    arguments = ansible_template.Templar(loader=DataLoader(), variables=variables).template(tasks[0][f"cisco.nd.{role.name}"])
    assert arguments["state"] == "deleted"
    assert [entry[f"{resource}_name"] for entry in arguments["config"]] == names
    assert tasks[0].get("failed_when") is not False


@pytest.mark.parametrize("resource", ["vrf", "network"])
@pytest.mark.parametrize("topology", ["standalone", "msd", "mcfg"])
@pytest.mark.parametrize("state", ["merged", "overridden", "staged"])
@pytest.mark.parametrize("enabled", [False, True])
def test_case_runner_respects_topology_and_destructive_opt_in(resource, topology, state, enabled):
    """Disabled topology/state selection must skip the entire case, including cleanup."""
    role = TARGETS / ("nd_manage_vrfs" if resource == "vrf" else "nd_manage_networks")
    runner = _load_tasks(role / "tasks/main.yaml")[-1]
    variables = _load_tasks(role / "defaults/main.yaml")
    variables.update(runner["vars"])
    variables.update(
        {
            f"nd_{resource}_test_case_to_run": str(role / "tests" / topology / f"{state}.yaml"),
            f"nd_{resource}_run_{topology}": enabled,
            f"nd_{resource}_{topology}_switch": "192.0.2.10",
            f"nd_{resource}_run_attach" if topology == "standalone" else f"nd_{resource}_run_{topology}_attach": True,
        }
    )
    variables["vars"] = dict(variables)
    condition = Conditional(loader=DataLoader())
    condition.when = runner["when"]
    assert condition.evaluate_conditional(ansible_template.Templar(loader=DataLoader(), variables=variables), variables) == (enabled and state != "overridden")


@pytest.mark.parametrize("resource", ["vrf", "network"])
def test_case_runner_always_cleans_only_the_current_scope(resource):
    """Failures must still clean the current case without inheriting a previous scope."""
    role = TARGETS / ("nd_manage_vrfs" if resource == "vrf" else "nd_manage_networks")
    tasks = _load_tasks(role / "tasks/run_case.yaml")
    scope = "target_vrf_names" if resource == "vrf" else "target_network_delete_config"
    assert tasks[0]["ansible.builtin.set_fact"] == {"target_fabric": "", scope: []}
    assert tasks[1]["always"][0]["ansible.builtin.include_tasks"] == "setup.yaml"
