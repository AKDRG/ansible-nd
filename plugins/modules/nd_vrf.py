#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Cisco and/or its affiliates.
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: nd_vrf
version_added: "1.0.0"
short_description: Manages VRFs on Cisco Nexus Dashboard.
description:
  - Manages network VRFs on Cisco Nexus Dashboard across standalone,
    Multisite (MSD), and Multicluster (MFD) fabric topologies.
  - Automatically detects fabric type from the ND API and routes to the
    appropriate workflow without requiring extra user input.
  - For parent fabrics (MSD / MFD), supports recursive child-fabric
    coordination via the C(child_fabric_config) parameter inside each
    VRF definition.
  - Child fabrics only permit C(state=query) when targeted directly;
    all write operations must be driven through the parent fabric.
author:
  - Cisco ND Team
options:
  fabric:
    description:
      - Name of the fabric to operate on.
      - The module auto-detects whether this is a standalone, parent,
        or child fabric and routes accordingly.
    type: str
    required: true
  state:
    description:
      - Desired state of the VRF resources.
      - V(merged) creates or updates VRFs that do not match the desired config.
      - V(replaced) replaces existing VRFs that match the desired config.
      - V(overridden) replaces all VRFs; removes any not in config.
      - V(deleted) removes specified VRFs (or all if config is empty).
      - V(query) returns current VRF state (the only state allowed on child
        fabrics when targeted directly).
    type: str
    choices: [ merged, replaced, overridden, deleted, query ]
    default: merged
  config:
    description:
      - List of VRF configurations to manage.
      - For parent fabrics each item may include a C(child_fabric_config)
        list that drives the recursive child-fabric invocation.
    type: list
    elements: dict
    required: true
  fabric_details:
    description:
      - Internal parameter injected by VrfWorkflowCoordinator when invoking
        child-fabric tasks recursively.
      - Not intended for direct use in playbooks.
    type: dict
extends_documentation_fragment:
  - cisco.nd.modules
  - cisco.nd.check_mode
"""

EXAMPLES = r"""
# ── Standalone fabric ────────────────────────────────────────────────────────
- name: Create VRF on standalone fabric
  cisco.nd.nd_vrf:
    fabric: fab1
    state: merged
    config:
      - vrf_name: VRF_BLUE
        vrf_template: Default_VRF_Universal
        vrf_id: 50010
        vlan_id: 2001
        attach:
          - ip_address: 192.168.1.1
            deploy: true

# ── Multisite / Multicluster parent fabric ───────────────────────────────────
- name: Create VRF on MSD parent and coordinate child fabrics
  cisco.nd.nd_vrf:
    fabric: msd_parent_fabric
    state: merged
    config:
      - vrf_name: VRF_BLUE
        vrf_template: Default_VRF_Universal
        vrf_id: 50010
        vlan_id: 2001
        attach:
          - ip_address: 192.168.1.1
            deploy: true
        child_fabric_config:
          - fabric: child_fabric_1
            attach:
              - ip_address: 10.0.0.1
                deploy: false
          - fabric: child_fabric_2
            attach:
              - ip_address: 10.0.0.2
                deploy: false

# ── Child fabric — query only ────────────────────────────────────────────────
- name: Query VRFs on a child fabric (write ops must go through parent)
  cisco.nd.nd_vrf:
    fabric: child_fabric_1
    state: query
    config: []

# ── Delete VRFs (parent fabric) ──────────────────────────────────────────────
- name: Delete a VRF from parent fabric (children follow automatically)
  cisco.nd.nd_vrf:
    fabric: msd_parent_fabric
    state: deleted
    config:
      - vrf_name: VRF_BLUE
"""

RETURN = r"""
changed:
  description: Whether any change was made.
  type: bool
  returned: always
failed:
  description: Whether the operation failed.
  type: bool
  returned: always
