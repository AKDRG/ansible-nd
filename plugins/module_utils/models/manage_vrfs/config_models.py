# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Playbook-facing Pydantic models for VRF configuration.

Three models covering the three deployment topologies exposed by nd_vrf.py:

- ``VrfChildConfigModel``  — per-child-fabric override entry (nested, used
  inside ``VrfParentConfigModel``).
- ``VrfConfigModel``       — standalone fabric VRF config (full field set).
- ``VrfParentConfigModel`` — parent (MSD / MFD) fabric VRF config; carries
  identity + shared fields and a list of per-child overrides.

Cross-field parameter dependencies (l3vni_wo_vlan, TRM group, no_rp,
netflow, bgp_password) are enforced by ``@model_validator`` hooks.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self  # type: ignore[assignment]

from typing import ClassVar, List, Optional, Union

from ansible_collections.cisco.nd.plugins.module_utils.common.pydantic_compat import (
    Field,
    field_validator,
    model_validator,
)
from ansible_collections.cisco.nd.plugins.module_utils.models.base import NDBaseModel
from ansible_collections.cisco.nd.plugins.module_utils.models.nested import (
    NDNestedModel,
)
from ansible_collections.cisco.nd.plugins.module_utils.models.manage_vrfs.validators import (
    VrfValidators,
)


# =============================================================================
# VrfChildConfigModel — per-child-fabric override entry
# =============================================================================


