# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""VRF data models (API request/response representations for CRUD operations).

Based on OpenAPI schema for Nexus Dashboard Manage APIs v1.1.332.

Covers:
- GET /fabrics/{fabricName}/vrfPreInformation
- GET /fabrics/{fabricName}/vrfs
- POST /fabrics/{fabricName}/vrfs
- GET /fabrics/{fabricName}/vrfs/{vrfName}
- PUT /fabrics/{fabricName}/vrfs/{vrfName}
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Any, Dict, List, Optional, ClassVar, Literal

from ansible_collections.cisco.nd.plugins.module_utils.common.pydantic_compat import (
    Field,
    field_validator,
)
from ansible_collections.cisco.nd.plugins.module_utils.models.base import NDBaseModel
from ansible_collections.cisco.nd.plugins.module_utils.models.nested import (
    NDNestedModel,
)

from ansible_collections.cisco.nd.plugins.module_utils.models.manage_vrfs.enums import (
    ConfigurationStatus,
    DpuAffinity,
    OperationStatus,
    VrfType,
)
from ansible_collections.cisco.nd.plugins.module_utils.models.manage_vrfs.validators import (
    VrfValidators,
)


# =============================================================================
# Nested / shared nested models
# =============================================================================


class MetadataCounts(NDNestedModel):
    """
    Pagination counts embedded in a list API response.

    Based on: components/schemas/MetadataCounts
    """

    identifiers: ClassVar[List[str]] = []
    total: int = Field(
        ...,
        description="The total number of records",
    )
    remaining: int = Field(
        ...,
        description="The remaining number of records",
    )


class Metadata(NDNestedModel):
    """
    Pagination metadata returned by list API calls.

    Based on: components/schemas/Metadata
    """

    identifiers: ClassVar[List[str]] = []
    counts: Optional[MetadataCounts] = Field(
        default=None,
        description="Count information including total and remaining",
    )
    links: Optional[Dict[str, str]] = Field(
        default=None,
        description="Pagination link URLs (next, previous)",
    )


class TrmData(NDNestedModel):
    """
    TRM (Tenant Routed Multicast) configuration data.

    Based on: components/schemas/trmData (allOf: trmCommonFields,
    trmV4Fields, trmV6Fields, trmFlags)
    """

    identifiers: ClassVar[List[str]] = []
    # trmCommonFields
    mvpn_route_target_import: Optional[List[str]] = Field(
        default=None,
        alias="mvpnRouteTargetImport",
        description="List of MVPN routes imports, NX-OS specific",
    )
    mvpn_route_target_export: Optional[List[str]] = Field(
        default=None,
        alias="mvpnRouteTargetExport",
        description="List of MVPN routes exports, NX-OS specific",
    )
    mvpn_inter_as: Optional[bool] = Field(
        default=False,
        alias="mvpnInterAs",
        description=(
            "Use the inter-as keyword for MVPN address family routes "
            "to cross BGP AS boundaries. IOS XE specific"
        ),
    )
    l3_vni_multicast_group: Optional[str] = Field(
        default=None,
        alias="l3VniMulticastGroup",
        description="Underlay multicast address",
    )
    trm_on_bgw: Optional[bool] = Field(
        default=False,
        alias="trmOnBgw",
        description="Enable TRM on border gateway multisite",
    )
    loopback_number: Optional[int] = Field(
        default=None,
        alias="loopbackNumber",
        ge=0,
        le=1023,
        description="Identifier for the loopback interface",
    )
    # trmV4Fields
    v4_rp_absent: Optional[bool] = Field(
        default=False,
        alias="v4RpAbsent",
        description=(
            "There is no RP in TRMv4 as only SSM is used"
        ),
    )
    v4_rp_external: Optional[bool] = Field(
        default=False,
        alias="v4RpExternal",
        description="Is TRMv4 RP external to the fabric?",
    )
    v4_rp_address: Optional[str] = Field(
        default=None,
        alias="v4RpAddress",
        description="IPv4 address for the RP",
    )
    v4_multicast_group: Optional[str] = Field(
        default=None,
        alias="v4MulticastGroup",
        description="Multicast group for TRMv4",
    )
    # trmV6Fields
    v6_rp_absent: Optional[bool] = Field(
        default=False,
        alias="v6RpAbsent",
        description=(
            "There is no RP in TRMv6 as only SSM is used. NX-OS specific"
        ),
    )
    v6_rp_external: Optional[bool] = Field(
        default=False,
        alias="v6RpExternal",
        description=(
            "Is RP external to the fabric in TRMv6? NX-OS specific"
        ),
    )
    v6_rp_address: Optional[str] = Field(
        default=None,
        alias="v6RpAddress",
        description="IPv6 address. NX-OS specific",
    )
    v6_multicast_group: Optional[str] = Field(
        default=None,
        alias="v6MulticastGroup",
        description="Multicast group for TRMv6. NX-OS specific",
    )
    # trmFlags
    ipv4_trm: Optional[bool] = Field(
        default=None,
        alias="ipv4Trm",
        description="Enable IPv4 tenant routed multicast",
    )
    ipv6_trm: Optional[bool] = Field(
        default=None,
        alias="ipv6Trm",
        description="Enable IPv6 tenant routed multicast",
    )

    @field_validator("v4_rp_address", mode="before")
    @classmethod
    def validate_v4_rp_address(cls, v: Optional[str]) -> Optional[str]:
        return VrfValidators.validate_ipv4_address(v)

    @field_validator("l3_vni_multicast_group", "v4_multicast_group", mode="before")
    @classmethod
    def validate_ipv4_fields(cls, v: Optional[str]) -> Optional[str]:
        return VrfValidators.validate_ipv4_address(v)

    @field_validator("v6_rp_address", mode="before")
    @classmethod
    def validate_v6_rp_address(cls, v: Optional[str]) -> Optional[str]:
        return VrfValidators.validate_ipv6_address(v)

    @field_validator("v6_multicast_group", mode="before")
    @classmethod
    def validate_v6_multicast(cls, v: Optional[str]) -> Optional[str]:
        return VrfValidators.validate_cidrv6(v)


