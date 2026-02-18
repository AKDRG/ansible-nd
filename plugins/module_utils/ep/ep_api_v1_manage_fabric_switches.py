# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
ND Manage Fabric Switches endpoint models.

This module contains endpoint definitions for switch CRUD operations
within fabrics in the ND Manage API.

Endpoints covered:
- List switches in a fabric
- Add switches to a fabric
- Get a specific switch
- Delete a specific switch
- Get switches summary
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type  # pylint: disable=invalid-name
__author__ = "Akshayanat C S"

from typing import Literal

from ansible_collections.cisco.nd.plugins.module_utils.enums import HttpVerbEnum
from ansible_collections.cisco.nd.plugins.module_utils.ep.base_paths_manage import BasePath
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_mixins import FabricNameMixin, SwitchIdMixin
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_query_params import (
    FabricSwitchesQueryParams,
    ManageSwitchAddQueryParams,
    SwitchDeleteQueryParams,
)
from ansible_collections.cisco.nd.plugins.module_utils.pydantic_compat import BaseModel, ConfigDict, Field

# Common config for basic validation
COMMON_CONFIG = ConfigDict(validate_assignment=True)


class _EpManageFabricSwitchesBase(FabricNameMixin, BaseModel):
    """
    Base class for Fabric Switches endpoints.

    Provides common functionality for all HTTP methods on the
    /api/v1/manage/fabrics/{fabricName}/switches endpoint.
    """

    model_config = COMMON_CONFIG

    @property
    def _base_path(self) -> str:
        """Build the base endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")
        return BasePath.manage_fabrics(self.fabric_name, "switches")


class EpManageFabricSwitchesGet(_EpManageFabricSwitchesBase):
    """
    # Summary

    List Fabric Switches Endpoint

    ## Description

    Endpoint to list all switches in a specific fabric with optional filtering.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switches

    ## Verb

    - GET

    ## Usage

    ```python
    request = EpManageFabricSwitchesGet()
    request.fabric_name = "MyFabric"
    request.query_params.hostname = "leaf1"
    request.query_params.max = 100

    path = request.path
    verb = request.verb
    ```
    """

    class_name: Literal["EpManageFabricSwitchesGet"] = Field(
        default="EpManageFabricSwitchesGet", description="Class name for backward compatibility"
    )
    query_params: FabricSwitchesQueryParams = Field(default_factory=FabricSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path with query parameters."""
        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{self._base_path}?{query_string}"
        return self._base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.GET


class EpManageFabricSwitchesAdd(_EpManageFabricSwitchesBase):
    """
    # Summary

    Add Switches to Fabric Endpoint

    ## Description

    Endpoint to add switches to a specific fabric.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switches

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageFabricSwitchesAdd()
    request.fabric_name = "MyFabric"
    request.query_params.cluster_name = "cluster1"
    request.query_params.ticket_id = "CHG12345"

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "password": "mysecret",
        "platformType": "nx-os",
        "preserveConfig": true,
        "switches": [
            {
                "hostname": "leaf1",
                "ip": "10.23.244.81",
                "model": "N9K-C93180YC-FX",
                "serialNumber": "SAL1948TRTT",
                "softwareVersion": "10.3(3)",
                "switchRole": "leaf"
            }
        ]
    }
    ```
    """

    class_name: Literal["EpManageFabricSwitchesAdd"] = Field(
        default="EpManageFabricSwitchesAdd", description="Class name for backward compatibility"
    )
    query_params: ManageSwitchAddQueryParams = Field(default_factory=ManageSwitchAddQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path with query parameters."""
        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{self._base_path}?{query_string}"
        return self._base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class _EpManageFabricSwitchBase(FabricNameMixin, SwitchIdMixin, BaseModel):
    """
    Base class for single switch endpoints.

    Provides common functionality for all HTTP methods on the
    /api/v1/manage/fabrics/{fabricName}/switches/{switchId} endpoint.
    """

    model_config = COMMON_CONFIG

    @property
    def _base_path(self) -> str:
        """Build the base endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")
        if self.switch_id is None:
            raise ValueError("switch_id must be set before accessing path")
        return BasePath.manage_fabrics(self.fabric_name, "switches", self.switch_id)


class EpManageFabricSwitchGet(_EpManageFabricSwitchBase):
    """
    # Summary

    Get Specific Switch Endpoint

    ## Description

    Endpoint to get details of a specific switch in a fabric.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switches/{switchId}

    ## Verb

    - GET

    ## Usage

    ```python
    request = EpManageFabricSwitchGet()
    request.fabric_name = "MyFabric"
    request.switch_id = "SAL1948TRTT"

    path = request.path
    verb = request.verb
    ```
    """

    class_name: Literal["EpManageFabricSwitchGet"] = Field(
        default="EpManageFabricSwitchGet", description="Class name for backward compatibility"
    )
    query_params: FabricSwitchesQueryParams = Field(default_factory=FabricSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path with query parameters."""
        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{self._base_path}?{query_string}"
        return self._base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.GET


class EpManageFabricSwitchDelete(_EpManageFabricSwitchBase):
    """
    # Summary

    Delete Specific Switch Endpoint

    ## Description

    Endpoint to delete a specific switch from a fabric.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switches/{switchId}

    ## Verb

    - DELETE

    ## Usage

    ```python
    request = EpManageFabricSwitchDelete()
    request.fabric_name = "MyFabric"
    request.switch_id = "SAL1948TRTT"
    request.query_params.force = True
    request.query_params.ticket_id = "CHG12345"

    path = request.path
    verb = request.verb
    ```
    """

    class_name: Literal["EpManageFabricSwitchDelete"] = Field(
        default="EpManageFabricSwitchDelete", description="Class name for backward compatibility"
    )
    query_params: SwitchDeleteQueryParams = Field(default_factory=SwitchDeleteQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path with query parameters."""
        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{self._base_path}?{query_string}"
        return self._base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.DELETE


class EpManageFabricSwitchesSummary(FabricNameMixin, BaseModel):
    """
    # Summary

    Fabric Switches Summary Endpoint

    ## Description

    Endpoint to get summary of switches in a fabric categorized by:
    - Anomaly level
    - Configuration sync status
    - Role
    - Software version

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switches/summary

    ## Verb

    - GET

    ## Usage

    ```python
    request = EpManageFabricSwitchesSummary()
    request.fabric_name = "MyFabric"

    path = request.path
    verb = request.verb
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricSwitchesSummary"] = Field(
        default="EpManageFabricSwitchesSummary", description="Class name for backward compatibility"
    )
    query_params: FabricSwitchesQueryParams = Field(default_factory=FabricSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "switches", "summary")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.GET


class EpManageFabricSwitchUpdateRole(FabricNameMixin, SwitchIdMixin, BaseModel):
    """
    # Summary

    Update Switch Role Endpoint

    ## Description

    Endpoint to update the role of a specific switch in a fabric.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switches/{switchId}/role

    ## Verb

    - PUT

    ## Usage

    ```python
    request = EpManageFabricSwitchUpdateRole()
    request.fabric_name = "MyFabric"
    request.switch_id = "SAL1948TRTT"

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "role": "spine"
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricSwitchUpdateRole"] = Field(
        default="EpManageFabricSwitchUpdateRole", description="Class name for backward compatibility"
    )
    query_params: FabricSwitchesQueryParams = Field(default_factory=FabricSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")
        if self.switch_id is None:
            raise ValueError("switch_id must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "switches", self.switch_id, "role")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.PUT