class VrfChildConfigModel(NDNestedModel):
    """
    Per-child-fabric override entry within a parent VRF config.

    Identifies a child fabric by name and provides optional per-fabric
    overrides for VLAN, TRM, advertising, BGP authentication, netflow,
    and route-target settings.

    All fields except ``fabric`` are optional; absent fields mean "inherit
    the parent setting".

    Based on: nd_vrf.py config.child_fabric_config suboptions
    """

    identifiers: ClassVar[List[str]] = []

    # --- Identity ---

    fabric: str = Field(
        description="Name of the child fabric",
    )

    # --- VLAN / SVI overrides ---

    vlan_id: Optional[int] = Field(
        default=None,
        alias="vlanId",
        ge=2,
        le=4094,
        description="VLAN ID for the VRF SVI in this child fabric (2–4094)",
    )
    vrf_vlan_name: Optional[str] = Field(
        default=None,
        alias="vrfVlanName",
        description="VLAN name for the VRF SVI",
    )
    vrf_intf_desc: Optional[str] = Field(
        default=None,
        alias="vrfIntfDesc",
        description="Description for the VRF SVI interface",
    )
    vrf_int_mtu: Optional[int] = Field(
        default=None,
        alias="vrfIntMtu",
        ge=68,
        le=9216,
        description="MTU for the VRF SVI interface (68–9216)",
    )

    # --- TRM overrides ---

    trm_enable: Optional[bool] = Field(
        default=None,
        alias="trmEnable",
        description="Enable Tenant Routed Multicast for this child fabric",
    )
    no_rp: Optional[bool] = Field(
        default=None,
        alias="noRp",
        description="No RP for TRM (SSM only); requires trm_enable=True",
    )
    rp_external: Optional[bool] = Field(
        default=None,
        alias="rpExternal",
        description="RP is external to the fabric; requires trm_enable=True",
    )
    rp_address: Optional[str] = Field(
        default=None,
        alias="rpAddress",
        description="IPv4 RP address; requires trm_enable=True",
    )
    rp_loopback_id: Optional[int] = Field(
        default=None,
        alias="rpLoopbackId",
        ge=0,
        le=1023,
        description="Loopback interface ID for RP (0–1023); requires trm_enable=True",
    )
    underlay_mcast_ip: Optional[str] = Field(
        default=None,
        alias="underlayMcastIp",
        description="Underlay IPv4 multicast address; requires trm_enable=True",
    )
    overlay_mcast_group: Optional[str] = Field(
        default=None,
        alias="overlayMcastGroup",
        description=(
            "Overlay multicast group IPv4 address (224.0.0.0/4 range); "
            "requires trm_enable=True"
        ),
    )
    trm_bgw_msite: Optional[bool] = Field(
        default=None,
        alias="trmBgwMsite",
        description=(
            "Enable TRM on border gateway multisite; requires trm_enable=True"
        ),
    )
    import_mvpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="importMvpnRt",
        description=(
            "MVPN import route targets (comma-separated string or list); "
            "requires trm_enable=True"
        ),
    )
    export_mvpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="exportMvpnRt",
        description=(
            "MVPN export route targets (comma-separated string or list); "
            "requires trm_enable=True"
        ),
    )

    # --- Routing / advertising overrides ---

    adv_host_routes: Optional[bool] = Field(
        default=None,
        alias="advHostRoutes",
        description="Advertise /32 and /128 host routes to edge routers",
    )
    adv_default_routes: Optional[bool] = Field(
        default=None,
        alias="advDefaultRoutes",
        description="Advertise default route internally",
    )
    static_default_route: Optional[bool] = Field(
        default=None,
        alias="staticDefaultRoute",
        description="Configure static default route",
    )

    # --- BGP authentication overrides ---

    bgp_password: Optional[str] = Field(
        default=None,
        alias="bgpPassword",
        min_length=4,
        max_length=32,
        description="BGP neighbour password (4–32 characters)",
    )
    bgp_passwd_encrypt: Optional[int] = Field(
        default=None,
        alias="bgpPasswdEncrypt",
        description=(
            "BGP password encryption type: 3 (3DES) or 7 (Cisco Type-7); "
            "required when bgp_password is set"
        ),
    )

    # --- Netflow overrides ---

    netflow_enable: Optional[bool] = Field(
        default=None,
        alias="netflowEnable",
        description="Enable netflow on VRF-Lite sub-interface",
    )
    nf_monitor: Optional[str] = Field(
        default=None,
        alias="nfMonitor",
        description="Netflow monitor name; required when netflow_enable=True",
    )

    # --- Route-target overrides ---

    import_vpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="importVpnRt",
        description="VPN import route targets (comma-separated string or list)",
    )
    export_vpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="exportVpnRt",
        description="VPN export route targets (comma-separated string or list)",
    )
    import_evpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="importEvpnRt",
        description="EVPN import route targets (comma-separated string or list)",
    )
    export_evpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="exportEvpnRt",
        description="EVPN export route targets (comma-separated string or list)",
    )

    # ------------------------------------------------------------------
    # Field validators
    # ------------------------------------------------------------------

    @field_validator("vrf_vlan_name", mode="before")
    @classmethod
    def _validate_vrf_vlan_name(cls, v: Optional[str]) -> Optional[str]:
        return VrfValidators.validate_vrf_vlan_name(v)

    @field_validator("rp_address", "underlay_mcast_ip", mode="before")
    @classmethod
    def _validate_ipv4(cls, v: Optional[str]) -> Optional[str]:
        return VrfValidators.validate_ipv4_address(v)

    @field_validator("overlay_mcast_group", mode="before")
    @classmethod
    def _validate_mcast_group(cls, v: Optional[str]) -> Optional[str]:
        return VrfValidators.validate_overlay_mcast_group(v)

    @field_validator("bgp_passwd_encrypt", mode="before")
    @classmethod
    def _validate_bgp_encrypt(cls, v: Optional[int]) -> Optional[int]:
        return VrfValidators.validate_bgp_passwd_encrypt(v)

    @field_validator(
        "import_vpn_rt",
        "export_vpn_rt",
        "import_evpn_rt",
        "export_evpn_rt",
        "import_mvpn_rt",
        "export_mvpn_rt",
        mode="before",
    )
    @classmethod
    def _normalize_rt(
        cls, v: Optional[Union[str, List[str]]]
    ) -> Optional[List[str]]:
        return VrfValidators.normalize_route_targets(v)

    # ------------------------------------------------------------------
    # Cross-field validators
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _check_trm_fields(self) -> Self:
        """Forbid TRM-dependent fields when trm_enable is explicitly False."""
        if self.trm_enable is False:
            trm_fields = {
                "no_rp": self.no_rp,
                "rp_external": self.rp_external,
                "rp_address": self.rp_address,
                "rp_loopback_id": self.rp_loopback_id,
                "underlay_mcast_ip": self.underlay_mcast_ip,
                "overlay_mcast_group": self.overlay_mcast_group,
                "trm_bgw_msite": self.trm_bgw_msite,
                "import_mvpn_rt": self.import_mvpn_rt,
                "export_mvpn_rt": self.export_mvpn_rt,
            }
            set_fields = [k for k, v in trm_fields.items() if v is not None]
            if set_fields:
                raise ValueError(
                    f"The following fields require trm_enable=True: "
                    f"{', '.join(set_fields)}"
                )
        return self

    @model_validator(mode="after")
    def _check_no_rp_fields(self) -> Self:
        """Forbid rp_external and rp_address when no_rp=True."""
        if self.no_rp is True:
            bad = {}
            if self.rp_external is True:
                bad["rp_external"] = self.rp_external
            if self.rp_address is not None:
                bad["rp_address"] = self.rp_address
            if bad:
                raise ValueError(
                    f"The following fields are not applicable when no_rp=True: "
                    f"{', '.join(bad.keys())}"
                )
        return self

    @model_validator(mode="after")
    def _check_netflow_monitor(self) -> Self:
        """Require nf_monitor when netflow_enable=True."""
        if self.netflow_enable is True and not self.nf_monitor:
            raise ValueError("nf_monitor is required when netflow_enable=True")
        return self

    @model_validator(mode="after")
    def _check_bgp_password(self) -> Self:
        """Require bgp_passwd_encrypt when bgp_password is set."""
        if self.bgp_password is not None and self.bgp_passwd_encrypt is None:
            raise ValueError(
                "bgp_passwd_encrypt (3 or 7) is required when bgp_password is set"
            )
        return self