class VxlanCoreData(NDNestedModel):
    """
    VXLAN VRF core configuration data.

    Based on: components/schemas/vxlanCoreData
    """

    identifiers: ClassVar[List[str]] = []
    vrf_vlan_name: Optional[str] = Field(
        default=None,
        alias="vrfVlanName",
        description="Name associated with the VLAN for the VRF",
    )
    vrf_interface_description: Optional[str] = Field(
        default=None,
        alias="vrfInterfaceDescription",
        description="Description of the interface associated with the VRF",
    )
    vrf_description: Optional[str] = Field(
        default=None,
        alias="vrfDescription",
        max_length=255,
        description="Description of the VRF",
    )
    mtu: Optional[int] = Field(
        default=9216,
        ge=68,
        le=9216,
        description="MTU associated with the interface",
    )
    routing_tag: Optional[int] = Field(
        default=12345,
        alias="routingTag",
        ge=0,
        le=4294967295,
        description="NX-OS specific",
    )
    vrf_route_map: Optional[str] = Field(
        default="FABRIC-RMAP-REDIST-SUBNET",
        alias="vrfRouteMap",
        description=(
            "Name of the route map applied to the VRF for controlling "
            "route redistribution"
        ),
    )
    v6_vrf_route_map: Optional[str] = Field(
        default="FABRIC-RMAP-REDIST-SUBNET",
        alias="v6VrfRouteMap",
        description=(
            "If not set, redistribute direct route map will be used"
        ),
    )
    max_bgp_paths: Optional[int] = Field(
        default=1,
        alias="maxBgpPaths",
        ge=1,
        le=64,
        description="1-64 for NX-OS, 1-32 for IOS XE",
    )
    max_ibgp_paths: Optional[int] = Field(
        default=2,
        alias="maxIbgpPaths",
        ge=1,
        le=64,
        description="1-64 for NX-OS, 1-32 for IOS XE",
    )
    ipv6_link_local: Optional[bool] = Field(
        default=True,
        alias="ipv6LinkLocal",
        description=(
            "Enables IPv6 link-local option under VRF SVI. "
            "Not applicable to L3VNI without VLAN config. NX-OS specific"
        ),
    )
    disable_rt_auto: Optional[bool] = Field(
        default=False,
        alias="disableRtAuto",
        description=(
            "Applicable to IPv4, IPv6 VPN/EVPN/MVPN. RtAuto automatically "
            "assigns route targets to VPNs"
        ),
    )
    route_target_import: Optional[List[str]] = Field(
        default=None,
        alias="routeTargetImport",
        description="List of VPN import route targets",
    )
    route_target_export: Optional[List[str]] = Field(
        default=None,
        alias="routeTargetExport",
        description="List of VPN export route targets",
    )
    evpn_route_target_import: Optional[List[str]] = Field(
        default=None,
        alias="evpnRouteTargetImport",
        description="List of EVPN import route targets",
    )
    evpn_route_target_export: Optional[List[str]] = Field(
        default=None,
        alias="evpnRouteTargetExport",
        description="List of EVPN export route targets",
    )


