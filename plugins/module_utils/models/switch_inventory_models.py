# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Pydantic Models for Switch and Inventory Operations.

Generated from OpenAPI schema (manage.json) for Nexus Dashboard Manage APIs v1.1.332.
These models provide type-safe representations of the API request/response payloads
for switch discovery, inventory management, bootstrap (POAP), and RMA operations.

Usage:
    from ansible_collections.cisco.nd.plugins.module_utils.schema.switch_inventory_models import (
        SwitchRole,
        SystemMode,
        PlatformType,
        SnmpV3AuthProtocol,
        SwitchDiscoveryModel,
        AddSwitchesRequestModel,
        SwitchDataModel,
        BootstrapSwitchModel,
        RMASwitchModel,
    )
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import re
from enum import Enum
from ipaddress import ip_address, ip_network
from pydantic import Field, field_validator, model_validator
from typing import List, Dict, Any, Optional, ClassVar, Literal, Union
from typing_extensions import Self

# TODO: To be replaced with: 
from ansible_collections.cisco.nd.plugins.module_utils.models.base import NDBaseModel, NDNestedModel
# from models.base import NDBaseModel, NDNestedModel


# =============================================================================
# ENUMS - Extracted from OpenAPI Schema components/schemas
# =============================================================================

class SwitchRole(str, Enum):
    """
    Switch role enumeration.
    
    Based on: components/schemas/switchRole
    Description: The role of the switch, meta is a read-only switch role
    """
    BORDER = "border"
    BORDER_GATEWAY = "borderGateway"
    BORDER_GATEWAY_SPINE = "borderGatewaySpine"
    BORDER_GATEWAY_SUPER_SPINE = "borderGatewaySuperSpine"
    BORDER_SPINE = "borderSpine"
    BORDER_SUPER_SPINE = "borderSuperSpine"
    LEAF = "leaf"
    SPINE = "spine"
    SUPER_SPINE = "superSpine"
    TIER2_LEAF = "tier2Leaf"
    TOR = "tor"
    ACCESS = "access"
    AGGREGATION = "aggregation"
    CORE_ROUTER = "coreRouter"
    EDGE_ROUTER = "edgeRouter"
    META = "meta"  # read-only
    NEIGHBOR = "neighbor"
    
    @classmethod
    def choices(cls) -> List[str]:
        """Return list of valid choices."""
        return [e.value for e in cls]
    
    @classmethod
    def from_user_input(cls, value: str) -> "SwitchRole":
        """
        Convert user-friendly input to enum value.
        Accepts underscore-separated values like 'border_gateway' -> 'borderGateway'
        """
        if not value:
            return cls.LEAF
        # Try direct match first
        try:
            return cls(value)
        except ValueError:
            pass
        # Try converting underscore to camelCase
        parts = value.lower().split('_')
        camel_case = parts[0] + ''.join(word.capitalize() for word in parts[1:])
        try:
            return cls(camel_case)
        except ValueError:
            raise ValueError(f"Invalid switch role: {value}. Valid options: {cls.choices()}")

    @classmethod
    def normalize(cls, value: Union[str, "SwitchRole", None]) -> "SwitchRole":
        """
        Normalize input to enum value (case-insensitive).
        Accepts: LEAF, leaf, border_gateway, borderGateway, etc.
        """
        if value is None:
            return cls.LEAF
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            v_lower = value.lower()
            # Try direct match with lowercase
            for role in cls:
                if role.value.lower() == v_lower:
                    return role
            # Try converting underscore to camelCase
            parts = v_lower.split('_')
            if len(parts) > 1:
                camel_case = parts[0] + ''.join(word.capitalize() for word in parts[1:])
                for role in cls:
                    if role.value == camel_case:
                        return role
        raise ValueError(f"Invalid SwitchRole: {value}. Valid: {cls.choices()}")


class SystemMode(str, Enum):
    """
    System mode enumeration.
    
    Based on: components/schemas/systemMode
    """
    NORMAL = "normal"
    MAINTENANCE = "maintenance"
    MIGRATION = "migration"
    INCONSISTENT = "inconsistent"
    WAITING = "waiting"
    NOT_APPLICABLE = "notApplicable"
    
    @classmethod
    def choices(cls) -> List[str]:
        return [e.value for e in cls]


class PlatformType(str, Enum):
    """
    Switch platform type enumeration.
    
    Based on: components/schemas (multiple references)
    """
    NX_OS = "nx-os"
    OTHER = "other"
    IOS_XE = "ios-xe"
    IOS_XR = "ios-xr"
    SONIC = "sonic"
    APIC = "apic"
    
    @classmethod
    def choices(cls) -> List[str]:
        return [e.value for e in cls]

    @classmethod
    def normalize(cls, value: Union[str, "PlatformType", None]) -> "PlatformType":
        """
        Normalize input to enum value (case-insensitive).
        Accepts: NX_OS, nx-os, NX-OS, ios_xe, ios-xe, etc.
        """
        if value is None:
            return cls.NX_OS
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            v_normalized = value.lower().replace('_', '-')
            for pt in cls:
                if pt.value == v_normalized:
                    return pt
        raise ValueError(f"Invalid PlatformType: {value}. Valid: {cls.choices()}")


class Platform(str, Enum):
    """
    Image platform enumeration.
    
    Based on: components/schemas/platform
    """
    N3K = "n3k"
    N5K = "n5k"
    N6K = "n6k"
    N7K = "n7k"
    N77 = "n77"
    N9K = "n9k"
    CAT9K_LITE = "cat9kLite"
    CAT9K = "cat9k"
    CAT8K = "cat8k"
    MDS = "mds"
    THIRD_PARTY = "thirdParty"
    
    @classmethod
    def choices(cls) -> List[str]:
        return [e.value for e in cls]


class SnmpV3AuthProtocol(str, Enum):
    """
    SNMPv3 authentication protocols.
    
    Based on: components/schemas/snmpV3AuthProtocol and schemas-snmpV3AuthProtocol
    """
    MD5 = "md5"
    SHA = "sha"
    MD5_DES = "md5-des"
    MD5_AES = "md5-aes"
    SHA_AES = "sha-aes"
    SHA_DES = "sha-des"
    SHA_AES_256 = "sha-aes-256"
    SHA_224 = "sha-224"
    SHA_224_AES = "sha-224-aes"
    SHA_224_AES_256 = "sha-224-aes-256"
    SHA_256 = "sha-256"
    SHA_256_AES = "sha-256-aes"
    SHA_256_AES_256 = "sha-256-aes-256"
    SHA_384 = "sha-384"
    SHA_384_AES = "sha-384-aes"
    SHA_384_AES_256 = "sha-384-aes-256"
    SHA_512 = "sha-512"
    SHA_512_AES = "sha-512-aes"
    SHA_512_AES_256 = "sha-512-aes-256"
    
    @classmethod
    def choices(cls) -> List[str]:
        return [e.value for e in cls]

    @classmethod
    def normalize(cls, value: Union[str, "SnmpV3AuthProtocol", None]) -> "SnmpV3AuthProtocol":
        """
        Normalize input to enum value (case-insensitive).
        Accepts: MD5, md5, MD5_DES, md5-des, etc.
        """
        if value is None:
            return cls.MD5
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            v_normalized = value.lower().replace('_', '-')
            for proto in cls:
                if proto.value == v_normalized:
                    return proto
        raise ValueError(f"Invalid SnmpV3AuthProtocol: {value}. Valid: {cls.choices()}")


class DiscoveryStatus(str, Enum):
    """
    Switch discovery status.
    
    Based on: components/schemas/additionalSwitchData.discoveryStatus
    """
    OK = "ok"
    DISCOVERING = "discovering"
    REDISCOVERING = "rediscovering"
    DEVICE_SHUTTING_DOWN = "deviceShuttingDown"
    UNREACHABLE = "unreachable"
    IP_ADDRESS_CHANGE = "ipAddressChange"
    DISCOVERY_TIMEOUT = "discoveryTimeout"
    RETRYING = "retrying"
    SSH_SESSION_ERROR = "sshSessionError"
    TIMEOUT = "timeout"
    UNKNOWN_USER_PASSWORD = "unknownUserPassword"
    CONNECTION_ERROR = "connectionError"
    NOT_APPLICABLE = "notApplicable"
    
    @classmethod
    def choices(cls) -> List[str]:
        return [e.value for e in cls]


class ShallowDiscoveryStatus(str, Enum):
    """
    Shallow discovery status for switches.
    
    Based on: components/schemas/switchShallowDiscoveredData.status
    """
    NOT_REACHABLE = "notReacheable"  # Note: typo in API spec
    NOT_AUTHORIZED = "notAuthorized"
    NOT_MANAGEABLE = "notManageable"
    MANAGEABLE = "manageable"
    ALREADY_MANAGED = "alreadyManaged"
    
    @classmethod
    def choices(cls) -> List[str]:
        return [e.value for e in cls]


class ConfigSyncStatus(str, Enum):
    """
    Configuration sync status.
    
    Based on: components/schemas/switchConfigSyncStatus
    """
    DEPLOYED = "deployed"
    DEPLOYMENT_IN_PROGRESS = "deploymentInProgress"
    FAILED = "failed"
    IN_PROGRESS = "inProgress"
    IN_SYNC = "inSync"
    NOT_APPLICABLE = "notApplicable"
    OUT_OF_SYNC = "outOfSync"
    PENDING = "pending"
    PREVIEW_IN_PROGRESS = "previewInProgress"
    SUCCESS = "success"
    
    @classmethod
    def choices(cls) -> List[str]:
        return [e.value for e in cls]


