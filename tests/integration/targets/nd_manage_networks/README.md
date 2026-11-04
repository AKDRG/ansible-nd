# Network Integration Tests

## PVLAN

PVLAN has separate opt-in tests because it requires private VLAN to be enabled
in fabric settings. It does not run as part of `testcase: merged`.

For standalone Data Center VXLAN fabrics, use `tests/standalone/pvlan.yaml`:

```yaml
testcase: pvlan
nd_network_test_topology: standalone
nd_network_run_pvlan: true
nd_network_standalone_fabric: test-dc-vxlan
nd_network_base_id: 40000
nd_network_base_vlan: 2300
```

For Fabric groups, use `tests/msd/pvlan.yaml`:

```yaml
testcase: pvlan
nd_network_test_topology: msd
nd_network_run_pvlan: true
nd_network_msd_parent_fabric: test-fabric-group
nd_network_msd_child_fabric: test-dc-member
nd_network_base_id: 40000
nd_network_base_vlan: 2300
```

Reserve available IDs/VLANs at base offsets 150-152 for standalone and 350-352
for the Fabric group. The group test discovers and checks every member, not only
the configured child. All members must be Data Center VXLAN fabrics with private
VLAN already enabled. Campus members are rejected. Enable PVLAN on the group
before testing; the parent Manage response may omit that setting. Neither test
changes fabric settings. Multi-cluster Fabric-group PVLAN remains unsupported.

Both entry files use `tasks/pvlan_tasks.yaml` for the same lifecycle: create the
primary before community/isolated secondaries, repeat identical definitions in
merged/replaced normal and check mode, and read native controller definitions.
The Fabric-group test verifies IDs, VLANs, types and primary associations on the
parent and every member. PVLAN definition properties are written on the parent,
not as child overrides. These cases create unattached Layer-2 definitions with
`deploy: false`; they do not test attachment, deployment, Layer-3 primary or traffic.

Existing fixture names in any scope cause failure before the lifecycle block.
Cleanup removes only the test secondaries, then the primary, including after a
failed assertion, and verifies removal from every scope. It never deletes all
Networks or uses overridden to clear a fabric.

## Attachment Options

Structured attachment tests remain in `tests/standalone/merged.yaml` and are
disabled by default. The ordinary merged tests also run.

```yaml
testcase: merged
nd_network_test_topology: standalone
nd_network_run_attachment_options: true
nd_network_standalone_fabric: test-dc-vxlan
nd_network_standalone_switch: 192.0.2.10
nd_network_l3_vrf_name: EXISTING_TEST_VRF
nd_network_base_id: 40000
nd_network_base_vlan: 2300
nd_network_attachment_options_gateway: 10.91.153.1/24
nd_network_attachment_options_interfaces: []
```

Reserve base offset 153 and an existing test VRF/switch. The test checks SVI state,
switch route targets and freeform text through the native attachment query, then
applies false/empty values while omitting interfaces. Normal/check repeats must
be unchanged and existing port bindings must be preserved. To test nonempty
bindings, provide dedicated unused ports:

```yaml
nd_network_attachment_options_interfaces:
  - mode: trunk
    interface_range: Ethernet1/1
```

Creation and updates use `deploy: false`; removing an attached fixture can still
deploy its scoped removal. Do not use ports carrying unrelated traffic.

For Fabric groups, select `testcase: attachment_options` with
`nd_network_test_topology: msd`, enable `nd_network_run_attachment_options`, and
provide the parent, child, switch, interface and existing VRF variables. This
checks true/false SVI state, nonempty/empty route targets and freeform text,
omitted-interface preservation, native binding readback and repeat idempotence.
Reserve offset 353. Ordinary standalone merged attachments use the configured
`nd_network_standalone_interface_mode` (default `trunk`); it must match the
existing port configuration.

## Property Coverage

Select `testcase: properties` and enable `nd_network_run_properties` to exercise
the shared standalone or Fabric-group property cases through the same Jinja
preparation. Set `nd_network_property_features` to applicable, preconfigured
features: `general`, `trm`, `netflow`, `security`, and `interfaces`. These tests
never enable fabric features themselves. Disabled feature cases are skipped,
not counted as verified.

General cases cover explicit normal/cross-connect and Layer-3 IPv4/IPv6,
secondary gateways, descriptions, MTU, ARP suppression, DHCP, loopback, routing
tag, multicast and border-gateway settings. Additional cases exercise TRM/IGMP,
NetFlow monitors, Layer 2 with VRF, native VLAN and single customer-VLAN mapping.
The interface cases require dedicated unused trunk ports on the selected switch.
Set `nd_network_property_mapped_interface` and `nd_network_property_native_interface`
(defaulting to inventory `ansible_network_interface1` and `ansible_network_interface2`).
The mapped port must belong to `nd_network_property_interface_group`, default
`ND_IT_PORT_GROUP`. NetFlow cases require existing `ND_IT_L2_MONITOR` and
`ND_IT_MONITOR` monitors; the VRF NetFlow case uses `ND_IT_MONITOR`. Reserve
offsets 400-407 and an existing test VRF. Use `nd_network_property_case_names` to
select specific named cases. The mapping-only case uses
`nd_network_property_mapping_interface`, defaulting to inventory interface 3 or
interface 2; keep it outside the test interface group to isolate customer-VLAN
mapping from the combined interface-group case. Each case checks supplied fields on
the effective standalone/member readback and normal/check repeats. Parent-owned
fields remain at parent scope; child-owned fields use `child_fabric_config`.

DPU settings require smart-switch fixtures; `is_active` requires a classic or
routed fabric. They are not positively tested by this Data Center VXLAN suite.
Supplying a property in a fixture does not establish every transition, enum,
hardware behavior, or release. Keep those limitations separate from live results.

## Configuration Preparation

All feature inputs use the existing `conf_prep_tasks.yaml` and
`nd_network_conf.j2` pipeline. Module calls, repeats and cleanup consume prepared
configuration variables. Only genuinely reused checks live in task helpers.
These definitions and offline rendering checks are not live verification on any
release or topology.