# =============================================================================
# VrfConfigModel — standalone fabric VRF config (full field set)
# =============================================================================


class VrfConfigModel(NDBaseModel):
    """
    Playbook-facing VRF configuration model for standalone fabrics.

    Carries the full field set from nd_vrf.py for use against a single
    (standalone) fabric.  All cross-field dependencies are validated by
    ``@model_validator`` hooks.

    Based on: nd_vrf.py config suboptions (standalone topology)
    """

    identifiers: ClassVar[Optional[List[str]]] = ["vrf_name"]
    identifier_strategy: ClassVar[Optional[str]] = "single"

    # --- Identity ---

    vrf_name: str = Field(
        alias="vrfName",
        description=(
            "Name of the VRF (max 94 chars; use tenant~vrfName for multi-tenant)"
        ),
    )
    vrf_id: Optional[int] = Field(
        default=None,
        alias="vrfId",
        ge=1,
        le=16777214,
        description="L3 VNI (VRF segment ID), 1–16777214",
    )

    # --- VRF templates ---

    vrf_template: str = Field(
        default="Default_VRF_Universal",
        alias="vrfTemplate",
        description="Name of the config template for the VRF",
    )
    vrf_extension_template: str = Field(
        default="Default_VRF_Extension_Universal",
        alias="vrfExtensionTemplate",
        description="Name of the config template for the VRF extension",
    )
    service_vrf_template: Optional[str] = Field(
        default=None,
        alias="serviceVrfTemplate",
        description="Name of the service config template for the VRF",
    )

    # --- VLAN / SVI ---

    vlan_id: Optional[int] = Field(
        default=None,
        alias="vlanId",
        ge=2,
        le=4094,
        description=(
            "VLAN ID for the VRF SVI (2–4094); "
            "not used when l3vni_wo_vlan=True"
        ),
    )
    vrf_vlan_name: Optional[str] = Field(
        default=None,
        alias="vrfVlanName",
        description=(
            "VLAN name for the VRF SVI; not used when l3vni_wo_vlan=True"
        ),
    )
    vrf_intf_desc: Optional[str] = Field(
        default=None,
        alias="vrfIntfDesc",
        description=(
            "Description for the VRF SVI interface; "
            "not used when l3vni_wo_vlan=True"
        ),
    )
    vrf_int_mtu: int = Field(
        default=9216,
        alias="vrfIntMtu",
        ge=68,
        le=9216,
        description=(
            "MTU for the VRF SVI interface (68–9216); "
            "not used when l3vni_wo_vlan=True"
        ),
    )

    # --- L3VNI without VLAN ---

    l3vni_wo_vlan: bool = Field(
        default=False,
        alias="l3vniWoVlan",
        description=(
            "Configure L3VNI without VLAN/SVI. When True, vlan_id, "
            "vrf_vlan_name, and vrf_intf_desc must not be set"
        ),
    )

    # --- Description ---

    vrf_description: Optional[str] = Field(
        default=None,
        alias="vrfDescription",
        max_length=255,
        description="Description of the VRF (max 255 characters)",
    )

    # --- Routing ---

    loopback_route_tag: int = Field(
        default=12345,
        alias="loopbackRouteTag",
        ge=0,
        le=4294967295,
        description="Routing tag for loopback routes (0–4294967295)",
    )
    redist_direct_rmap: str = Field(
        default="FABRIC-RMAP-REDIST-SUBNET",
        alias="redistDirectRmap",
        description="Route map name for redistribute direct (IPv4)",
    )
    v6_redist_direct_rmap: str = Field(
        default="FABRIC-RMAP-REDIST-SUBNET",
        alias="v6RedistDirectRmap",
        description="Route map name for redistribute direct (IPv6)",
    )
    max_bgp_paths: int = Field(
        default=1,
        alias="maxBgpPaths",
        ge=1,
        le=64,
        description="Maximum eBGP multipaths (1–64)",
    )
    max_ibgp_paths: int = Field(
        default=2,
        alias="maxIbgpPaths",
        ge=1,
        le=64,
        description="Maximum iBGP multipaths (1–64)",
    )
    ipv6_linklocal_enable: bool = Field(
        default=True,
        alias="ipv6LinkLocalEnable",
        description=(
            "Enable IPv6 link-local on VRF SVI; "
            "not applicable when l3vni_wo_vlan=True"
        ),
    )

    # --- Route targets ---

    disable_rt_auto: bool = Field(
        default=False,
        alias="disableRtAuto",
        description="Disable automatic route-target assignment",
    )
    import_vpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="importVpnRt",
        description="VPN import route targets (comma-separated string or list)",
    )
    export_vpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="exportVpnRt",
        description="VPN export route targets (comma-separated string or list)",
    )
    import_evpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="importEvpnRt",
        description="EVPN import route targets (comma-separated string or list)",
    )
    export_evpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="exportEvpnRt",
        description="EVPN export route targets (comma-separated string or list)",
    )

    # --- TRM ---

    trm_enable: bool = Field(
        default=False,
        alias="trmEnable",
        description="Enable Tenant Routed Multicast",
    )
    no_rp: bool = Field(
        default=False,
        alias="noRp",
        description="No RP for TRM (SSM only); requires trm_enable=True",
    )
    rp_external: bool = Field(
        default=False,
        alias="rpExternal",
        description="RP is external to the fabric; requires trm_enable=True",
    )
    rp_address: Optional[str] = Field(
        default=None,
        alias="rpAddress",
        description="IPv4 RP address; requires trm_enable=True",
    )
    rp_loopback_id: Optional[int] = Field(
        default=None,
        alias="rpLoopbackId",
        ge=0,
        le=1023,
        description=(
            "Loopback interface ID for RP (0–1023); requires trm_enable=True"
        ),
    )
    underlay_mcast_ip: Optional[str] = Field(
        default=None,
        alias="underlayMcastIp",
        description=(
            "Underlay IPv4 multicast address; requires trm_enable=True"
        ),
    )
    overlay_mcast_group: Optional[str] = Field(
        default=None,
        alias="overlayMcastGroup",
        description=(
            "Overlay multicast group IPv4 address (224.0.0.0/4 range); "
            "requires trm_enable=True"
        ),
    )
    trm_bgw_msite: bool = Field(
        default=False,
        alias="trmBgwMsite",
        description=(
            "Enable TRM on border gateway multisite; requires trm_enable=True"
        ),
    )
    import_mvpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="importMvpnRt",
        description=(
            "MVPN import route targets (comma-separated string or list); "
            "requires trm_enable=True"
        ),
    )
    export_mvpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="exportMvpnRt",
        description=(
            "MVPN export route targets (comma-separated string or list); "
            "requires trm_enable=True"
        ),
    )

    # --- Advertising ---

    adv_host_routes: bool = Field(
        default=False,
        alias="advHostRoutes",
        description="Advertise /32 and /128 host routes to edge routers",
    )
    adv_default_routes: bool = Field(
        default=True,
        alias="advDefaultRoutes",
        description="Advertise default route internally",
    )
    static_default_route: bool = Field(
        default=True,
        alias="staticDefaultRoute",
        description="Configure static default route",
    )

    # --- BGP authentication ---

    bgp_password: Optional[str] = Field(
        default=None,
        alias="bgpPassword",
        min_length=4,
        max_length=32,
        description="BGP neighbour password (4–32 characters)",
    )
    bgp_passwd_encrypt: Optional[int] = Field(
        default=None,
        alias="bgpPasswdEncrypt",
        description=(
            "BGP password encryption type: 3 (3DES) or 7 (Cisco Type-7); "
            "required when bgp_password is set"
        ),
    )

    # --- Netflow ---

    netflow_enable: bool = Field(
        default=False,
        alias="netflowEnable",
        description="Enable netflow on VRF-Lite sub-interface",
    )
    nf_monitor: Optional[str] = Field(
        default=None,
        alias="nfMonitor",
        description="Netflow monitor name; required when netflow_enable=True",
    )

    # ------------------------------------------------------------------
    # Field validators
    # ------------------------------------------------------------------

    @field_validator("vrf_name", mode="before")
    @classmethod
    def _validate_vrf_name(cls, v: str) -> str:
        return VrfValidators.require_vrf_name(v)

    @field_validator("vrf_vlan_name", mode="before")
    @classmethod
    def _validate_vrf_vlan_name(cls, v: Optional[str]) -> Optional[str]:
        return VrfValidators.validate_vrf_vlan_name(v)

    @field_validator("rp_address", "underlay_mcast_ip", mode="before")
    @classmethod
    def _validate_ipv4(cls, v: Optional[str]) -> Optional[str]:
        return VrfValidators.validate_ipv4_address(v)

    @field_validator("overlay_mcast_group", mode="before")
    @classmethod
    def _validate_mcast_group(cls, v: Optional[str]) -> Optional[str]:
        return VrfValidators.validate_overlay_mcast_group(v)

    @field_validator("bgp_passwd_encrypt", mode="before")
    @classmethod
    def _validate_bgp_encrypt(cls, v: Optional[int]) -> Optional[int]:
        return VrfValidators.validate_bgp_passwd_encrypt(v)

    @field_validator(
        "import_vpn_rt",
        "export_vpn_rt",
        "import_evpn_rt",
        "export_evpn_rt",
        "import_mvpn_rt",
        "export_mvpn_rt",
        mode="before",
    )
    @classmethod
    def _normalize_rt(
        cls, v: Optional[Union[str, List[str]]]
    ) -> Optional[List[str]]:
        return VrfValidators.normalize_route_targets(v)

    # ------------------------------------------------------------------
    # Cross-field validators
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _check_l3vni_wo_vlan(self) -> Self:
        """When l3vni_wo_vlan=True, VLAN/SVI fields must not be set."""
        if self.l3vni_wo_vlan:
            vlan_fields = {
                "vlan_id": self.vlan_id,
                "vrf_vlan_name": self.vrf_vlan_name,
                "vrf_intf_desc": self.vrf_intf_desc,
            }
            set_fields = [k for k, v in vlan_fields.items() if v is not None]
            if set_fields:
                raise ValueError(
                    f"The following fields must not be set when "
                    f"l3vni_wo_vlan=True: {', '.join(set_fields)}"
                )
        return self

    @model_validator(mode="after")
    def _check_trm_fields(self) -> Self:
        """Forbid TRM-dependent fields when trm_enable=False."""
        if not self.trm_enable:
            trm_fields = {
                "no_rp": self.no_rp or None,
                "rp_external": self.rp_external or None,
                "rp_address": self.rp_address,
                "rp_loopback_id": self.rp_loopback_id,
                "underlay_mcast_ip": self.underlay_mcast_ip,
                "overlay_mcast_group": self.overlay_mcast_group,
                "trm_bgw_msite": self.trm_bgw_msite or None,
                "import_mvpn_rt": self.import_mvpn_rt,
                "export_mvpn_rt": self.export_mvpn_rt,
            }
            set_fields = [k for k, v in trm_fields.items() if v is not None]
            if set_fields:
                raise ValueError(
                    f"The following fields require trm_enable=True: "
                    f"{', '.join(set_fields)}"
                )
        return self

    @model_validator(mode="after")
    def _check_no_rp_fields(self) -> Self:
        """Forbid rp_external and rp_address when no_rp=True."""
        if self.no_rp:
            bad = {}
            if self.rp_external:
                bad["rp_external"] = self.rp_external
            if self.rp_address is not None:
                bad["rp_address"] = self.rp_address
            if bad:
                raise ValueError(
                    f"The following fields are not applicable when no_rp=True: "
                    f"{', '.join(bad.keys())}"
                )
        return self

    @model_validator(mode="after")
    def _check_netflow_monitor(self) -> Self:
        """Require nf_monitor when netflow_enable=True."""
        if self.netflow_enable and not self.nf_monitor:
            raise ValueError("nf_monitor is required when netflow_enable=True")
        return self

    @model_validator(mode="after")
    def _check_bgp_password(self) -> Self:
        """Require bgp_passwd_encrypt when bgp_password is set."""
        if self.bgp_password is not None and self.bgp_passwd_encrypt is None:
            raise ValueError(
                "bgp_passwd_encrypt (3 or 7) is required when bgp_password is set"
            )
        return self