class VxlanFabricInstance(NDNestedModel):
    """
    Fabric instance fields for a VXLAN VRF.

    Based on: components/schemas/vxlanFabricInstance
    These fields are not applicable to fabric groups.
    """

    identifiers: ClassVar[List[str]] = []
    l3_vni_without_vlan: Optional[bool] = Field(
        default=False,
        alias="l3VniWithoutVlan",
        description=(
            "L3 VNI configuration without VLAN configuration. "
            "NX-OS specific"
        ),
    )
    bgp_best_path_relax: Optional[bool] = Field(
        default=False,
        alias="bgpBestPathRelax",
        description=(
            "Allow multipath when remote BGP peers have different ASN. "
            "NX-OS specific"
        ),
    )
    bgp_log_neighbor_change: Optional[bool] = Field(
        default=False,
        alias="bgpLogNeighborChange",
        description="Log messages for BGP neighbor up/down event",
    )
    bgp_allow_as_in: Optional[bool] = Field(
        default=False,
        alias="bgpAllowAsIn",
        description=(
            "Accept AS-path even if it contains ASN configured on this "
            "border switch. VRF Lite specific."
        ),
    )
    bgp_allow_as_in_num: Optional[int] = Field(
        default=3,
        alias="bgpAllowAsInNum",
        ge=1,
        le=10,
        description=(
            "Number of occurrences of ASN allowed in the AS-path. "
            "VRF Lite specific."
        ),
    )
    bgp_as_override: Optional[bool] = Field(
        default=False,
        alias="bgpAsOverride",
        description=(
            "Override matching ASN while sending a BGP update. "
            "VRF Lite specific."
        ),
    )
    bgp_disable_peer_as_check: Optional[bool] = Field(
        default=False,
        alias="bgpDisablePeerAsCheck",
        description=(
            "Disable checking of peer ASN while advertising route to that "
            "BGP peer. NX-OS specific. VRF Lite specific."
        ),
    )
    bgp_soft_reconfig_always: Optional[bool] = Field(
        default=False,
        alias="bgpSoftReconfigAlways",
        description=(
            "Allow inbound soft reconfiguration always. VRF Lite specific."
        ),
    )
    advertise_host_route: Optional[bool] = Field(
        default=False,
        alias="advertiseHostRoute",
        description=(
            "Flag to control advertisement of /32 and /128 routes "
            "to edge routers"
        ),
    )
    advertise_default_route: Optional[bool] = Field(
        default=True,
        alias="advertiseDefaultRoute",
        description=(
            "Flag to control advertisement of default route internally"
        ),
    )
    configure_static_default_route: Optional[bool] = Field(
        default=True,
        alias="configureStaticDefaultRoute",
        description="Flag to control static default route configuration",
    )
    bgp_password: Optional[str] = Field(
        default=None,
        alias="bgpPassword",
        min_length=4,
        max_length=32,
        description="VRF Lite BGP neighbor password",
    )
    bgp_password_key_type: Optional[int] = Field(
        default=3,
        alias="bgpPasswordKeyType",
        description=(
            "Represents the BGP password key type. "
            "Required if BGP authentication is enabled"
        ),
    )
    netflow: Optional[bool] = Field(
        default=False,
        description=(
            "For netflow on VRF-LITE sub-interface. "
            "Supported only if netflow is enabled on fabric"
        ),
    )
    netflow_monitor: Optional[str] = Field(
        default=None,
        alias="netflowMonitor",
        description=(
            "For NX-OS only. Required when netflow is enabled"
        ),
    )
    stretch: Optional[str] = Field(
        default=None,
        description="Border gateway list name",
    )
    trm_data: Optional[TrmData] = Field(
        default=None,
        alias="trmData",
        description="TRM configuration data",
    )

    @field_validator("bgp_password_key_type", mode="before")
    @classmethod
    def validate_bgp_key_type(
        cls, v: Optional[int]
    ) -> Optional[int]:
        if v is not None and v not in (3, 7):
            raise ValueError(
                f"bgpPasswordKeyType must be 3 or 7, got: {v}"
            )
        return v


