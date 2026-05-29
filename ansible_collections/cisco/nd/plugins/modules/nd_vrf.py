#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: nd_vrf
version_added: "1.0.0"
short_description: Manages VRF definitions on Cisco Nexus Dashboard.
description:
  - Manages VRF definitions on Cisco Nexus Dashboard across standalone,
    Multisite (MSD), and Multicluster (MFD) fabric topologies.
  - This module manages *VRF definitions only* (identity, custom templates,
    VLAN/SVI, TRM, routing, netflow, route targets). VRF attachment and
    deployment to switches is handled by a separate module.
  - Automatically detects fabric type from the ND API and routes to the
    appropriate workflow without requiring extra user input.
  - For parent fabrics (MSD / MFD), supports child-fabric coordination
    via the C(child_fabric_config) parameter inside each VRF definition.
  - Child fabrics only permit C(state=query) when targeted directly;
    all write operations must be driven through the parent fabric.
author:
  - Akshayanat C S (@achengam)
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
      - List of VRF definition configurations to manage.
      - Each element defines a VRF with identity, template, VLAN/SVI,
        routing, TRM, and other settings.
      - For parent fabrics each item may include a C(child_fabric_config)
        list to provide per-child-fabric overrides (TRM, BGP auth,
        netflow, and MVPN route targets).
    type: list
    elements: dict
    required: true
    suboptions:
      vrf_name:
        description: Name of the VRF (max 94 characters).
        type: str
        required: true
      vrf_id:
        description: L3 VNI (VRF segment ID), 1-16777214.
        type: int
      vrf_type:
        description:
          - VRF schema type.
          - Leave unset to derive the value from the fabric C(management.type).
          - Set to V(userDefined) to use custom VRF template fields.
        type: str
        choices:
          - userDefined
          - vxlan
          - vxlanIbgp
          - vxlanEbgp
          - vxlanCampus
          - aimlVxlanIbgp
          - aimlVxlanEbgp
          - classicLanEnhanced
          - vxlanAci
          - aci
          - externalConnectivity
          - vxlanExternal
      vrf_template_name:
        description:
          - Custom VRF template name.
          - Supported only when C(vrf_type=userDefined).
        type: str
      vrf_extension_template_name:
        description:
          - Custom VRF extension template name.
          - Supported only when C(vrf_type=userDefined).
        type: str
      service_vrf_template_name:
        description:
          - Custom service VRF template name.
          - Supported only when C(vrf_type=userDefined).
        type: str
      vrf_template_config:
        description:
          - Custom VRF template parameters.
          - Supported only when C(vrf_type=userDefined).
          - Values must be strings as required by the ND schema.
        type: dict
      vlan_id:
        description: VLAN ID for the VRF SVI (2-4094). Not used when C(l3vni_wo_vlan=true).
        type: int
      vrf_vlan_name:
        description: VLAN name for the VRF SVI.
        type: str
      vrf_intf_desc:
        description: Description for the VRF SVI interface.
        type: str
      vrf_int_mtu:
        description: MTU for the VRF SVI interface (68-9216).
        type: int
        default: 9216
      l3vni_wo_vlan:
        description: Configure L3VNI without VLAN/SVI.
        type: bool
        default: false
      vrf_description:
        description: Description of the VRF (max 255 characters).
        type: str
      loopback_route_tag:
        description: Routing tag for loopback routes (0-4294967295).
        type: int
        default: 12345
      redist_direct_rmap:
        description: Route map for redistribute direct (IPv4).
        type: str
        default: FABRIC-RMAP-REDIST-SUBNET
      v6_redist_direct_rmap:
        description: Route map for redistribute direct (IPv6).
        type: str
        default: FABRIC-RMAP-REDIST-SUBNET
      max_bgp_paths:
        description: Maximum eBGP multipaths (1-64).
        type: int
        default: 1
      max_ibgp_paths:
        description: Maximum iBGP multipaths (1-64).
        type: int
        default: 2
      ipv6_linklocal_enable:
        description: Enable IPv6 link-local on VRF SVI.
        type: bool
        default: true
      disable_rt_auto:
        description: Disable automatic route-target assignment.
        type: bool
        default: false
      import_vpn_rt:
        description: VPN import route targets.
        type: list
        elements: str
      export_vpn_rt:
        description: VPN export route targets.
        type: list
        elements: str
      import_evpn_rt:
        description: EVPN import route targets.
        type: list
        elements: str
      export_evpn_rt:
        description: EVPN export route targets.
        type: list
        elements: str
      trm_enable:
        description: Enable Tenant Routed Multicast.
        type: bool
        default: false
      no_rp:
        description: No RP for TRM (SSM only). Requires C(trm_enable=true).
        type: bool
        default: false
      rp_external:
        description: RP is external to the fabric. Requires C(trm_enable=true).
        type: bool
        default: false
      rp_address:
        description: IPv4 RP address. Requires C(trm_enable=true).
        type: str
      rp_loopback_id:
        description: Loopback interface ID for RP (0-1023). Requires C(trm_enable=true).
        type: int
      underlay_mcast_ip:
        description: Underlay IPv4 multicast address. Requires C(trm_enable=true).
        type: str
      overlay_mcast_group:
        description: Overlay multicast group (224.0.0.0/4 range). Requires C(trm_enable=true).
        type: str
      trm_bgw_msite:
        description: Enable TRM on border gateway multisite. Requires C(trm_enable=true).
        type: bool
        default: false
      import_mvpn_rt:
        description: MVPN import route targets. Requires C(trm_enable=true).
        type: list
        elements: str
      export_mvpn_rt:
        description: MVPN export route targets. Requires C(trm_enable=true).
        type: list
        elements: str
      adv_host_routes:
        description: Advertise /32 and /128 host routes to edge routers.
        type: bool
        default: false
      adv_default_routes:
        description: Advertise default route internally.
        type: bool
        default: true
      static_default_route:
        description: Configure static default route.
        type: bool
        default: true
      bgp_password:
        description: BGP neighbour password (4-32 characters).
        type: str
      bgp_passwd_encrypt:
        description: BGP password encryption type, 3 (3DES) or 7 (Cisco Type-7).
        type: int
        choices: [ 3, 7 ]
      netflow_enable:
        description: Enable netflow on VRF-Lite sub-interface.
        type: bool
        default: false
      nf_monitor:
        description: Netflow monitor name. Required when C(netflow_enable=true).
        type: str
      deploy:
        description:
          - Deploy pending VRF attachment changes for this VRF.
          - For parent fabrics, deployment is performed once after all child
            fabric tasks complete.
          - Applies only to parent/standalone VRF attachments, not child fabric
            override entries.
        type: bool
        default: true
      deploy_type:
        description:
          - Scope of the deploy operation when C(deploy=true).
          - C(switch) deploys only the switches affected by this VRF attachment
            operation when switch identifiers are available.
          - C(vrf) deploys the pending VRF changes for this VRF.
        type: str
        default: switch
        choices:
          - switch
          - vrf
      attach:
        description:
          - Parent/standalone switch attachment entries for this VRF.
          - Switches are identified by management IP address and resolved to
            ND C(switchId) values before the attachment payload is sent.
          - Not supported under C(child_fabric_config).
        type: list
        elements: dict
        suboptions:
          ip_address:
            description: Management IP address of the switch to attach.
            type: str
            required: true
          loopback_id:
            description: Attachment loopback interface identifier, 0-1023.
            type: int
          loopback_ipv4_address:
            description: Attachment loopback IPv4 address.
            type: str
          loopback_ipv6_address:
            description: Attachment loopback IPv6 address.
            type: str
          import_vpn_rt:
            description: Attachment-level VPN import route targets.
            type: list
            elements: str
          export_vpn_rt:
            description: Attachment-level VPN export route targets.
            type: list
            elements: str
          import_evpn_rt:
            description: Attachment-level EVPN import route targets.
            type: list
            elements: str
          export_evpn_rt:
            description: Attachment-level EVPN export route targets.
            type: list
            elements: str
      child_fabric_config:
        description:
          - Per-child-fabric override entries (parent fabrics only).
          - Each entry targets a child member fabric and may override
            TRM, advertising, BGP auth, netflow, and MVPN route-target settings.
          - Omitted fields inherit the parent VRF setting.
          - Ignored when C(state=deleted); child fabric tasks are not executed
            for delete operations.
        type: list
        elements: dict
        suboptions:
          fabric:
            description: Name of the child fabric.
            type: str
            required: true
          l3vni_wo_vlan:
            description: Enable L3VNI without VLAN on this child fabric.
            type: bool
          trm_enable:
            description: Enable Tenant Routed Multicast on this child fabric.
            type: bool
          no_rp:
            description: No RP, SSM only. Requires C(trm_enable=true).
            type: bool
          rp_external:
            description: RP is external to the child fabric. Requires C(trm_enable=true).
            type: bool
          rp_address:
            description: IPv4 RP address. Requires C(trm_enable=true).
            type: str
          rp_loopback_id:
            description: Loopback ID for RP (0-1023). Requires C(trm_enable=true).
            type: int
          underlay_mcast_ip:
            description: Underlay IPv4 multicast address. Requires C(trm_enable=true).
            type: str
          overlay_mcast_group:
            description: Overlay multicast group (224.0.0.0/4 range). Requires C(trm_enable=true).
            type: str
          trm_bgw_msite:
            description: Enable TRM on border gateway multisite. Requires C(trm_enable=true).
            type: bool
          import_mvpn_rt:
            description: MVPN import route targets. Requires C(trm_enable=true).
            type: list
            elements: str
          export_mvpn_rt:
            description: MVPN export route targets. Requires C(trm_enable=true).
            type: list
            elements: str
          adv_host_routes:
            description: Advertise /32 and /128 host routes.
            type: bool
          adv_default_routes:
            description: Advertise default route internally.
            type: bool
          static_default_route:
            description: Configure static default route.
            type: bool
          bgp_password:
            description: BGP neighbour password (4-32 characters).
            type: str
          bgp_passwd_encrypt:
            description: BGP password encryption type.
            type: int
            choices: [ 3, 7 ]
          netflow_enable:
            description: Enable netflow on this child fabric.
            type: bool
          nf_monitor:
            description: Netflow monitor name.
            type: str