class ComplianceStatus(str, Enum):
    """
    Compliance status.
    
    Based on: components/schemas/complianceStatus
    """
    IN_SYNC = "inSync"
    OUT_OF_SYNC = "outOfSync"
    NOT_APPLICABLE = "notApplicable"
    
    @classmethod
    def choices(cls) -> List[str]:
        return [e.value for e in cls]


class VpcRole(str, Enum):
    """
    VPC role enumeration.
    
    Based on: components/schemas/schemas-vpcRole
    """
    PRIMARY = "primary"
    SECONDARY = "secondary"
    OPERATIONAL_PRIMARY = "operationalPrimary"
    OPERATIONAL_SECONDARY = "operationalSecondary"
    NONE_ESTABLISHED = "noneEstablished"
    
    @classmethod
    def choices(cls) -> List[str]:
        return [e.value for e in cls]


class RemoteCredentialStore(str, Enum):
    """
    Remote credential store type.
    
    Based on: components/schemas/remoteCredentialStore
    """
    LOCAL = "local"
    CYBERARK = "cyberark"
    
    @classmethod
    def choices(cls) -> List[str]:
        return [e.value for e in cls]


class AnomalyLevel(str, Enum):
    """
    Anomaly level classification.
    """
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    WARNING = "warning"
    INFO = "info"
    
    @classmethod
    def choices(cls) -> List[str]:
        return [e.value for e in cls]


class AdvisoryLevel(str, Enum):
    """
    Advisory level classification.
    """
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    NONE = "none"
    
    @classmethod
    def choices(cls) -> List[str]:
        return [e.value for e in cls]


# =============================================================================
# VALIDATOR MIXIN
# =============================================================================