class SecurityGroupData(NDNestedModel):
    """
    Security group configuration within a VRF.

    Based on: components/schemas/securityGroupData
    """

    identifiers: ClassVar[List[str]] = []
    default_security_action: Optional[
        Literal["unenforcedOrNone", "enforcedPermit", "enforcedDeny"]
    ] = Field(
        default=None,
        alias="defaultSecurityAction",
        description=(
            "Type of enforcement. Use 'unenforcedOrNone' if security "
            "groups are not enabled for the fabric. Only applicable to "
            "vxlan type fabrics."
        ),
    )
    default_security_group_tag: Optional[int] = Field(
        default=None,
        alias="defaultSecurityGroupTag",
        ge=16,
        le=65535,
        description=(
            "Tag ID for the default security group. Applicable only if "
            "security groups are enabled and enforced."
        ),
    )


class L4l7ServiceData(NDNestedModel):
    """
    L4L7 service configuration schema.

    Based on: components/schemas/l4l7ServiceData
    """

    identifiers: ClassVar[List[str]] = []
    service_config: Optional[Dict[str, str]] = Field(
        default=None,
        alias="serviceConfig",
        description="Service configuration in JSON format",
    )
    service_epbr_config: Optional[Dict[str, str]] = Field(
        default=None,
        alias="serviceEpbrConfig",
        description="ePBR service configuration in JSON format",
    )


# =============================================================================
# Top-level VRF data models
# =============================================================================


class VrfDataModel(NDBaseModel):
    """
    Schema for a VRF object as returned/sent by list, get, create, and
    replace VRF endpoints.

    Based on: components/schemas/vrfCommon + vxlanVrfBase +
              securityGroupData + vxlanVrfProperties
    Path: GET/POST /fabrics/{fabricName}/vrfs
          GET/PUT  /fabrics/{fabricName}/vrfs/{vrfName}

    Note: ``vrfSchema`` is a discriminated oneOf over 12 VRF types
    (discriminator: ``vrfType``). This model covers the common fields
    shared across all types (``vrfCommon``) plus the VXLAN-specific base
    fields (``vxlanVrfBase`` + ``securityGroupData``).  The type-specific
    ``coreData`` and ``fabricData`` are captured as typed nested models
    (``VxlanCoreData``, ``VxlanFabricInstance``) for the standard VXLAN
    variant; for other types they are accepted as free-form dicts.
    """

    identifiers: ClassVar[List[str]] = ["vrf_name", "fabric_name"]
    identifier_strategy: ClassVar[
        Optional[Literal["single", "composite", "hierarchical", "singleton"]]
    ] = "composite"

    # vrfCommon required fields
    fabric_name: str = Field(
        ...,
        alias="fabricName",
        description="Name of the fabric",
    )
    vrf_name: str = Field(
        ...,
        alias="vrfName",
        max_length=94,
        description=(
            "Name of the VRF. For multi-tenant environments, use the "
            "format tenantName~vrfName."
        ),
    )
    # vrfCommon optional fields
    vrf_status: Optional[ConfigurationStatus] = Field(
        default=None,
        alias="vrfStatus",
        description="Configuration deployment status (read-only)",
    )
    tenant_name: Optional[str] = Field(
        default=None,
        alias="tenantName",
        description="Name of the tenant (multi-tenant)",
    )
    # vxlanVrfBase fields
    vrf_id: Optional[int] = Field(
        default=None,
        alias="vrfId",
        ge=1,
        le=16777214,
        description="ID of the VRF",
    )
    vlan_id: Optional[int] = Field(
        default=None,
        alias="vlanId",
        ge=2,
        le=4094,
        description="VLAN identifier. Must be between 2 and 4094.",
    )
    vrf_type: Optional[str] = Field(
        default=None,
        alias="vrfType",
        description="Type of VRF (discriminator for vrfSchema)",
    )
    core_data: Optional[Any] = Field(
        default=None,
        alias="coreData",
        description=(
            "VRF core data. For VXLAN VRFs this is ``VxlanCoreData``; "
            "for other types this is a free-form object."
        ),
    )
    fabric_data: Optional[Any] = Field(
        default=None,
        alias="fabricData",
        description=(
            "Fabric-instance data. For VXLAN VRFs this is "
            "``VxlanFabricInstance``; for other types a free-form object."
        ),
    )
    service_data: Optional[L4l7ServiceData] = Field(
        default=None,
        alias="serviceData",
        description="L4L7 service configuration",
    )
    # securityGroupData fields
    default_security_action: Optional[
        Literal["unenforcedOrNone", "enforcedPermit", "enforcedDeny"]
    ] = Field(
        default=None,
        alias="defaultSecurityAction",
        description=(
            "Type of enforcement. Use 'unenforcedOrNone' if security "
            "groups are not enabled for the fabric. Only applicable to "
            "vxlan type fabrics."
        ),
    )
    default_security_group_tag: Optional[int] = Field(
        default=None,
        alias="defaultSecurityGroupTag",
        ge=16,
        le=65535,
        description=(
            "Tag ID for the default security group. Applicable only if "
            "security groups are enabled and enforced."
        ),
    )

    @field_validator("vrf_name", mode="before")
    @classmethod
    def validate_vrf_name(cls, v: str) -> str:
        return VrfValidators.require_vrf_name(v)