extends_documentation_fragment:
  - cisco.nd.modules
  - cisco.nd.check_mode
"""

EXAMPLES = r"""
# ── Standalone fabric — create a VRF ─────────────────────────────────────────
- name: Create VRF on standalone fabric
  cisco.nd.nd_vrf:
    fabric: fab1
    state: merged
    config:
      - vrf_name: VRF_BLUE
        vrf_id: 50010
        vlan_id: 2001

# ── Standalone fabric — create VRF with TRM ──────────────────────────────────
- name: Create VRF with Tenant Routed Multicast enabled
  cisco.nd.nd_vrf:
    fabric: fab1
    state: merged
    config:
      - vrf_name: VRF_MCAST
        vrf_id: 50020
        vlan_id: 2002
        trm_enable: true
        rp_address: 10.254.254.1
        rp_loopback_id: 100
        underlay_mcast_ip: 239.1.1.1
        overlay_mcast_group: 239.1.1.2

# ── Parent fabric — create VRF with child fabric-instance overrides ──────────
- name: Create VRF on MSD parent with per-child fabric-instance overrides
  cisco.nd.nd_vrf:
    fabric: msd_parent
    state: merged
    config:
      - vrf_name: VRF_BLUE
        vrf_id: 50010
        child_fabric_config:
          - fabric: child_fabric_1
            adv_host_routes: true
          - fabric: child_fabric_2
            adv_default_routes: false

# ── Child fabric — query only ────────────────────────────────────────────────
- name: Query VRFs on a child fabric (write ops must go through parent)
  cisco.nd.nd_vrf:
    fabric: child_fabric_1
    state: query
    config: []

# ── Delete VRFs ──────────────────────────────────────────────────────────────
- name: Delete a VRF
  cisco.nd.nd_vrf:
    fabric: fab1
    state: deleted
    config:
      - vrf_name: VRF_BLUE

# ── Replace VRF configuration ───────────────────────────────────────────────
- name: Replace VRF configuration (full replace)
  cisco.nd.nd_vrf:
    fabric: fab1
    state: replaced
    config:
      - vrf_name: VRF_BLUE
        vrf_id: 50010
        vlan_id: 2001
        vrf_description: "Updated Blue VRF"
        max_bgp_paths: 4
        max_ibgp_paths: 4
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
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    try:
        fabric_name: str = module.params["fabric"]

        # Resolve the VRF strategy from the ND API
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