class SwitchValidators:
    """
    Common validators for switch-related fields.
    """
    
    @staticmethod
    def validate_ip_address(v: Optional[str]) -> Optional[str]:
        """Validate IPv4 or IPv6 address."""
        if v is None:
            return None
        v = str(v).strip()
        if not v:
            return None
        try:
            ip_address(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid IP address format: {v}")
    
    @staticmethod
    def validate_cidr(v: Optional[str]) -> Optional[str]:
        """Validate CIDR notation (IP/mask)."""
        if v is None:
            return None
        v = str(v).strip()
        if not v:
            return None
        if '/' not in v:
            raise ValueError(f"CIDR notation required (IP/mask format): {v}")
        try:
            ip_network(v, strict=False)
            return v
        except ValueError:
            raise ValueError(f"Invalid CIDR format: {v}")
    
    @staticmethod
    def validate_serial_number(v: Optional[str]) -> Optional[str]:
        """Validate switch serial number format."""
        if v is None:
            return None
        v = str(v).strip()
        if not v:
            return None
        # Serial numbers are typically alphanumeric with optional hyphens
        if not re.match(r'^[A-Za-z0-9_-]+$', v):
            raise ValueError(
                f"Serial number must be alphanumeric with optional hyphens/underscores: {v}"
            )
        return v
    
    @staticmethod
    def validate_hostname(v: Optional[str]) -> Optional[str]:
        """Validate hostname format."""
        if v is None:
            return None
        v = str(v).strip()
        if not v:
            return None
        # RFC 1123 hostname validation
        if len(v) > 255:
            raise ValueError("Hostname cannot exceed 255 characters")
        # Allow alphanumeric, dots, hyphens, underscores
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$', v):
            raise ValueError(
                f"Invalid hostname format. Must start with alphanumeric and "
                f"contain only alphanumeric, dots, hyphens, underscores: {v}"
            )
        if v.startswith('.') or v.endswith('.') or '..' in v:
            raise ValueError(f"Invalid hostname format (dots): {v}")
        return v
    
    @staticmethod
    def validate_mac_address(v: Optional[str]) -> Optional[str]:
        """Validate MAC address format."""
        if v is None:
            return None
        v = str(v).strip()
        if not v:
            return None
        # Accept colon or hyphen separated MAC addresses
        mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        if not re.match(mac_pattern, v):
            raise ValueError(f"Invalid MAC address format: {v}")
        return v
    
    @staticmethod
    def validate_vpc_domain(v: Optional[int]) -> Optional[int]:
        """Validate VPC domain ID (1-1000)."""
        if v is None:
            return None
        if not 1 <= v <= 1000:
            raise ValueError(f"VPC domain must be between 1 and 1000: {v}")
        return v


# =============================================================================
# NESTED MODELS - Sub-objects used in main models
# =============================================================================

class TelemetryIpCollection(NDNestedModel):
    """
    Telemetry IP collection for switch.
    """
    identifiers: ClassVar[List[str]] = []
    inband_ipv4_address: Optional[str] = Field(
        default=None,
        alias="inbandIpV4Address",
        description="Inband IPv4 address"
    )
    inband_ipv6_address: Optional[str] = Field(
        default=None,
        alias="inbandIpV6Address",
        description="Inband IPv6 address"
    )
    out_of_band_ipv4_address: Optional[str] = Field(
        default=None,
        alias="outOfBandIpV4Address",
        description="Out of band IPv4 address"
    )
    out_of_band_ipv6_address: Optional[str] = Field(
        default=None,
        alias="outOfBandIpV6Address",
        description="Out of band IPv6 address"
    )
    
    @field_validator('inband_ipv4_address', 'out_of_band_ipv4_address', mode='before')
    @classmethod
    def validate_ipv4(cls, v: Optional[str]) -> Optional[str]:
        return SwitchValidators.validate_ip_address(v)


class VpcData(NDNestedModel):
    """
    VPC pair information.
    
    Based on: components/schemas/vpcData
    """
    identifiers: ClassVar[List[str]] = []
    vpc_domain: int = Field(
        ...,
        alias="vpcDomain",
        ge=1,
        le=1000,
        description="vPC domain ID"
    )
    peer_switch_id: str = Field(
        ...,
        alias="peerSwitchId",
        description="vPC peer switch serial number"
    )
    consistent_status: Optional[bool] = Field(
        default=None,
        alias="consistentStatus",
        description="Flag to indicate the vPC status is consistent"
    )
    intended_peer_name: Optional[str] = Field(
        default=None,
        alias="intendedPeerName",
        description="Intended vPC host name for pre-provisioned peer switch"
    )
    keep_alive_status: Optional[str] = Field(
        default=None,
        alias="keepAliveStatus",
        description="vPC peer keep alive status"
    )
    peer_link_status: Optional[str] = Field(
        default=None,
        alias="peerLinkStatus",
        description="vPC peer link status"
    )
    peer_name: Optional[str] = Field(
        default=None,
        alias="peerName",
        description="vPC peer switch name"
    )
    vpc_role: Optional[VpcRole] = Field(
        default=None,
        alias="vpcRole",
        description="The vPC role"
    )
    
    @field_validator('peer_switch_id', mode='before')
    @classmethod
    def validate_peer_serial(cls, v: str) -> str:
        result = SwitchValidators.validate_serial_number(v)
        if result is None:
            raise ValueError("peer_switch_id cannot be empty")
        return result


class SwitchMetadata(NDNestedModel):
    """
    Metadata for associated switch.
    
    Based on: components/schemas/switchMetaData
    """
    identifiers: ClassVar[List[str]] = []
    switch_db_id: Optional[int] = Field(
        default=None,
        alias="switchDbId",
        description="Database Id of the switch"
    )
    switch_uuid: Optional[str] = Field(
        default=None,
        alias="switchUuid",
        description="Internal unique Id of the switch"
    )


class AdditionalSwitchData(NDNestedModel):
    """
    Additional switch data for non-ACI switches.
    
    Based on: components/schemas/additionalSwitchData
    """
    identifiers: ClassVar[List[str]] = []
    usage: Literal["others"] = Field(
        default="others",
        description="The usage of additional data"
    )
    config_sync_status: Optional[ConfigSyncStatus] = Field(
        default=None,
        alias="configSyncStatus",
        description="Configuration sync status"
    )
    discovery_status: Optional[DiscoveryStatus] = Field(
        default=None,
        alias="discoveryStatus",
        description="Discovery status"
    )
    domain_name: Optional[str] = Field(
        default=None,
        alias="domainName",
        description="Domain name"
    )
    smart_switch: Optional[bool] = Field(
        default=None,
        alias="smartSwitch",
        description="Flag that indicates if the switch is equipped with DPUs or not"
    )
    hypershield_connectivity_status: Optional[str] = Field(
        default=None,
        alias="hypershieldConnectivityStatus",
        description="Smart switch connectivity status to hypershield controller"
    )
    hypershield_tenant: Optional[str] = Field(
        default=None,
        alias="hypershieldTenant",
        description="Hypershield tenant name"
    )
    hypershield_integration_name: Optional[str] = Field(
        default=None,
        alias="hypershieldIntegrationName",
        description="Hypershield Integration Id"
    )
    source_interface_name: Optional[str] = Field(
        default=None,
        alias="sourceInterfaceName",
        description="Source interface for switch discovery"
    )
    source_vrf_name: Optional[str] = Field(
        default=None,
        alias="sourceVrfName",
        description="Source VRF for switch discovery"
    )
    platform_type: Optional[PlatformType] = Field(
        default=None,
        alias="platformType",
        description="Platform type of the switch"
    )
    discovered_system_mode: Optional[SystemMode] = Field(
        default=None,
        alias="discoveredSystemMode",
        description="Discovered system mode"
    )
    intended_system_mode: Optional[SystemMode] = Field(
        default=None,
        alias="intendedSystemMode",
        description="Intended system mode"
    )
    scalable_unit: Optional[str] = Field(
        default=None,
        alias="scalableUnit",
        description="Name of the scalable unit"
    )
    system_mode: Optional[SystemMode] = Field(
        default=None,
        alias="systemMode",
        description="System mode"
    )
    vendor: Optional[str] = Field(
        default=None,
        description="Vendor of the switch"
    )
    username: Optional[str] = Field(
        default=None,
        description="Discovery user name"
    )
    remote_credential_store: Optional[RemoteCredentialStore] = Field(
        default=None,
        alias="remoteCredentialStore"
    )
    meta: Optional[SwitchMetadata] = Field(
        default=None,
        description="Switch metadata"
    )


class AdditionalAciSwitchData(NDNestedModel):
    """
    Additional ACI switch data.
    
    Based on: components/schemas/additionalAciSwitchData
    """
    identifiers: ClassVar[List[str]] = []
    usage: Literal["aci"] = Field(
        default="aci",
        description="The usage of additional data"
    )
    admin_status: Optional[Literal["inService", "outOfService"]] = Field(
        default=None,
        alias="adminStatus",
        description="Admin status"
    )
    health_score: Optional[int] = Field(
        default=None,
        alias="healthScore",
        ge=1,
        le=100,
        description="Switch health score"
    )
    last_reload_time: Optional[str] = Field(
        default=None,
        alias="lastReloadTime",
        description="Timestamp when the system is last reloaded"
    )
    last_software_update_time: Optional[str] = Field(
        default=None,
        alias="lastSoftwareUpdateTime",
        description="Timestamp when the software is last updated"
    )
    node_id: Optional[int] = Field(
        default=None,
        alias="nodeId",
        ge=1,
        description="Node ID"
    )
    node_status: Optional[Literal["active", "inActive"]] = Field(
        default=None,
        alias="nodeStatus",
        description="Node status"
    )
    pod_id: Optional[int] = Field(
        default=None,
        alias="podId",
        ge=1,
        description="Pod ID"
    )
    remote_leaf_group_name: Optional[str] = Field(
        default=None,
        alias="remoteLeafGroupName",
        description="Remote leaf group name"
    )
    switch_added: Optional[str] = Field(
        default=None,
        alias="switchAdded",
        description="Timestamp when the switch is added"
    )
    tep_pool: Optional[str] = Field(
        default=None,
        alias="tepPool",
        description="TEP IP pool"
    )


class Metadata(NDNestedModel):
    """
    API response metadata with counts.
    """
    identifiers: ClassVar[List[str]] = []
    
    counts: Optional[Dict[str, int]] = Field(
        default=None,
        description="Count information including total and remaining"
    )


# =============================================================================
# DISCOVERY MODELS
# =============================================================================

class ShallowDiscoveryRequestModel(NDNestedModel):
    """
    Request body for shallow discovery.
    
    Based on: components/schemas/shallowDiscoverRequestBody
    Path: POST /fabrics/{fabricName}/actions/shallowDiscovery
    """
    identifiers: ClassVar[List[str]] = []
    exclude_from_diff: ClassVar[List[str]] = ["password"]
    seed_ip_collection: List[str] = Field(
        ...,
        alias="seedIpCollection",
        min_length=1,
        description="Seed switch IP collection"
    )
    max_hop: int = Field(
        default=2,
        alias="maxHop",
        ge=0,
        le=7,
        description="Max hop"
    )
    platform_type: PlatformType = Field(
        default=PlatformType.NX_OS,
        alias="platformType",
        description="Switch platform type"
    )
    snmp_v3_auth_protocol: SnmpV3AuthProtocol = Field(
        default=SnmpV3AuthProtocol.MD5,
        alias="snmpV3AuthProtocol",
        description="SNMPv3 authentication protocols"
    )
    username: Optional[str] = Field(
        default=None,
        description="User name for switch login"
    )
    password: Optional[str] = Field(
        default=None,
        description="User password for switch login"
    )
    remote_credential_store: Optional[RemoteCredentialStore] = Field(
        default=None,
        alias="remoteCredentialStore",
        description="Type of credential store"
    )
    remote_credential_store_key: Optional[str] = Field(
        default=None,
        alias="remoteCredentialStoreKey",
        description="Remote credential store key"
    )
    
    @field_validator('seed_ip_collection', mode='before')
    @classmethod
    def validate_seed_ips(cls, v: List[str]) -> List[str]:
        """Validate all seed IPs."""
        if not v:
            raise ValueError("At least one seed IP is required")
        validated = []
        for ip in v:
            result = SwitchValidators.validate_ip_address(ip)
            if result:
                validated.append(result)
        if not validated:
            raise ValueError("No valid seed IPs provided")
        return validated

    @field_validator('snmp_v3_auth_protocol', mode='before')
    @classmethod
    def normalize_snmp_auth(cls, v: Union[str, SnmpV3AuthProtocol, None]) -> SnmpV3AuthProtocol:
        """Normalize SNMP auth protocol (case-insensitive)."""
        return SnmpV3AuthProtocol.normalize(v)

    @field_validator('platform_type', mode='before')
    @classmethod
    def normalize_platform(cls, v: Union[str, PlatformType, None]) -> PlatformType:
        """Normalize platform type (case-insensitive)."""
        return PlatformType.normalize(v)
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert to API payload format."""
        return self.model_dump(by_alias=True, exclude_none=True)


class SwitchShallowDiscoveredData(NDBaseModel):
    """
    Result for each switch discovered by shallow discovery.
    
    Based on: components/schemas/switchShallowDiscoveredData
    """
    identifiers: ClassVar[List[str]] = ["serial_number"]
    identifier_strategy: ClassVar[Literal["single", "composite", "hierarchical"]] = "single"
    serial_number: str = Field(
        ...,
        alias="serialNumber",
        description="Serial number of switch or APIC controller node"
    )
    hostname: Optional[str] = Field(
        default=None,
        description="Switch host name"
    )
    ip: Optional[str] = Field(
        default=None,
        description="Switch IPv4/v6 address"
    )
    model: Optional[str] = Field(
        default=None,
        description="Model of switch or APIC controller node"
    )
    software_version: Optional[str] = Field(
        default=None,
        alias="softwareVersion",
        description="Software version of switch or APIC controller node"
    )
    status: Optional[ShallowDiscoveryStatus] = Field(
        default=None,
        description="Switch status"
    )
    status_reason: Optional[str] = Field(
        default=None,
        alias="statusReason",
        description="Switch status reason"
    )
    vdc_id: Optional[int] = Field(
        default=None,
        alias="vdcId",
        description="N7K VDC ID. Mandatory for N7K switch discovery"
    )
    vdc_mac: Optional[str] = Field(
        default=None,
        alias="vdcMac",
        description="N7K VDC Mac address. Mandatory for N7K switch discovery"
    )
    
    @field_validator('serial_number', mode='before')
    @classmethod
    def validate_serial(cls, v: str) -> str:
        result = SwitchValidators.validate_serial_number(v)
        if result is None:
            raise ValueError("serial_number cannot be empty")
        return result
    
    @field_validator('ip', mode='before')
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        return SwitchValidators.validate_ip_address(v)
    
    @field_validator('hostname', mode='before')
    @classmethod
    def validate_host(cls, v: Optional[str]) -> Optional[str]:
        return SwitchValidators.validate_hostname(v)
    
    @field_validator('vdc_mac', mode='before')
    @classmethod
    def validate_mac(cls, v: Optional[str]) -> Optional[str]:
        return SwitchValidators.validate_mac_address(v)
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert to API payload format."""
        return self.model_dump(by_alias=True, exclude_none=True)
    
    @classmethod
    def from_response(cls, response: Dict[str, Any]) -> Self:
        """Create model instance from API response."""
        return cls.model_validate(response)


class ShallowDiscoveryResponseModel(NDNestedModel):
    """
    Response body for shallow discovery.
    
    Based on: components/schemas/shallowDiscoverResponseBody
    """
    identifiers: ClassVar[List[str]] = []
    switches: List[SwitchShallowDiscoveredData] = Field(
        default_factory=list,
        description="Switch shallow discovery info"
    )
    warning: Optional[str] = Field(
        default=None,
        description="Warning message if any"
    )


# =============================================================================
# SWITCH DISCOVERY MODEL (for adding switches)
# =============================================================================

class SwitchDiscoveryModel(NDBaseModel):
    """
    Switch discovery data for adding to fabric.
    
    Based on: components/schemas/switchDiscovery
    Note: For N7K user VDC, the serial number will be serialNumber:vDCName
    """
    identifiers: ClassVar[List[str]] = ["serial_number"]
    identifier_strategy: ClassVar[Literal["single", "composite", "hierarchical"]] = "single"
    hostname: str = Field(
        ...,
        description="Switch host name"
    )
    ip: str = Field(
        ...,
        description="Switch IPv4/v6 address"
    )
    serial_number: str = Field(
        ...,
        alias="serialNumber",
        description="Switch serial number"
    )
    model: str = Field(
        ...,
        description="Switch model"
    )
    software_version: Optional[str] = Field(
        default=None,
        alias="softwareVersion",
        description="Switch software version"
    )
    vdc_id: Optional[int] = Field(
        default=None,
        alias="vdcId",
        ge=0,
        description="N7K VDC ID. Mandatory for N7K switch discovery"
    )
    vdc_mac: Optional[str] = Field(
        default=None,
        alias="vdcMac",
        description="N7K VDC Mac address. Mandatory for N7K switch discovery"
    )
    switch_role: Optional[SwitchRole] = Field(
        default=None,
        alias="switchRole",
        description="Switch role"
    )
    
    @field_validator('hostname', mode='before')
    @classmethod
    def validate_host(cls, v: str) -> str:
        result = SwitchValidators.validate_hostname(v)
        if result is None:
            raise ValueError("hostname cannot be empty")
        return result
    
    @field_validator('ip', mode='before')
    @classmethod
    def validate_ip(cls, v: str) -> str:
        result = SwitchValidators.validate_ip_address(v)
        if result is None:
            raise ValueError("ip cannot be empty")
        return result
    
    @field_validator('serial_number', mode='before')
    @classmethod
    def validate_serial(cls, v: str) -> str:
        result = SwitchValidators.validate_serial_number(v)
        if result is None:
            raise ValueError("serial_number cannot be empty")
        return result
    
    @field_validator('vdc_mac', mode='before')
    @classmethod
    def validate_mac(cls, v: Optional[str]) -> Optional[str]:
        return SwitchValidators.validate_mac_address(v)
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert to API payload format."""
        return self.model_dump(by_alias=True, exclude_none=True)
    
    @classmethod
    def from_response(cls, response: Dict[str, Any]) -> Self:
        """Create model instance from API response."""
        return cls.model_validate(response)


class AddSwitchesRequestModel(NDNestedModel):
    """
    Request body for add switch API.
    
    Based on: components/schemas/addSwitchesRequestBody
    Path: POST /fabrics/{fabricName}/switches
    """
    identifiers: ClassVar[List[str]] = []
    exclude_from_diff: ClassVar[List[str]] = ["password"]
    switches: List[SwitchDiscoveryModel] = Field(
        ...,
        min_length=1,
        description="The list of switches to be imported"
    )
    platform_type: PlatformType = Field(
        default=PlatformType.NX_OS,
        alias="platformType",
        description="Switch platform type"
    )
    preserve_config: bool = Field(
        default=True,
        alias="preserveConfig",
        description="Flag to preserve the switch configuration after import"
    )
    snmp_v3_auth_protocol: SnmpV3AuthProtocol = Field(
        default=SnmpV3AuthProtocol.MD5,
        alias="snmpV3AuthProtocol",
        description="SNMPv3 authentication protocols"
    )
    use_credential_for_write: Optional[bool] = Field(
        default=None,
        alias="useCredentialForWrite",
        description="Flag to use the discovery credential as LAN credential"
    )
    username: Optional[str] = Field(
        default=None,
        description="User name for switch login"
    )
    password: Optional[str] = Field(
        default=None,
        description="User password for switch login"
    )
    remote_credential_store: Optional[RemoteCredentialStore] = Field(
        default=None,
        alias="remoteCredentialStore",
        description="Type of credential store"
    )
    remote_credential_store_key: Optional[str] = Field(
        default=None,
        alias="remoteCredentialStoreKey",
        description="Remote credential store key"
    )
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert to API payload format."""
        payload = self.model_dump(by_alias=True, exclude_none=True)
        # Convert nested switches to payload format
        if 'switches' in payload:
            payload['switches'] = [
                s.to_payload() if hasattr(s, 'to_payload') else s
                for s in self.switches
            ]
        return payload

    @field_validator('snmp_v3_auth_protocol', mode='before')
    @classmethod
    def normalize_snmp_auth(cls, v: Union[str, SnmpV3AuthProtocol, None]) -> SnmpV3AuthProtocol:
        """Normalize SNMP auth protocol (case-insensitive: MD5, md5, etc.)."""
        return SnmpV3AuthProtocol.normalize(v)

    @field_validator('platform_type', mode='before')
    @classmethod
    def normalize_platform_type(cls, v: Union[str, PlatformType, None]) -> PlatformType:
        """Normalize platform type (case-insensitive: NX_OS, nx-os, etc.)."""
        return PlatformType.normalize(v)


# =============================================================================
# SWITCH DATA MODEL (Response)
# =============================================================================

class SwitchDataModel(NDBaseModel):
    """
    Each switch record for the inventory switches.
    
    Based on: components/schemas/switchData
    """
    identifiers: ClassVar[List[str]] = ["switch_id"]
    identifier_strategy: ClassVar[Literal["single", "composite", "hierarchical"]] = "single"
    switch_id: str = Field(
        ...,
        alias="switchId",
        description="Serial number of Switch or Node Id of ACI switch"
    )
    serial_number: Optional[str] = Field(
        default=None,
        alias="serialNumber",
        description="Serial number of switch or APIC controller node"
    )
    additional_data: Optional[Union[AdditionalSwitchData, AdditionalAciSwitchData]] = Field(
        default=None,
        alias="additionalData",
        description="Additional switch data"
    )
    advisory_level: Optional[AdvisoryLevel] = Field(
        default=None,
        alias="advisoryLevel"
    )
    anomaly_level: Optional[AnomalyLevel] = Field(
        default=None,
        alias="anomalyLevel"
    )
    alert_suspend: Optional[str] = Field(
        default=None,
        alias="alertSuspend"
    )
    fabric_management_ip: Optional[str] = Field(
        default=None,
        alias="fabricManagementIp",
        description="Switch IPv4/v6 address used for management"
    )
    fabric_name: Optional[str] = Field(
        default=None,
        alias="fabricName",
        description="Fabric name",
        max_length=64
    )
    fabric_type: Optional[str] = Field(
        default=None,
        alias="fabricType",
        description="Fabric type"
    )
    hostname: Optional[str] = Field(
        default=None,
        description="Switch host name"
    )
    model: Optional[str] = Field(
        default=None,
        description="Model of switch or APIC controller node"
    )
    software_version: Optional[str] = Field(
        default=None,
        alias="softwareVersion",
        description="Software version of switch or APIC controller node"
    )
    switch_role: Optional[SwitchRole] = Field(
        default=None,
        alias="switchRole"
    )
    mode: Optional[str] = Field(
        default=None,
        description="Switch mode (Normal, Migration, etc.)"
    )
    system_up_time: Optional[str] = Field(
        default=None,
        alias="systemUpTime",
        description="System up time"
    )
    vpc_configured: Optional[bool] = Field(
        default=None,
        alias="vpcConfigured",
        description="Flag to indicate switch is part of a vPC domain"
    )
    vpc_data: Optional[VpcData] = Field(
        default=None,
        alias="vpcData"
    )
    telemetry_ip_collection: Optional[TelemetryIpCollection] = Field(
        default=None,
        alias="telemetryIpCollection"
    )
    
    @field_validator('switch_id', mode='before')
    @classmethod
    def validate_switch_id(cls, v: str) -> str:
        result = SwitchValidators.validate_serial_number(v)
        if result is None:
            raise ValueError("switch_id cannot be empty")
        return result
    
    @field_validator('fabric_management_ip', mode='before')
    @classmethod
    def validate_mgmt_ip(cls, v: Optional[str]) -> Optional[str]:
        return SwitchValidators.validate_ip_address(v)
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert to API payload format."""
        return self.model_dump(by_alias=True, exclude_none=True)
    
    @classmethod
    def from_response(cls, response: Dict[str, Any]) -> Self:
        """
        Create model instance from API response.
        
        Handles two response formats:
        1. Inventory API format: {switchId, fabricManagementIp, switchRole, ...}
        2. Discovery API format: {serialNumber, ip, hostname, model, softwareVersion, status, ...}
        
        Args:
            response: Response dict from either inventory or discovery API
            
        Returns:
            SwitchDataModel instance
        """
        # Detect format and transform if needed
        if "switchId" in response or "fabricManagementIp" in response:
            # Already in inventory format - use as-is
            return cls.model_validate(response)
        
        # Discovery format - transform to inventory format
        transformed = {
            "switchId": response.get("serialNumber"),
            "serialNumber": response.get("serialNumber"),
            "fabricManagementIp": response.get("ip"),
            "hostname": response.get("hostname"),
            "model": response.get("model"),
            "softwareVersion": response.get("softwareVersion"),
            "mode": response.get("mode", "Normal"),
        }
        
        # Only add switchRole if present in response (avoid overwriting with None)
        if "switchRole" in response:
            transformed["switchRole"] = response["switchRole"]
        elif "role" in response:
            transformed["switchRole"] = response["role"]
        
        return cls.model_validate(transformed)


class ListAllSwitchesResponseModel(NDNestedModel):
    """
    Response body for get all switches API call.
    
    Based on: components/schemas/listAllSwitchesResponseBody
    Path: GET /fabrics/{fabricName}/switches
    """
    identifiers: ClassVar[List[str]] = []
    meta: Optional[Metadata] = Field(
        default=None,
        description="Response metadata"
    )
    switches: List[SwitchDataModel] = Field(
        default_factory=list,
        description="List of switch data"
    )


# =============================================================================
# BOOTSTRAP MODELS
# =============================================================================

class BootstrapBaseData(NDNestedModel):
    """
    Data provided by the bootstrap device.
    
    Based on: components/schemas/bootstrapBaseData
    """
    identifiers: ClassVar[List[str]] = []
    gateway_ip_mask: Optional[str] = Field(
        default=None,
        alias="gatewayIpMask",
        description="Gateway IP address with mask"
    )
    models: Optional[List[str]] = Field(
        default=None,
        description="Supported models for switch"
    )
    
    @field_validator('gateway_ip_mask', mode='before')
    @classmethod
    def validate_gateway(cls, v: Optional[str]) -> Optional[str]:
        return SwitchValidators.validate_cidr(v)


class BootstrapBaseModel(NDNestedModel):
    """
    Base properties common to all bootstrap switch components.
    
    Based on: components/schemas/bootstrapBase
    """
    identifiers: ClassVar[List[str]] = []
    gateway_ip_mask: str = Field(
        ...,
        alias="gatewayIpMask",
        description="Gateway IP address with mask"
    )
    model: str = Field(
        ...,
        description="Model of the bootstrap switch"
    )
    software_version: str = Field(
        ...,
        alias="softwareVersion",
        description="Software version of the bootstrap switch"
    )
    image_policy: Optional[str] = Field(
        default=None,
        alias="imagePolicy",
        description="Image policy associated with the switch during bootstrap"
    )
    switch_role: Optional[SwitchRole] = Field(
        default=None,
        alias="switchRole"
    )
    data: Optional[BootstrapBaseData] = Field(
        default=None,
        description="Additional bootstrap data"
    )
    
    @field_validator('gateway_ip_mask', mode='before')
    @classmethod
    def validate_gateway(cls, v: str) -> str:
        result = SwitchValidators.validate_cidr(v)
        if result is None:
            raise ValueError("gateway_ip_mask cannot be empty")
        return result


class BootstrapCredentialModel(NDNestedModel):
    """
    Credentials and related properties for switch bootstrap.
    
    Based on: components/schemas/bootstrapCredential
    """
    identifiers: ClassVar[List[str]] = []
    exclude_from_diff: ClassVar[List[str]] = ["password", "discovery_password"]
    password: str = Field(
        ...,
        description="Switch password to be set during bootstrap for admin user"
    )
    discovery_auth_protocol: SnmpV3AuthProtocol = Field(
        ...,
        alias="discoveryAuthProtocol"
    )
    use_new_credentials: bool = Field(
        default=False,
        alias="useNewCredentials",
        description="If True, use discoveryUsername and discoveryPassword"
    )
    discovery_username: Optional[str] = Field(
        default=None,
        alias="discoveryUsername",
        description="Username to be used for switch discovery post bootstrap"
    )
    discovery_password: Optional[str] = Field(
        default=None,
        alias="discoveryPassword",
        description="Password associated with the corresponding switch discovery user"
    )
    remote_credential_store: RemoteCredentialStore = Field(
        default=RemoteCredentialStore.LOCAL,
        alias="remoteCredentialStore",
        description="Type of credential store for discovery credentials"
    )
    remote_credential_store_key: Optional[str] = Field(
        default=None,
        alias="remoteCredentialStoreKey",
        description="Remote credential store key for discovery credentials"
    )
    
    @model_validator(mode='after')
    def validate_credentials(self) -> Self:
        """Validate credential configuration logic."""
        if self.use_new_credentials:
            if self.remote_credential_store == RemoteCredentialStore.CYBERARK:
                if not self.remote_credential_store_key:
                    raise ValueError(
                        "remote_credential_store_key is required when "
                        "remote_credential_store is 'cyberark'"
                    )
            elif self.remote_credential_store == RemoteCredentialStore.LOCAL:
                if not self.discovery_username or not self.discovery_password:
                    raise ValueError(
                        "discovery_username and discovery_password are required when "
                        "remote_credential_store is 'local' and use_new_credentials is True"
                    )
        return self


class BootstrapImportSpecificModel(NDNestedModel):
    """
    Bootstrap import specific properties.
    
    Based on: components/schemas/bootstrapImportSpecific
    """
    identifiers: ClassVar[List[str]] = []
    hostname: str = Field(
        ...,
        description="Hostname of the bootstrap switch"
    )
    ip: str = Field(
        ...,
        description="IP address of the bootstrap switch"
    )
    serial_number: str = Field(
        ...,
        alias="serialNumber",
        description="Serial number of the bootstrap switch"
    )
    in_inventory: bool = Field(
        ...,
        alias="inInventory",
        description="True if the bootstrap switch is in inventory"
    )
    public_key: str = Field(
        ...,
        alias="publicKey",
        description="Public Key"
    )
    finger_print: str = Field(
        ...,
        alias="fingerPrint",
        description="Fingerprint"
    )
    dhcp_bootstrap_ip: Optional[str] = Field(
        default=None,
        alias="dhcpBootstrapIp",
        description="This is used for device day-0 bring-up when using inband reachability"
    )
    seed_switch: bool = Field(
        default=False,
        alias="seedSwitch",
        description="Use as seed switch"
    )
    
    @field_validator('hostname', mode='before')
    @classmethod
    def validate_host(cls, v: str) -> str:
        result = SwitchValidators.validate_hostname(v)
        if result is None:
            raise ValueError("hostname cannot be empty")
        return result
    
    @field_validator('ip', 'dhcp_bootstrap_ip', mode='before')
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return SwitchValidators.validate_ip_address(v)
    
    @field_validator('serial_number', mode='before')
    @classmethod
    def validate_serial(cls, v: str) -> str:
        result = SwitchValidators.validate_serial_number(v)
        if result is None:
            raise ValueError("serial_number cannot be empty")
        return result


class BootstrapImportSwitchModel(NDBaseModel):
    """
    Import a bootstrap switch.
    
    Based on: components/schemas/bootstrapImportSwitch (allOf bootstrapBase + bootstrapCredential + bootstrapImportSpecific)
    Path: POST /fabrics/{fabricName}/switchActions/importBootstrap
    """
    identifiers: ClassVar[List[str]] = ["serial_number"]
    identifier_strategy: ClassVar[Literal["single", "composite", "hierarchical"]] = "single"
    exclude_from_diff: ClassVar[List[str]] = ["password", "discovery_password"]
    # From bootstrapBase
    gateway_ip_mask: str = Field(
        ...,
        alias="gatewayIpMask",
        description="Gateway IP address with mask"
    )
    model: str = Field(
        ...,
        description="Model of the bootstrap switch"
    )
    software_version: str = Field(
        ...,
        alias="softwareVersion",
        description="Software version of the bootstrap switch"
    )
    image_policy: Optional[str] = Field(
        default=None,
        alias="imagePolicy",
        description="Image policy associated with the switch during bootstrap"
    )
    switch_role: Optional[SwitchRole] = Field(
        default=None,
        alias="switchRole"
    )
    
    # From bootstrapCredential
    password: str = Field(
        ...,
        description="Switch password to be set during bootstrap for admin user"
    )
    discovery_auth_protocol: SnmpV3AuthProtocol = Field(
        ...,
        alias="discoveryAuthProtocol"
    )
    use_new_credentials: bool = Field(
        default=False,
        alias="useNewCredentials"
    )
    discovery_username: Optional[str] = Field(
        default=None,
        alias="discoveryUsername"
    )
    discovery_password: Optional[str] = Field(
        default=None,
        alias="discoveryPassword"
    )
    remote_credential_store: RemoteCredentialStore = Field(
        default=RemoteCredentialStore.LOCAL,
        alias="remoteCredentialStore"
    )
    remote_credential_store_key: Optional[str] = Field(
        default=None,
        alias="remoteCredentialStoreKey"
    )
    
    # From bootstrapImportSpecific
    hostname: str = Field(
        ...,
        description="Hostname of the bootstrap switch"
    )
    ip: str = Field(
        ...,
        description="IP address of the bootstrap switch"
    )
    serial_number: str = Field(
        ...,
        alias="serialNumber",
        description="Serial number of the bootstrap switch"
    )
    in_inventory: bool = Field(
        ...,
        alias="inInventory"
    )
    public_key: str = Field(
        ...,
        alias="publicKey"
    )
    finger_print: str = Field(
        ...,
        alias="fingerPrint"
    )
    dhcp_bootstrap_ip: Optional[str] = Field(
        default=None,
        alias="dhcpBootstrapIp"
    )
    seed_switch: bool = Field(
        default=False,
        alias="seedSwitch"
    )
    
    @field_validator('gateway_ip_mask', mode='before')
    @classmethod
    def validate_gateway(cls, v: str) -> str:
        result = SwitchValidators.validate_cidr(v)
        if result is None:
            raise ValueError("gateway_ip_mask cannot be empty")
        return result
    
    @field_validator('hostname', mode='before')
    @classmethod
    def validate_host(cls, v: str) -> str:
        result = SwitchValidators.validate_hostname(v)
        if result is None:
            raise ValueError("hostname cannot be empty")
        return result
    
    @field_validator('ip', 'dhcp_bootstrap_ip', mode='before')
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        result = SwitchValidators.validate_ip_address(v)
        if v is not None and result is None:
            raise ValueError(f"Invalid IP address: {v}")
        return result
    
    @field_validator('serial_number', mode='before')
    @classmethod
    def validate_serial(cls, v: str) -> str:
        result = SwitchValidators.validate_serial_number(v)
        if result is None:
            raise ValueError("serial_number cannot be empty")
        return result
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert to API payload format."""
        return self.model_dump(by_alias=True, exclude_none=True)
    
    @classmethod
    def from_response(cls, response: Dict[str, Any]) -> Self:
        """Create model instance from API response."""
        return cls.model_validate(response)


class ImportBootstrapSwitchesRequestModel(NDNestedModel):
    """
    A list of bootstrap switches for bootstrap API payload.
    
    Based on: components/schemas/importBootstrapSwitchesRequestBody
    """
    identifiers: ClassVar[List[str]] = []
    switches: List[BootstrapImportSwitchModel] = Field(
        ...,
        description="PowerOn Auto Provisioning switches"
    )
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert to API payload format."""
        return {
            "switches": [s.to_payload() for s in self.switches]
        }


# =============================================================================
# RMA MODELS
# =============================================================================

class RMASpecificModel(NDNestedModel):
    """
    Bootstrap RMA specific properties.
    
    Based on: components/schemas/RMASpecific
    """
    identifiers: ClassVar[List[str]] = []
    hostname: str = Field(
        ...,
        description="Hostname of the switch"
    )
    ip: str = Field(
        ...,
        description="IP address of the switch"
    )
    new_switch_id: str = Field(
        ...,
        alias="newSwitchId",
        description="SwitchId (serial number) of the switch"
    )
    public_key: str = Field(
        ...,
        alias="publicKey",
        description="Public Key"
    )
    finger_print: str = Field(
        ...,
        alias="fingerPrint",
        description="Fingerprint"
    )
    dhcp_bootstrap_ip: Optional[str] = Field(
        default=None,
        alias="dhcpBootstrapIp",
        description="This is used for device day-0 bring-up when using inband reachability"
    )
    seed_switch: bool = Field(
        default=False,
        alias="seedSwitch",
        description="Use as seed switch"
    )
    
    @field_validator('hostname', mode='before')
    @classmethod
    def validate_host(cls, v: str) -> str:
        result = SwitchValidators.validate_hostname(v)
        if result is None:
            raise ValueError("hostname cannot be empty")
        return result
    
    @field_validator('ip', 'dhcp_bootstrap_ip', mode='before')
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return SwitchValidators.validate_ip_address(v)
    
    @field_validator('new_switch_id', mode='before')
    @classmethod
    def validate_serial(cls, v: str) -> str:
        result = SwitchValidators.validate_serial_number(v)
        if result is None:
            raise ValueError("new_switch_id cannot be empty")
        return result


class RMASwitchModel(NDBaseModel):
    """
    Request body for RMA bootstrap switch.
    
    Based on: components/schemas/RMASwitch (allOf bootstrapBase + bootstrapCredential + RMASpecific)
    Path: POST /fabrics/{fabricName}/switches/{switchId}/actions/provisionRMA
    
    Notes:
    - If admin user and password is not used for discovery, then remoteCredentialStore is mandatory.
    - If remoteCredentialStore is cyberark, then remoteCredentialStoreKey is mandatory.
    - If remoteCredentialStore is local, then discoveryUsername and discoveryPassword are mandatory.
    """
    identifiers: ClassVar[List[str]] = ["new_switch_id"]
    identifier_strategy: ClassVar[Literal["single", "composite", "hierarchical"]] = "single"
    exclude_from_diff: ClassVar[List[str]] = ["password", "discovery_password"]
    # From bootstrapBase
    gateway_ip_mask: str = Field(
        ...,
        alias="gatewayIpMask",
        description="Gateway IP address with mask"
    )
    model: str = Field(
        ...,
        description="Model of the bootstrap switch"
    )
    software_version: str = Field(
        ...,
        alias="softwareVersion",
        description="Software version of the bootstrap switch"
    )
    image_policy: Optional[str] = Field(
        default=None,
        alias="imagePolicy",
        description="Image policy associated with the switch during bootstrap"
    )
    switch_role: Optional[SwitchRole] = Field(
        default=None,
        alias="switchRole"
    )
    
    # From bootstrapCredential
    password: str = Field(
        ...,
        description="Switch password to be set during bootstrap for admin user"
    )
    discovery_auth_protocol: SnmpV3AuthProtocol = Field(
        ...,
        alias="discoveryAuthProtocol"
    )
    use_new_credentials: bool = Field(
        default=False,
        alias="useNewCredentials"
    )
    discovery_username: Optional[str] = Field(
        default=None,
        alias="discoveryUsername"
    )
    discovery_password: Optional[str] = Field(
        default=None,
        alias="discoveryPassword"
    )
    remote_credential_store: RemoteCredentialStore = Field(
        default=RemoteCredentialStore.LOCAL,
        alias="remoteCredentialStore"
    )
    remote_credential_store_key: Optional[str] = Field(
        default=None,
        alias="remoteCredentialStoreKey"
    )
    
    # From RMASpecific
    hostname: str = Field(
        ...,
        description="Hostname of the switch"
    )
    ip: str = Field(
        ...,
        description="IP address of the switch"
    )
    new_switch_id: str = Field(
        ...,
        alias="newSwitchId",
        description="SwitchId (serial number) of the switch"
    )
    public_key: str = Field(
        ...,
        alias="publicKey",
        description="Public Key"
    )
    finger_print: str = Field(
        ...,
        alias="fingerPrint",
        description="Fingerprint"
    )
    dhcp_bootstrap_ip: Optional[str] = Field(
        default=None,
        alias="dhcpBootstrapIp"
    )
    seed_switch: bool = Field(
        default=False,
        alias="seedSwitch"
    )
    
    @field_validator('gateway_ip_mask', mode='before')
    @classmethod
    def validate_gateway(cls, v: str) -> str:
        result = SwitchValidators.validate_cidr(v)
        if result is None:
            raise ValueError("gateway_ip_mask cannot be empty")
        return result
    
    @field_validator('hostname', mode='before')
    @classmethod
    def validate_host(cls, v: str) -> str:
        result = SwitchValidators.validate_hostname(v)
        if result is None:
            raise ValueError("hostname cannot be empty")
        return result
    
    @field_validator('ip', 'dhcp_bootstrap_ip', mode='before')
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        result = SwitchValidators.validate_ip_address(v)
        if v is not None and result is None:
            raise ValueError(f"Invalid IP address: {v}")
        return result
    
    @field_validator('new_switch_id', mode='before')
    @classmethod
    def validate_serial(cls, v: str) -> str:
        result = SwitchValidators.validate_serial_number(v)
        if result is None:
            raise ValueError("new_switch_id cannot be empty")
        return result
    
    @model_validator(mode='after')
    def validate_rma_credentials(self) -> Self:
        """Validate RMA credential configuration logic."""
        if self.use_new_credentials:
            if self.remote_credential_store == RemoteCredentialStore.CYBERARK:
                if not self.remote_credential_store_key:
                    raise ValueError(
                        "remote_credential_store_key is required when "
                        "remote_credential_store is 'cyberark'"
                    )
            elif self.remote_credential_store == RemoteCredentialStore.LOCAL:
                if not self.discovery_username or not self.discovery_password:
                    raise ValueError(
                        "discovery_username and discovery_password are required when "
                        "remote_credential_store is 'local' and use_new_credentials is True"
                    )
        return self
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert to API payload format."""
        return self.model_dump(by_alias=True, exclude_none=True)
    
    @classmethod
    def from_response(cls, response: Dict[str, Any]) -> Self:
        """Create model instance from API response."""
        return cls.model_validate(response)


# =============================================================================
# SWITCH ACTIONS MODELS
# =============================================================================

class ChangeSwitchSerialNumberRequestModel(NDBaseModel):
    """
    Request body to change Switch serial number.
    
    Based on: components/schemas/changeSwitchSerialNumberRequestBody
    Path: POST /fabrics/{fabricName}/switches/{switchId}/actions/changeSwitchSerialNumber
    """
    identifiers: ClassVar[List[str]] = ["new_switch_id"]
    identifier_strategy: ClassVar[Literal["single", "composite", "hierarchical"]] = "single"
    new_switch_id: str = Field(
        ...,
        alias="newSwitchId",
        description="New switchId"
    )
    
    @field_validator('new_switch_id', mode='before')
    @classmethod
    def validate_serial(cls, v: str) -> str:
        result = SwitchValidators.validate_serial_number(v)
        if result is None:
            raise ValueError("new_switch_id cannot be empty")
        return result
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert to API payload format."""
        return self.model_dump(by_alias=True, exclude_none=True)
    
    @classmethod
    def from_response(cls, response: Dict[str, Any]) -> Self:
        """Create model instance from API response."""
        return cls.model_validate(response)


class SwitchIdsListModel(NDNestedModel):
    """
    List of switches for various operations.
    
    Based on: components/schemas/switchIdsList
    """
    identifiers: ClassVar[List[str]] = []
    switch_ids: List[str] = Field(
        ...,
        alias="switchIds",
        min_length=1,
        description="List of switch serial numbers"
    )
    
    @field_validator('switch_ids', mode='before')
    @classmethod
    def validate_switch_ids(cls, v: List[str]) -> List[str]:
        """Validate all switch IDs."""
        if not v:
            raise ValueError("At least one switch ID is required")
        validated = []
        for serial in v:
            result = SwitchValidators.validate_serial_number(serial)
            if result:
                validated.append(result)
        if not validated:
            raise ValueError("No valid switch IDs provided")
        return validated
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert to API payload format."""
        return self.model_dump(by_alias=True, exclude_none=True)


class SwitchCredentialsRequestModel(NDNestedModel):
    """
    Request body to save switch credentials.

    Based on: components/schemas/switchCredentialsPost (allOf credentialsBase + switchIds)
    Path: POST /api/v1/manage/credentials/switches

    Supports both local credentials (switchUsername/switchPassword) and
    remote credential store (CyberArk) configurations.

    ## Usage

    ```python
    # Local credentials
    creds = SwitchCredentialsRequestModel(
        switchIds=["SAL1948TRTT", "SAL1947TRAB"],
        switchUsername="admin",
        switchPassword="secret"
    )
    payload = creds.to_payload()
    # {"switchIds": ["SAL1948TRTT", "SAL1947TRAB"], "switchUsername": "admin", "switchPassword": "secret"}

    # CyberArk credentials
    creds = SwitchCredentialsRequestModel(
        switchIds=["SAL1948TRTT"],
        remoteCredentialStoreType="cyberark",
        remoteCredentialStoreKey="NexusDashboard/root/.../admin"
    )
    ```
    """
    identifiers: ClassVar[List[str]] = []

    switch_ids: List[str] = Field(
        ...,
        alias="switchIds",
        min_length=1,
        description="List of switch serial numbers"
    )
    switch_username: Optional[str] = Field(
        default=None,
        alias="switchUsername",
        description="Switch username"
    )
    switch_password: Optional[str] = Field(
        default=None,
        alias="switchPassword",
        description="Switch password"
    )
    remote_credential_store_key: Optional[str] = Field(
        default=None,
        alias="remoteCredentialStoreKey",
        description="Remote credential store key (e.g. CyberArk path)"
    )
    remote_credential_store_type: Optional[str] = Field(
        default=None,
        alias="remoteCredentialStoreType",
        description="Remote credential store type (e.g. 'cyberark')"
    )

    @field_validator('switch_ids', mode='before')
    @classmethod
    def validate_switch_ids(cls, v: List[str]) -> List[str]:
        """Validate all switch IDs."""
        if not v:
            raise ValueError("At least one switch ID is required")
        validated = []
        for serial in v:
            result = SwitchValidators.validate_serial_number(serial)
            if result:
                validated.append(result)
        if not validated:
            raise ValueError("No valid switch IDs provided")
        return validated

    @model_validator(mode='after')
    def validate_credentials(self) -> Self:
        """Ensure either local or remote credentials are provided."""
        has_local = self.switch_username is not None and self.switch_password is not None
        has_remote = self.remote_credential_store_key is not None and self.remote_credential_store_type is not None
        if not has_local and not has_remote:
            raise ValueError(
                "Either local credentials (switchUsername + switchPassword) "
                "or remote credentials (remoteCredentialStoreKey + remoteCredentialStoreType) must be provided"
            )
        return self

    def to_payload(self) -> Dict[str, Any]:
        """Convert to API payload format."""
        return self.model_dump(by_alias=True, exclude_none=True)


# =============================================================================
# SWITCHES SUMMARY MODEL
# =============================================================================

class CounterNameValue(NDNestedModel):
    """
    Counter name-value pair.
    """
    identifiers: ClassVar[List[str]] = []
    name: str = Field(..., description="Category name")
    count: int = Field(..., ge=0, description="Count value")


class SwitchesSummaryModel(NDNestedModel):
    """
    Counts for different categories for switches.
    
    Based on: components/schemas/switchesSummary
    Path: GET /fabrics/{fabricName}/switches/summary
    """
    identifiers: ClassVar[List[str]] = []
    anomaly_level: Optional[List[CounterNameValue]] = Field(
        default=None,
        alias="anomalyLevel"
    )
    config_sync_status: Optional[List[CounterNameValue]] = Field(
        default=None,
        alias="configSyncStatus"
    )
    role: Optional[List[CounterNameValue]] = Field(
        default=None
    )
    software_version: Optional[List[CounterNameValue]] = Field(
        default=None,
        alias="softwareVersion"
    )


# =============================================================================
# ANSIBLE PLAYBOOK CONFIG MODELS
# =============================================================================

class ConfigDataModel(NDNestedModel):
    """
    Configuration data for POAP/RMA operations.
    
    Used in Ansible playbook config for bootstrap config_data.
    
    Based on: dcnm_inventory.py config.poap.config_data and config.rma.config_data
    """
    identifiers: ClassVar[List[str]] = []
    
    modules_model: List[str] = Field(
        ...,
        alias="modulesModel",
        min_length=1,
        description="List of model of modules in switch to Bootstrap/Pre-provision/RMA"
    )
    gateway: str = Field(
        ...,
        description="Gateway IP with mask for the switch (e.g., 192.168.0.1/24)"
    )
    
    # Optional additional config data fields
    # Add other fields as needed based on NDFC/DCNM configuration guide
    
    @field_validator('gateway', mode='before')
    @classmethod
    def validate_gateway(cls, v: str) -> str:
        """Validate gateway is a valid IP address with mask."""
        if not v:
            raise ValueError("gateway cannot be empty")
        
        # Check for CIDR notation
        if '/' not in v:
            raise ValueError("gateway must include subnet mask (e.g., 192.168.0.1/24)")
        
        try:
            ip_network(v, strict=False)
        except Exception as e:
            raise ValueError(f"Invalid gateway IP address with mask: {v}") from e
        
        return v


class POAPConfigModel(NDNestedModel):
    """
    POAP (PowerOn Auto Provisioning) configuration for Ansible playbook.
    
    Supports both Bootstrap and Pre-provision operations.
    
    Based on: dcnm_inventory.py config.poap suboptions
    """
    identifiers: ClassVar[List[str]] = []
    
    # Discovery credentials
    discovery_username: Optional[str] = Field(
        default=None,
        alias="discoveryUsername",
        description="Username for device discovery during POAP"
    )
    discovery_password: Optional[str] = Field(
        default=None,
        alias="discoveryPassword",
        description="Password for device discovery during POAP"
    )
    
    # Bootstrap operation - requires actual switch serial number
    serial_number: Optional[str] = Field(
        default=None,
        alias="serialNumber",
        min_length=1,
        description="Serial number of switch to Bootstrap"
    )
    
    # Pre-provision operation - requires pre-provision serial number
    preprovision_serial: Optional[str] = Field(
        default=None,
        alias="preprovisionSerial",
        min_length=1,
        description="Serial number of switch to Pre-provision"
    )
    
    # Common fields for both operations
    model: Optional[str] = Field(
        default=None,
        description="Model of switch to Bootstrap/Pre-provision"
    )
    version: Optional[str] = Field(
        default=None,
        description="Software version of switch to Bootstrap/Pre-provision"
    )
    hostname: Optional[str] = Field(
        default=None,
        description="Hostname of switch to Bootstrap/Pre-provision"
    )
    image_policy: Optional[str] = Field(
        default=None,
        alias="imagePolicy",
        description="Name of the image policy to be applied on switch"
    )
    config_data: Optional[ConfigDataModel] = Field(
        default=None,
        alias="configData",
        description="Basic config data of switch to Bootstrap/Pre-provision"
    )
    
    @model_validator(mode='after')
    def validate_operation_type(self) -> Self:
        """Validate that either serial_number or preprovision_serial is provided."""
        if not self.serial_number and not self.preprovision_serial:
            raise ValueError(
                "Either 'serial_number' (for Bootstrap) or 'preprovision_serial' "
                "(for Pre-provision) must be provided"
            )
        
        # Both can be provided for swap operation (NDFC only)
        # No validation error if both are present
        
        return self
    
    @field_validator('serial_number', 'preprovision_serial', mode='before')
    @classmethod
    def validate_serial_numbers(cls, v: Optional[str]) -> Optional[str]:
        """Validate serial numbers are not empty strings."""
        if v is not None and not v.strip():
            raise ValueError("Serial number cannot be empty")
        return v


class RMAConfigModel(NDNestedModel):
    """
    RMA (Return Material Authorization) configuration for Ansible playbook.
    
    Used to replace an existing switch with a new one.
    
    Based on: dcnm_inventory.py config.rma suboptions
    """
    identifiers: ClassVar[List[str]] = []
    
    # Discovery credentials
    discovery_username: Optional[str] = Field(
        default=None,
        alias="discoveryUsername",
        description="Username for device discovery during RMA"
    )
    discovery_password: Optional[str] = Field(
        default=None,
        alias="discoveryPassword",
        description="Password for device discovery during RMA"
    )
    
    # Required fields for RMA
    serial_number: str = Field(
        ...,
        alias="serialNumber",
        min_length=1,
        description="Serial number of new switch to Bootstrap for RMA"
    )
    old_serial: str = Field(
        ...,
        alias="oldSerial",
        min_length=1,
        description="Serial number of switch to be replaced by RMA"
    )
    model: str = Field(
        ...,
        min_length=1,
        description="Model of new switch to Bootstrap for RMA"
    )
    version: str = Field(
        ...,
        min_length=1,
        description="Software version of new switch to Bootstrap for RMA"
    )
    
    # Optional fields
    image_policy: Optional[str] = Field(
        default=None,
        alias="imagePolicy",
        description="Name of the image policy to be applied on switch during RMA"
    )
    
    # Required config data for RMA
    config_data: ConfigDataModel = Field(
        ...,
        alias="configData",
        description="Basic config data of switch to Bootstrap for RMA (modulesModel and gateway are mandatory)"
    )
    
    @field_validator('serial_number', 'old_serial', mode='before')
    @classmethod
    def validate_serial_numbers(cls, v: str) -> str:
        """Validate serial numbers are not empty."""
        if not v or not v.strip():
            raise ValueError("Serial number cannot be empty")
        return v.strip()


class SwitchConfigModel(NDBaseModel):
    """
    Switch configuration model for Ansible playbook.
    
    Main configuration model for each switch in the config list.
    Supports normal switch addition, POAP operations, and RMA operations.
    
    Based on: dcnm_inventory.py config suboptions
    
    Usage:
        ```python
        # Normal switch
        switch_config = SwitchConfigModel(
            seed_ip="192.168.0.1",
            user_name="admin",
            password="cisco123",
            role="leaf"
        )
        
        # POAP switch
        poap_config = SwitchConfigModel(
            seed_ip="192.168.0.2",
            user_name="admin",
            password="cisco123",
            role="spine",
            poap=[{
                "serial_number": "ABC123",
                "model": "N9K-C9300v",
                "version": "9.3(7)",
                "hostname": "switch1",
                "config_data": {
                    "modulesModel": ["N9K-X9364v"],
                    "gateway": "192.168.0.1/24"
                }
            }]
        )
        
        # RMA switch
        rma_config = SwitchConfigModel(
            seed_ip="192.168.0.3",
            user_name="admin",
            password="cisco123",
            rma=[{
                "serial_number": "NEW123",
                "old_serial": "OLD123",
                "model": "N9K-C9300v",
                "version": "9.3(7)",
                "config_data": {
                    "modulesModel": ["N9K-X9364v"],
                    "gateway": "192.168.0.1/24"
                }
            }]
        )
        ```
    """
    identifiers: ClassVar[List[str]] = ["seed_ip"]
    
    # Required fields
    seed_ip: str = Field(
        ...,
        alias="seedIp",
        min_length=1,
        description="Seed IP address or DNS name of the switch"
    )
    user_name: str = Field(
        ...,
        alias="userName",
        description="Login username to the switch"
    )
    password: str = Field(
        ...,
        description="Login password to the switch"
    )
    
    # Optional fields with defaults
    auth_proto: SnmpV3AuthProtocol = Field(
        default=SnmpV3AuthProtocol.MD5,
        alias="authProto",
        description="Authentication protocol to use"
    )
    max_hops: int = Field(
        default=0,
        alias="maxHops",
        ge=0,
        le=7,
        description="Maximum hops to reach the switch (deprecated, defaults to 0)"
    )
    role: SwitchRole = Field(
        default=SwitchRole.LEAF,
        description="Role to assign to the switch"
    )
    preserve_config: bool = Field(
        default=False,
        alias="preserveConfig",
        description="Set to false for greenfield, true for brownfield deployment"
    )
    platform_type: PlatformType = Field(
        default=PlatformType.NX_OS,
        alias="platformType",
        description="Platform type of the switch (nx-os, ios-xe, etc.)"
    )
    
    # POAP and RMA configurations
    poap: Optional[List[POAPConfigModel]] = Field(
        default=None,
        description="POAP (PowerOn Auto Provisioning) configurations for Bootstrap/Pre-provision"
    )
    rma: Optional[List[RMAConfigModel]] = Field(
        default=None,
        description="RMA (Return Material Authorization) configurations for switch replacement"
    )
    
    @model_validator(mode='after')
    def validate_poap_rma_mutual_exclusion(self) -> Self:
        """Validate that POAP and RMA are mutually exclusive."""
        if self.poap and self.rma:
            raise ValueError("Cannot specify both 'poap' and 'rma' configurations for the same switch")
        
        return self
    
    @model_validator(mode='after')
    def validate_poap_rma_credentials(self) -> Self:
        """Validate credentials for POAP and RMA operations."""
        if self.poap or self.rma:
            # For POAP and RMA, username should be 'admin'
            if self.user_name != "admin":
                raise ValueError("For POAP and RMA operations, user_name should be 'admin'")
            
            # For POAP and RMA, auth_proto should be MD5
            if self.auth_proto != SnmpV3AuthProtocol.MD5:
                raise ValueError("For POAP and RMA operations, auth_proto should be 'MD5'")
        
        return self
    
    @field_validator('seed_ip', mode='before')
    @classmethod
    def validate_seed_ip(cls, v: str) -> str:
        """Validate seed IP is valid IP address or DNS name."""
        if not v or not v.strip():
            raise ValueError("seed_ip cannot be empty")
        
        v = v.strip()
        
        # Try to validate as IP address first
        try:
            ip_address(v)
            return v
        except ValueError:
            pass
        
        # If not an IP, assume it's a DNS name - basic validation
        if not v.replace('-', '').replace('.', '').replace('_', '').isalnum():
            raise ValueError(f"Invalid seed_ip: {v}. Must be a valid IP address or DNS name")
        
        return v
    
    @field_validator('poap', 'rma', mode='before')
    @classmethod
    def validate_lists_not_empty(cls, v: Optional[List]) -> Optional[List]:
        """Validate that if POAP or RMA lists are provided, they are not empty."""
        if v is not None and len(v) == 0:
            raise ValueError("POAP/RMA list cannot be empty if provided")
        return v

    @field_validator('auth_proto', mode='before')
    @classmethod
    def normalize_auth_proto(cls, v: Union[str, SnmpV3AuthProtocol, None]) -> SnmpV3AuthProtocol:
        """Normalize auth_proto to handle case-insensitive input (MD5, md5, etc.)."""
        return SnmpV3AuthProtocol.normalize(v)

    @field_validator('role', mode='before')
    @classmethod
    def normalize_role(cls, v: Union[str, SwitchRole, None]) -> SwitchRole:
        """Normalize role for case-insensitive and underscore-to-camelCase matching."""
        return SwitchRole.normalize(v)

    @field_validator('platform_type', mode='before')
    @classmethod
    def normalize_platform_type(cls, v: Union[str, PlatformType, None]) -> PlatformType:
        """Normalize platform_type for case-insensitive matching (NX_OS, nx-os, etc.)."""
        return PlatformType.normalize(v)

    def to_payload(self) -> Dict[str, Any]:
        """Convert to API payload format."""
        return self.model_dump(by_alias=True, exclude_none=True)

    @classmethod
    def from_response(cls, response: Dict[str, Any]) -> Self:
        """Create model instance from API response."""
        return cls.model_validate(response)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "SwitchRole",
    "SystemMode",
    "PlatformType",
    "Platform",
    "SnmpV3AuthProtocol",
    "DiscoveryStatus",
    "ShallowDiscoveryStatus",
    "ConfigSyncStatus",
    "ComplianceStatus",
    "VpcRole",
    "RemoteCredentialStore",
    "AnomalyLevel",
    "AdvisoryLevel",
    # Base Classes (re-exported from base.py)
    "NDBaseModel",
    "NDNestedModel",
    # Validators
    "SwitchValidators",
    # Nested Models
    "TelemetryIpCollection",
    "VpcData",
    "SwitchMetadata",
    "AdditionalSwitchData",
    "AdditionalAciSwitchData",
    "Metadata",
    # Discovery Models
    "ShallowDiscoveryRequestModel",
    "SwitchShallowDiscoveredData",
    "ShallowDiscoveryResponseModel",
    "SwitchDiscoveryModel",
    "AddSwitchesRequestModel",
    # Switch Data Models
    "SwitchDataModel",
    "ListAllSwitchesResponseModel",
    # Bootstrap Models
    "BootstrapBaseData",
    "BootstrapBaseModel",
    "BootstrapCredentialModel",
    "BootstrapImportSpecificModel",
    "BootstrapImportSwitchModel",
    "ImportBootstrapSwitchesRequestModel",
    # RMA Models
    "RMASpecificModel",
    "RMASwitchModel",
    # Switch Actions Models
    "ChangeSwitchSerialNumberRequestModel",
    "SwitchIdsListModel",
    "SwitchCredentialsRequestModel",
    # Summary Models
    "CounterNameValue",
    "SwitchesSummaryModel",
    # Ansible Playbook Config Models
    "ConfigDataModel",
    "POAPConfigModel",
    "RMAConfigModel",
    "SwitchConfigModel",
]
