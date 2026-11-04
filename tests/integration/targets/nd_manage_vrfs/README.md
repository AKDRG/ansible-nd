# VRF Integration Tests

The existing state-specific tests cover standalone fabrics, Fabric groups
and Multi-cluster Fabric groups. Configure only the topologies present in the
test inventory; unset fabric names disable that topology. For example:

```yaml
nd_vrf_test_topology: standalone
testcase: merged
nd_vrf_standalone_fabric: test-dc-vxlan
nd_vrf_standalone_switch: 192.0.2.10
nd_vrf_standalone_switch2: 192.0.2.11
nd_vrf_base_id: 55000
nd_vrf_base_vlan: 2000
```

Choose available IDs and VLANs within the test fabric's configured ranges.
Reserve the `ansible-*` and `ndvrf*` fixture names used in the selected files.
Setup and final cleanup delete only that case's named fixtures, including after
an assertion fails. Cleanup failures are not suppressed. The module resolves
the appropriate Manage or OneManage endpoint; setup does not assume a Manage
fabric lookup works for every topology.

`overridden` is disabled by default, including inside the sanity tests.
Enable `nd_vrf_run_overridden: true` only on a dedicated test fabric: the state
removes omitted VRFs, not just test fixtures. Staged attachment tests require
a test switch; ordinary merged tests may also deploy attachment changes.
Deleting attached fixtures can deploy their scoped removal even when creation
used `deploy: false`.

Parent definitions contain shared fields only. Child TRM, advertising, BGP and
no-VLAN overrides belong under `child_fabric_config`. BGP key types use the public
strings `3des`, `type6` and `type7`; passwords are hexadecimal. No-VLAN fixtures
omit inapplicable SVI fields. The configuration template preserves the supplied
structure rather than filtering fields through a separate allow-list.

Offline fixture rendering and syntax checks do not establish live idempotence.
Controller readback, unchanged repeats and cleanup must still be verified on
each available release and topology. Positive TRM/NetFlow cases need suitable
fabric prerequisites; release-specific features need compatible targets.

## Property Coverage

Select `testcase: properties` with `nd_vrf_run_properties: true` for the shared
standalone or Fabric-group property cases. Set `nd_vrf_property_features` to
features already available in the lab: `general`, `trm`, `netflow`, `security`,
`nd43`, `iosxe43`, `iosxe_trm`, or `bgw_trm`. The fixtures do not enable fabric features.
Choose only capabilities supported by the receiving switches and ND release;
skipped capabilities are not live verification.

Cases cover routing/SVI fields, custom redistribution map values, BGP controls
and all three password key types, IPv4/IPv6 internal/external RP and SSM modes,
MVPN targets, NetFlow, enforced security actions/tags, RD zero and border TRM.
Inputs pass through the existing Jinja preparation and are checked using
effective standalone/member readback and normal/check repeats. Reserve base
offsets 100-117. The `nd43` leaking and `iosxe43` RD cases require ND 4.3.1 or
later; do not enable them on ND 4.2 or an unknown release. These explicit cases
keep release-specific fields out of ordinary routing fixtures. Use
`nd_vrf_property_case_names` to select individual named
cases for a focused repeat. BGP passwords are not compared as clear text in registered
results; unchanged repeats still exercise password/key-type reconciliation.

Merged attachment checks query native controller bindings and assert supplied
loopback addresses, route targets and freeform text instead of relying on the
definition-only validation helper. Ordinary gathered output is inventory-wide;
property checks select the exact fixture name before comparing fields.

DPU and user-defined-template options require separate smart-switch/custom
fabric fixtures and are not positively tested by this Data Center VXLAN suite.
Definition readback does not demonstrate route leaking, VRF-Lite authentication,
multicast forwarding or other operational behavior on an unattached VRF.
