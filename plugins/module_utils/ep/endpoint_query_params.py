# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Allen Robel (@arobel) <arobel@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
Endpoint-specific query parameter classes.

This module provides query parameter classes tailored for specific API
endpoints, handling their unique parameter requirements.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type  # pylint: disable=invalid-name
__author__ = "Allen Robel"

from typing import Optional

from ansible_collections.cisco.nd.plugins.module_utils.enums import BooleanStringEnum
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_mixins import (
    ClusterNameMixin,
    ForceMixin,
    ForceShowRunMixin,
    HostnameMixin,
    InclAllMsdSwitchesMixin,
    TicketIdMixin,
)
from ansible_collections.cisco.nd.plugins.module_utils.pydantic_compat import BaseModel, ConfigDict, Field

# Config for classes that use enums and need automatic value extraction
ENUM_CONFIG = ConfigDict(validate_assignment=True, use_enum_values=True)


class EndpointQueryParams(BaseModel):
    """
    # Summary

    Base class for endpoint query parameter models.

    This abstract base class provides a common interface for all endpoint-specific
    query parameter classes. Subclasses must implement the to_query_string() method
    to generate properly formatted query strings for their specific endpoints.

    ## Raises

    None
    """

    def to_query_string(self) -> str:
        """
        Build a query string from the model fields.

        Subclasses must override this method to provide endpoint-specific
        query string formatting.

        Returns an empty string by default.
        """
        return ""


class FabricConfigDeployQueryParams(EndpointQueryParams, ForceShowRunMixin, InclAllMsdSwitchesMixin):
    """
    # Summary

    Query parameters for fabric config deploy endpoints.

    ## Parameters

    - force_show_run: If true, fetch latest running config from device; if false, use cached version (default: "false")
    - incl_all_msd_switches: If true and MSD fabric, deploy all child fabric changes; if false, skip child fabrics (default: "false")

    ## Raises

    None
    """

    model_config = ENUM_CONFIG

    def to_query_string(self) -> str:
        """Build query string with forceShowRun and inclAllMSDSwitches parameters."""
        params = []
        # Always include these params - they have default values
        # Use .value to get the string value from the enum
        params.append(f"forceShowRun={self.force_show_run.value if hasattr(self.force_show_run, 'value') else self.force_show_run}")
        params.append(f"inclAllMSDSwitches={self.incl_all_msd_switches.value if hasattr(self.incl_all_msd_switches, 'value') else self.incl_all_msd_switches}")
        return "&".join(params)


class FabricConfigPreviewQueryParams(EndpointQueryParams, ForceShowRunMixin):
    """
    # Summary

    Query parameters for fabric config preview endpoints.

    ## Parameters

    - force_show_run: Force show running config (default: "false")
    - show_brief: Show brief output (default: "false")
    """

    show_brief: BooleanStringEnum = Field(default=BooleanStringEnum.FALSE, description="Show brief output")

    def to_query_string(self) -> str:
        """Build query string with forceShowRun and showBrief parameters."""
        params = []
        if self.force_show_run:
            params.append(f"forceShowRun={self.force_show_run.value if hasattr(self.force_show_run, 'value') else self.force_show_run}")
        if self.show_brief:
            params.append(f"showBrief={self.show_brief.value if hasattr(self.show_brief, 'value') else self.show_brief}")
        return "&".join(params)


class LinkByUuidQueryParams(EndpointQueryParams):
    """
    # Summary

    Query parameters for link by UUID endpoints.

    ## Parameters

    - source_cluster_name: Source cluster name (e.g., "nd-cluster-1")
    - destination_cluster_name: Destination cluster name (e.g., "nd-cluster-2")
    """

    source_cluster_name: Optional[str] = Field(default=None, min_length=1, description="Source cluster name")
    destination_cluster_name: Optional[str] = Field(default=None, min_length=1, description="Destination cluster name")

    def to_query_string(self) -> str:
        """Build query string with sourceClusterName and destinationClusterName parameters."""
        params = []
        if self.source_cluster_name:
            params.append(f"sourceClusterName={self.source_cluster_name}")
        if self.destination_cluster_name:
            params.append(f"destinationClusterName={self.destination_cluster_name}")
        return "&".join(params)


class NetworkNamesQueryParams(EndpointQueryParams):
    """
    # Summary

    Query parameters for network deletion endpoints.

    ## Parameters

    - network_names: Comma-separated list of network names to delete e.g. "Net1,Net2,Net3"
    """

    network_names: Optional[str] = Field(default=None, min_length=1, description="Comma-separated network names")

    def to_query_string(self) -> str:
        """Build query string with network-names parameter."""
        params = []
        if self.network_names:
            params.append(f"network-names={self.network_names}")
        return "&".join(params)