class VrfCreateRequestModel(NDBaseModel):
    """
    Request body for creating one or more VRFs in the specified fabric.

    Based on: POST /fabrics/{fabricName}/vrfs request body
    Schema: ``{ vrfs: vrfSchema[] }``
    """

    identifiers: ClassVar[List[str]] = []
    identifier_strategy: ClassVar[
        Optional[Literal["single", "composite", "hierarchical", "singleton"]]
    ] = "singleton"

    vrfs: List[VrfDataModel] = Field(
        ...,
        min_length=1,
        description="List of VRFs to be created",
    )


class VrfCreate207StatusModel(NDNestedModel):
    """
    Status of a single VRF creation in a 207 multi-status response.

    Based on: components/schemas/vrfCreate207Status
    (allOf: schemas-multiStatusBase + vrfId)
    """

    identifiers: ClassVar[List[str]] = []
    vrf_name: Optional[str] = Field(
        default=None,
        alias="vrfName",
        description="Name of the VRF",
    )
    status: Optional[OperationStatus] = Field(
        default=None,
        description="Status of the VRF creation",
    )
    message: Optional[str] = Field(
        default=None,
        description="Error message in case of VRF operation failure",
    )
    vrf_id: Optional[int] = Field(
        default=None,
        alias="vrfId",
        description="The unique ID of the created VRF",
    )


class VrfCreateResponseModel(NDBaseModel):
    """
    207 multi-status response for bulk VRF creation.

    Based on: POST /fabrics/{fabricName}/vrfs response
    Schema: ``{ results: vrfCreate207Status[] }``
    """

    identifiers: ClassVar[List[str]] = []
    identifier_strategy: ClassVar[
        Optional[Literal["single", "composite", "hierarchical", "singleton"]]
    ] = "singleton"

    results: Optional[List[VrfCreate207StatusModel]] = Field(
        default=None,
        description="List of statuses for each VRF creation request",
    )


class VrfListResponseModel(NDBaseModel):
    """
    Response body for listing VRFs.

    Based on: GET /fabrics/{fabricName}/vrfs response
    Schema: ``{ vrfs: vrfSchema[], meta: Metadata }``
    """

    identifiers: ClassVar[List[str]] = []
    identifier_strategy: ClassVar[
        Optional[Literal["single", "composite", "hierarchical", "singleton"]]
    ] = "singleton"

    vrfs: Optional[List[VrfDataModel]] = Field(
        default=None,
        description="List of all VRFs under the given fabric",
    )
    meta: Optional[Metadata] = Field(
        default=None,
        description="Pagination and result-count metadata",
    )


class VrfPreInformationResponseModel(NDBaseModel):
    """
    Response body for the VRF pre-information endpoint.

    Based on: components/schemas/vrfInfoGet
    Path: GET /fabrics/{fabricName}/vrfPreInformation
    """

    identifiers: ClassVar[List[str]] = []
    identifier_strategy: ClassVar[
        Optional[Literal["single", "composite", "hierarchical", "singleton"]]
    ] = "singleton"

    l3_vni: Optional[int] = Field(
        default=None,
        alias="l3Vni",
        description="Layer 3 VNI (Virtual Network Identifier)",
    )
    vrf_name_prefix: Optional[str] = Field(
        default=None,
        alias="vrfNamePrefix",
        description="Prefix for the VRF name",
    )
    vlan_id: Optional[int] = Field(
        default=None,
        alias="vlanId",
        description="VLAN ID for the VRF",
    )
    default_security_group_tag: Optional[int] = Field(
        default=None,
        alias="defaultSecurityGroupTag",
        description=(
            "Tag ID for the default security group. Applicable only if "
            "security groups are enabled and enforced."
        ),
    )


__all__ = [
    "L4l7ServiceData",
    "Metadata",
    "MetadataCounts",
    "SecurityGroupData",
    "TrmData",
    "VrfCreate207StatusModel",
    "VrfCreateRequestModel",
    "VrfCreateResponseModel",
    "VrfDataModel",
    "VrfListResponseModel",
    "VrfPreInformationResponseModel",
    "VxlanCoreData",
    "VxlanFabricInstance",
]