# =============================================================================
# VrfParentConfigModel — parent (MSD / MFD) fabric VRF config
# =============================================================================


class VrfParentConfigModel(NDBaseModel):
    """
    Playbook-facing VRF configuration model for parent (MSD / MFD) fabrics.

    Carries identity, template, and shared VRF properties. Per-fabric VLAN,
    advertising, BGP-auth and netflow overrides belong in
    ``child_fabric_config`` entries (``VrfChildConfigModel``).

    Cross-field TRM and bgp_password dependencies are validated identically
    to ``VrfConfigModel``.

    Based on: nd_vrf.py config suboptions (parent / MSD topology)
    """

    identifiers: ClassVar[Optional[List[str]]] = ["vrf_name"]
    identifier_strategy: ClassVar[Optional[str]] = "single"

    # --- Identity ---

    vrf_name: str = Field(
        alias="vrfName",
        description=(
            "Name of the VRF (max 94 chars; use tenant~vrfName for multi-tenant)"
        ),
    )
    vrf_id: Optional[int] = Field(
        default=None,
        alias="vrfId",
        ge=1,
        le=16777214,
        description="L3 VNI (VRF segment ID), 1–16777214",
    )

    # --- VRF templates ---

    vrf_template: str = Field(
        default="Default_VRF_Universal",
        alias="vrfTemplate",
        description="Name of the config template for the VRF",
    )
    vrf_extension_template: str = Field(
        default="Default_VRF_Extension_Universal",
        alias="vrfExtensionTemplate",
        description="Name of the config template for the VRF extension",
    )
    service_vrf_template: Optional[str] = Field(
        default=None,
        alias="serviceVrfTemplate",
        description="Name of the service config template for the VRF",
    )

    # --- L3VNI without VLAN ---

    l3vni_wo_vlan: bool = Field(
        default=False,
        alias="l3vniWoVlan",
        description=(
            "Configure L3VNI without VLAN/SVI across all member fabrics. "
            "Per-fabric VLAN settings are still possible in child_fabric_config"
        ),
    )

    # --- Description ---

    vrf_description: Optional[str] = Field(
        default=None,
        alias="vrfDescription",
        max_length=255,
        description="Description of the VRF (max 255 characters)",
    )

    # --- Routing ---

    loopback_route_tag: int = Field(
        default=12345,
        alias="loopbackRouteTag",
        ge=0,
        le=4294967295,
        description="Routing tag for loopback routes (0–4294967295)",
    )
    redist_direct_rmap: str = Field(
        default="FABRIC-RMAP-REDIST-SUBNET",
        alias="redistDirectRmap",
        description="Route map name for redistribute direct (IPv4)",
    )
    v6_redist_direct_rmap: str = Field(
        default="FABRIC-RMAP-REDIST-SUBNET",
        alias="v6RedistDirectRmap",
        description="Route map name for redistribute direct (IPv6)",
    )
    max_bgp_paths: int = Field(
        default=1,
        alias="maxBgpPaths",
        ge=1,
        le=64,
        description="Maximum eBGP multipaths (1–64)",
    )
    max_ibgp_paths: int = Field(
        default=2,
        alias="maxIbgpPaths",
        ge=1,
        le=64,
        description="Maximum iBGP multipaths (1–64)",
    )
    ipv6_linklocal_enable: bool = Field(
        default=True,
        alias="ipv6LinkLocalEnable",
        description="Enable IPv6 link-local on VRF SVI",
    )

    # --- Route targets ---

    disable_rt_auto: bool = Field(
        default=False,
        alias="disableRtAuto",
        description="Disable automatic route-target assignment",
    )
    import_vpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="importVpnRt",
        description="VPN import route targets (comma-separated string or list)",
    )
    export_vpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="exportVpnRt",
        description="VPN export route targets (comma-separated string or list)",
    )
    import_evpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="importEvpnRt",
        description="EVPN import route targets (comma-separated string or list)",
    )
    export_evpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="exportEvpnRt",
        description="EVPN export route targets (comma-separated string or list)",
    )

    # --- TRM ---

    trm_enable: bool = Field(
        default=False,
        alias="trmEnable",
        description="Enable Tenant Routed Multicast",
    )
    no_rp: bool = Field(
        default=False,
        alias="noRp",
        description="No RP for TRM (SSM only); requires trm_enable=True",
    )
    rp_external: bool = Field(
        default=False,
        alias="rpExternal",
        description="RP is external to the fabric; requires trm_enable=True",
    )
    rp_address: Optional[str] = Field(
        default=None,
        alias="rpAddress",
        description="IPv4 RP address; requires trm_enable=True",
    )
    rp_loopback_id: Optional[int] = Field(
        default=None,
        alias="rpLoopbackId",
        ge=0,
        le=1023,
        description=(
            "Loopback interface ID for RP (0–1023); requires trm_enable=True"
        ),
    )
    underlay_mcast_ip: Optional[str] = Field(
        default=None,
        alias="underlayMcastIp",
        description=(
            "Underlay IPv4 multicast address; requires trm_enable=True"
        ),
    )
    overlay_mcast_group: Optional[str] = Field(
        default=None,
        alias="overlayMcastGroup",
        description=(
            "Overlay multicast group IPv4 address (224.0.0.0/4 range); "
            "requires trm_enable=True"
        ),
    )
    trm_bgw_msite: bool = Field(
        default=False,
        alias="trmBgwMsite",
        description=(
            "Enable TRM on border gateway multisite; requires trm_enable=True"
        ),
    )
    import_mvpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="importMvpnRt",
        description=(
            "MVPN import route targets (comma-separated string or list); "
            "requires trm_enable=True"
        ),
    )
    export_mvpn_rt: Optional[List[str]] = Field(
        default=None,
        alias="exportMvpnRt",
        description=(
            "MVPN export route targets (comma-separated string or list); "
            "requires trm_enable=True"
        ),
    )

    # --- Child fabric configs ---

    child_fabric_config: Optional[List[VrfChildConfigModel]] = Field(
        default=None,
        alias="childFabricConfig",
        description=(
            "Per-child-fabric override entries for multisite / multicluster "
            "deployments"
        ),
    )

    # ------------------------------------------------------------------
    # Field validators
    # ------------------------------------------------------------------

    @field_validator("vrf_name", mode="before")
    @classmethod
    def _validate_vrf_name(cls, v: str) -> str:
        return VrfValidators.require_vrf_name(v)

    @field_validator("rp_address", "underlay_mcast_ip", mode="before")
    @classmethod
    def _validate_ipv4(cls, v: Optional[str]) -> Optional[str]:
        return VrfValidators.validate_ipv4_address(v)

    @field_validator("overlay_mcast_group", mode="before")
    @classmethod
    def _validate_mcast_group(cls, v: Optional[str]) -> Optional[str]:
        return VrfValidators.validate_overlay_mcast_group(v)

    @field_validator(
        "import_vpn_rt",
        "export_vpn_rt",
        "import_evpn_rt",
        "export_evpn_rt",
        "import_mvpn_rt",
        "export_mvpn_rt",
        mode="before",
    )
    @classmethod
    def _normalize_rt(
        cls, v: Optional[Union[str, List[str]]]
    ) -> Optional[List[str]]:
        return VrfValidators.normalize_route_targets(v)

    # ------------------------------------------------------------------
    # Cross-field validators
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _check_trm_fields(self) -> Self:
        """Forbid TRM-dependent fields when trm_enable=False."""
        if not self.trm_enable:
            trm_fields = {
                "no_rp": self.no_rp or None,
                "rp_external": self.rp_external or None,
                "rp_address": self.rp_address,
                "rp_loopback_id": self.rp_loopback_id,
                "underlay_mcast_ip": self.underlay_mcast_ip,
                "overlay_mcast_group": self.overlay_mcast_group,
                "trm_bgw_msite": self.trm_bgw_msite or None,
                "import_mvpn_rt": self.import_mvpn_rt,
                "export_mvpn_rt": self.export_mvpn_rt,
            }
            set_fields = [k for k, v in trm_fields.items() if v is not None]
            if set_fields:
                raise ValueError(
                    f"The following fields require trm_enable=True: "
                    f"{', '.join(set_fields)}"
                )
        return self

    @model_validator(mode="after")
    def _check_no_rp_fields(self) -> Self:
        """Forbid rp_external and rp_address when no_rp=True."""
        if self.no_rp:
            bad = {}
            if self.rp_external:
                bad["rp_external"] = self.rp_external
            if self.rp_address is not None:
                bad["rp_address"] = self.rp_address
            if bad:
                raise ValueError(
                    f"The following fields are not applicable when no_rp=True: "
                    f"{', '.join(bad.keys())}"
                )
        return self