class VrfNamesQueryParams(EndpointQueryParams):
    """
    # Summary

    Query parameters for VRF deletion endpoints.

    ## Parameters

    - vrf_names: Comma-separated list of VRF names to delete e.g. "VRF1,VRF2,VRF3"
    """

    vrf_names: Optional[str] = Field(default=None, min_length=1, description="Comma-separated VRF names")

    def to_query_string(self) -> str:
        """Build query string with vrf-names parameter."""
        params = []
        if self.vrf_names:
            params.append(f"vrf-names={self.vrf_names}")
        return "&".join(params)


class ClusterHealthConfigQueryParams(EndpointQueryParams):
    """
    # Summary

    Query parameters for cluster health config endpoint.

    ## Parameters

    - cluster_name: Cluster name (optional)
    """

    cluster_name: Optional[str] = Field(default=None, min_length=1, description="Cluster name")

    def to_query_string(self) -> str:
        """Build query string with clusterName parameter."""
        params = []
        if self.cluster_name:
            params.append(f"clusterName={self.cluster_name}")
        return "&".join(params)


class ClusterHealthStatusQueryParams(EndpointQueryParams):
    """
    # Summary

    Query parameters for cluster health status endpoint.

    ## Parameters

    - cluster_name: Cluster name (optional)
    - health_category: Health category (optional)
    - node_name: Node name (optional)
    """

    cluster_name: Optional[str] = Field(default=None, min_length=1, description="Cluster name")
    health_category: Optional[str] = Field(default=None, min_length=1, description="Health category")
    node_name: Optional[str] = Field(default=None, min_length=1, description="Node name")

    def to_query_string(self) -> str:
        """Build query string with clusterName, healthCategory, and nodeName parameters."""
        params = []
        if self.cluster_name:
            params.append(f"clusterName={self.cluster_name}")
        if self.health_category:
            params.append(f"healthCategory={self.health_category}")
        if self.node_name:
            params.append(f"nodeName={self.node_name}")
        return "&".join(params)


# ============================================================================
# Switch and Inventory Query Parameter Classes
# ============================================================================


class LuceneQueryParams(EndpointQueryParams):
    """
    # Summary

    Base query parameters for endpoints supporting Lucene-style filtering.

    ## Parameters

    - filter: Lucene filter expression
    - max: Maximum number of results to return
    - offset: Pagination offset
    - sort: Sort field and direction (e.g., "hostname:asc")
    """

    filter: Optional[str] = Field(default=None, description="Lucene filter expression")
    max: Optional[int] = Field(default=None, ge=1, description="Maximum results to return")
    offset: Optional[int] = Field(default=None, ge=0, description="Pagination offset")
    sort: Optional[str] = Field(default=None, description="Sort field and direction")

    def to_lucene_query_string(self, url_encode: bool = False) -> str:
        """Build query string with Lucene parameters."""
        params = []
        if self.filter:
            filter_value = self.filter
            if url_encode:
                from urllib.parse import quote
                filter_value = quote(filter_value, safe="")
            params.append(f"filter={filter_value}")
        if self.max is not None:
            params.append(f"max={self.max}")
        if self.offset is not None:
            params.append(f"offset={self.offset}")
        if self.sort:
            params.append(f"sort={self.sort}")
        return "&".join(params)

    def to_query_string(self) -> str:
        """Build query string with Lucene parameters."""
        return self.to_lucene_query_string()


class ManageSwitchAddQueryParams(EndpointQueryParams, ClusterNameMixin, TicketIdMixin):
    """
    # Summary

    Query parameters for switch add endpoints.

    ## Parameters

    - cluster_name: Cluster name (default: None)
    - ticket_id: Ticket ID (default: None)
    """

    def to_query_string(self) -> str:
        """Build query string with clusterName and ticketId parameters."""
        params = []
        if self.cluster_name:
            params.append(f"clusterName={self.cluster_name}")
        if self.ticket_id:
            params.append(f"ticketId={self.ticket_id}")
        return "&".join(params)


class FabricSwitchesQueryParams(LuceneQueryParams, ClusterNameMixin, HostnameMixin):
    """
    # Summary

    Query parameters for listing switches in a fabric.

    ## Parameters

    - cluster_name: Cluster name for multi-cluster environments (default: None)
    - hostname: Filter by switch hostname (default: None)
    - filter: Lucene filter expression (inherited from LuceneQueryParams)
    - max: Maximum number of results (inherited from LuceneQueryParams)
    - offset: Pagination offset (inherited from LuceneQueryParams)
    - sort: Sort field and direction (inherited from LuceneQueryParams)

    ## Usage

    ```python
    params = FabricSwitchesQueryParams(
        hostname="leaf1",
        max=100,
        sort="hostname:asc"
    )
    ```
    """

    def to_query_string(self) -> str:
        """Build query string combining Lucene and endpoint-specific parameters."""
        params = []
        if self.cluster_name:
            params.append(f"clusterName={self.cluster_name}")
        if self.hostname:
            params.append(f"hostname={self.hostname}")

        # Add Lucene parameters
        lucene_string = self.to_lucene_query_string(url_encode=True)
        if lucene_string:
            params.append(lucene_string)

        return "&".join(params)