fabric_type:
  description: >
    Detected fabric type.
    One of: standalone, multisite_parent, multicluster_parent,
    multisite_child, multicluster_child.
  type: str
  returned: always
workflow:
  description: Description of the workflow path that was executed.
  type: str
  returned: always
parent_fabric:
  description: Parent fabric operation results (parent workflows only).
  type: dict
  returned: when fabric is a parent and child_fabric_config is present
child_fabrics:
  description: Per-child-fabric operation results.
  type: list
  returned: when fabric is a parent and child_fabric_config is present
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.cisco.nd.plugins.module_utils.nd import nd_argument_spec, NDModule
from ansible_collections.cisco.nd.plugins.module_utils.common.exceptions import NDStateMachineError
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.vrf_argument_specs import (
    vrf_base_argument_spec,
    vrf_parent_argument_spec,
)
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.vrf_fabric_resolver import (
    VrfFabricResolver,
)
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.vrf_workflow_coordinator import (
    VrfWorkflowCoordinator,
)


# ---------------------------------------------------------------------------
# Argument-spec helpers
# ---------------------------------------------------------------------------

def vrf_base_argument_spec():
    """Re-exported for backward compatibility. Defined in vrf_argument_specs."""
    from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.vrf_argument_specs import (
        vrf_base_argument_spec as _impl,
    )
    return _impl()


def _child_fabric_config_element_spec():
    from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.vrf_argument_specs import (
        _child_fabric_config_element_spec as _impl,
    )
    return _impl()


def vrf_parent_argument_spec():
    """Re-exported for backward compatibility. Defined in vrf_argument_specs."""
    from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.vrf_argument_specs import (
        vrf_parent_argument_spec as _impl,
    )
    return _impl()


# ---------------------------------------------------------------------------
# Strategy fast-path for injected fabric_details
# ---------------------------------------------------------------------------

def _strategy_from_fabric_details(fabric_name: str, fabric_details: dict):
    """
    Build a strategy directly from an injected fabric_details dict.

    Delegates to VrfFabricResolver.strategy_from_fabric_details so the
    mapping lives in exactly one place.
    """
    return VrfFabricResolver.strategy_from_fabric_details(fabric_name, fabric_details)


# ---------------------------------------------------------------------------
# Module entry point
# ---------------------------------------------------------------------------

def main():
    argument_spec = nd_argument_spec()
    argument_spec.update(
        fabric=dict(type="str", required=True),
        state=dict(
            type="str",
            default="merged",
            choices=["merged", "replaced", "overridden", "deleted", "query"],
        ),
        config=dict(type="list", elements="dict", required=True),
        # fabric_details is injected internally by VrfWorkflowCoordinator for
        # child-fabric re-invocations. It is not intended for direct playbook use.
        fabric_details=dict(type="dict"),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    try:
        fabric_name: str = module.params["fabric"]
        fabric_details = module.params.get("fabric_details")

        if fabric_details:
            # ── Fast path: coordinator-injected child task ─────────────────
            # fabric_details was set by VrfWorkflowCoordinator — skip the
            # resolver API round-trip and build the strategy directly.
            strategy = _strategy_from_fabric_details(fabric_name, fabric_details)
        else:
            # ── Normal path: resolve strategy from ND API ──────────────────
            nd_module = NDModule(module)
            resolver = VrfFabricResolver(
                nd_module=nd_module,
                fabric_name=fabric_name,
            )
            strategy = resolver.resolve()

        # Run the workflow coordinator for the resolved strategy
        coordinator = VrfWorkflowCoordinator(
            module=module,
            strategy=strategy,
        )
        result = coordinator.run()

        module.exit_json(**result)

    except NDStateMachineError as e:
        module.fail_json(msg=str(e))
    except NotImplementedError as e:
        module.fail_json(msg=f"Feature not yet implemented: {str(e)}")
    except Exception as e:
        module.fail_json(msg=f"Unexpected error: {str(e)}")


if __name__ == "__main__":
    main()