class SwitchDeleteQueryParams(EndpointQueryParams, ClusterNameMixin, TicketIdMixin, ForceMixin):
    """
    # Summary

    Query parameters for switch deletion endpoints.

    ## Parameters

    - cluster_name: Cluster name for multi-cluster environments (default: None)
    - ticket_id: Change control ticket ID (default: None)
    - force: Force deletion even if switch has dependencies (default: False)

    ## Usage

    ```python
    params = SwitchDeleteQueryParams(
        ticket_id="CHG12345",
        force=True
    )
    ```
    """

    def to_query_string(self) -> str:
        """Build query string with clusterName, ticketId, and force parameters."""
        params = []
        if self.cluster_name:
            params.append(f"clusterName={self.cluster_name}")
        if self.ticket_id:
            params.append(f"ticketId={self.ticket_id}")
        if self.force:
            params.append(f"force={str(self.force).lower()}")
        return "&".join(params)


class BootstrapQueryParams(LuceneQueryParams, ClusterNameMixin):
    """
    # Summary

    Query parameters for bootstrap (POAP/PnP) switch listing endpoints.

    ## Parameters

    - cluster_name: Cluster name for multi-cluster environments (default: None)
    - filter: Lucene filter expression (inherited from LuceneQueryParams)
    - max: Maximum number of results (inherited from LuceneQueryParams)
    - offset: Pagination offset (inherited from LuceneQueryParams)
    - sort: Sort field and direction (inherited from LuceneQueryParams)

    ## Usage

    ```python
    params = BootstrapQueryParams(
        max=50,
        sort="serialNumber:asc"
    )
    ```
    """

    def to_query_string(self) -> str:
        """Build query string combining Lucene and cluster parameters."""
        params = []
        if self.cluster_name:
            params.append(f"clusterName={self.cluster_name}")

        # Add Lucene parameters
        lucene_string = self.to_lucene_query_string(url_encode=True)
        if lucene_string:
            params.append(lucene_string)

        return "&".join(params)


class InventorySwitchesQueryParams(LuceneQueryParams, ClusterNameMixin, HostnameMixin):
    """
    # Summary

    Query parameters for global inventory switches listing.

    ## Parameters

    - cluster_name: Cluster name for multi-cluster environments (default: None)
    - hostname: Filter by switch hostname (default: None)
    - fabric_name: Filter by fabric name (default: None)
    - switch_id: Filter by switch ID/serial number (default: None)
    - filter: Lucene filter expression (inherited from LuceneQueryParams)
    - max: Maximum number of results (inherited from LuceneQueryParams)
    - offset: Pagination offset (inherited from LuceneQueryParams)
    - sort: Sort field and direction (inherited from LuceneQueryParams)

    ## Usage

    ```python
    params = InventorySwitchesQueryParams(
        fabric_name="MyFabric",
        hostname="spine*",
        max=100
    )
    ```
    """

    fabric_name: Optional[str] = Field(default=None, min_length=1, max_length=64, description="Filter by fabric name")
    switch_id: Optional[str] = Field(default=None, min_length=1, description="Filter by switch ID")

    def to_query_string(self) -> str:
        """Build query string combining all parameters."""
        params = []
        if self.cluster_name:
            params.append(f"clusterName={self.cluster_name}")
        if self.fabric_name:
            params.append(f"fabricName={self.fabric_name}")
        if self.switch_id:
            params.append(f"switchId={self.switch_id}")
        if self.hostname:
            params.append(f"hostname={self.hostname}")

        # Add Lucene parameters
        lucene_string = self.to_lucene_query_string(url_encode=True)
        if lucene_string:
            params.append(lucene_string)

        return "&".join(params)


class CredentialsSwitchesQueryParams(EndpointQueryParams, ClusterNameMixin):
    """
    # Summary

    Query parameters for credentials/switches endpoints.

    ## Parameters

    - cluster_name: Cluster name for multi-cluster environments (default: None)
    """

    def to_query_string(self) -> str:
        """Build query string with clusterName parameter."""
        params = []
        if self.cluster_name:
            params.append(f"clusterName={self.cluster_name}")
        return "&".join(params)
