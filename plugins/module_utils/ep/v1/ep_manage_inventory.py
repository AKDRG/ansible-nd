# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
ND Manage Inventory endpoint models.

This module contains endpoint definitions for global inventory operations
in the ND Manage API (cross-fabric queries).

Endpoints covered:
- List all switches globally
- Global switches summary
- Switch licenses
- Fabric inventory summary
- Global switch actions (rediscover, remove, deploy, preview, copy run start)
"""

from __future__ import absolute_import, annotations, division, print_function

# pylint: disable=invalid-name
__metaclass__ = type
__author__ = "Akshayanat C S"
# pylint: enable=invalid-name

from typing import Literal

from ansible_collections.cisco.nd.plugins.module_utils.enums import HttpVerbEnum
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_mixins import FabricNameMixin
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_query_params import (
    CredentialsSwitchesQueryParams,
    FabricSwitchesQueryParams,
    InventorySwitchesQueryParams,
    SwitchDeleteQueryParams,
)
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.base_paths_manage import BasePath
from ansible_collections.cisco.nd.plugins.module_utils.pydantic_compat import BaseModel, ConfigDict, Field

# Common config for basic validation
COMMON_CONFIG = ConfigDict(validate_assignment=True)


# ============================================================================
# Global Inventory Endpoints
# ============================================================================


class EpManageInventorySwitchesGet(BaseModel):
    """
    # Summary

    List All Switches Globally Endpoint

    ## Description

    Endpoint to list switches globally across all fabrics.

    ## Path

    - /api/v1/manage/inventory/switches

    ## Verb

    - GET

    ## Usage

    ```python
    request = EpManageInventorySwitchesGet()
    request.query_params.fabric_name = "MyFabric"
    request.query_params.hostname = "leaf*"
    request.query_params.max = 100

    path = request.path
    verb = request.verb
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageInventorySwitchesGet"] = Field(
        default="EpManageInventorySwitchesGet", description="Class name for backward compatibility"
    )
    query_params: InventorySwitchesQueryParams = Field(default_factory=InventorySwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path with query parameters."""
        base_path = BasePath.manage_inventory("switches")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.GET


class EpManageInventorySwitchesSummary(BaseModel):
    """
    # Summary

    Global Switches Summary Endpoint

    ## Description

    Endpoint to get global summary of switches across all fabrics.

    ## Path

    - /api/v1/manage/inventory/switches/summary

    ## Verb

    - GET

    ## Usage

    ```python
    request = EpManageInventorySwitchesSummary()

    path = request.path
    verb = request.verb
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageInventorySwitchesSummary"] = Field(
        default="EpManageInventorySwitchesSummary", description="Class name for backward compatibility"
    )
    query_params: CredentialsSwitchesQueryParams = Field(default_factory=CredentialsSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        base_path = BasePath.manage_inventory("switches", "summary")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.GET


class EpManageInventorySwitchesLicenses(BaseModel):
    """
    # Summary

    List Switch Licenses Endpoint

    ## Description

    Endpoint to list switch licenses globally.

    ## Path

    - /api/v1/manage/inventory/switches/licenses

    ## Verb

    - GET

    ## Usage

    ```python
    request = EpManageInventorySwitchesLicenses()
    request.query_params.max = 100

    path = request.path
    verb = request.verb
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageInventorySwitchesLicenses"] = Field(
        default="EpManageInventorySwitchesLicenses", description="Class name for backward compatibility"
    )
    query_params: InventorySwitchesQueryParams = Field(default_factory=InventorySwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path with query parameters."""
        base_path = BasePath.manage_inventory("switches", "licenses")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.GET


class EpManageFabricInventorySummary(FabricNameMixin, BaseModel):
    """
    # Summary

    Fabric Inventory Summary Endpoint

    ## Description

    Endpoint to get inventory summary for a specific fabric including
    count of switches, VPC pairs, devices, and controllers.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/inventory/summary

    ## Verb

    - GET

    ## Usage

    ```python
    request = EpManageFabricInventorySummary()
    request.fabric_name = "MyFabric"

    path = request.path
    verb = request.verb
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricInventorySummary"] = Field(
        default="EpManageFabricInventorySummary", description="Class name for backward compatibility"
    )
    query_params: FabricSwitchesQueryParams = Field(default_factory=FabricSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "inventory", "summary")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.GET


# ============================================================================
# Inventory Switch Actions Endpoints
# ============================================================================


class EpManageInventorySwitchActionsRediscover(BaseModel):
    """
    # Summary

    Global Rediscover Switches Endpoint

    ## Description

    Endpoint to rediscover switches globally (not fabric-specific).

    ## Path

    - /api/v1/manage/inventory/switchActions/rediscover

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageInventorySwitchActionsRediscover()

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "switchIds": ["SAL1948TRTT", "SAL1947TRAB"]
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageInventorySwitchActionsRediscover"] = Field(
        default="EpManageInventorySwitchActionsRediscover", description="Class name for backward compatibility"
    )
    query_params: CredentialsSwitchesQueryParams = Field(default_factory=CredentialsSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        base_path = BasePath.manage_inventory("switchActions", "rediscover")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageInventorySwitchActionsRemove(BaseModel):
    """
    # Summary

    Global Remove Switches Endpoint

    ## Description

    Endpoint to remove switches globally (not fabric-specific).

    ## Path

    - /api/v1/manage/inventory/switchActions/remove

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageInventorySwitchActionsRemove()

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "switchIds": ["SAL1948TRTT", "SAL1947TRAB"]
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageInventorySwitchActionsRemove"] = Field(
        default="EpManageInventorySwitchActionsRemove", description="Class name for backward compatibility"
    )
    query_params: SwitchDeleteQueryParams = Field(default_factory=SwitchDeleteQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        base_path = BasePath.manage_inventory("switchActions", "remove")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageInventorySwitchActionsDeploy(BaseModel):
    """
    # Summary

    Deploy Configuration to Switches Endpoint

    ## Description

    Endpoint to deploy configuration to specified switches globally.

    ## Path

    - /api/v1/manage/inventory/switchActions/deploy

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageInventorySwitchActionsDeploy()

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "switchIds": ["SAL1948TRTT", "SAL1947TRAB"]
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageInventorySwitchActionsDeploy"] = Field(
        default="EpManageInventorySwitchActionsDeploy", description="Class name for backward compatibility"
    )
    query_params: CredentialsSwitchesQueryParams = Field(default_factory=CredentialsSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        base_path = BasePath.manage_inventory("switchActions", "deploy")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageInventorySwitchActionsPreview(BaseModel):
    """
    # Summary

    Preview Configuration Changes Endpoint

    ## Description

    Endpoint to preview configuration changes for specified switches.

    ## Path

    - /api/v1/manage/inventory/switchActions/preview

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageInventorySwitchActionsPreview()

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "switchIds": ["SAL1948TRTT", "SAL1947TRAB"]
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageInventorySwitchActionsPreview"] = Field(
        default="EpManageInventorySwitchActionsPreview", description="Class name for backward compatibility"
    )
    query_params: CredentialsSwitchesQueryParams = Field(default_factory=CredentialsSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        base_path = BasePath.manage_inventory("switchActions", "preview")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageInventorySwitchActionsCopyRunStart(BaseModel):
    """
    # Summary

    Copy Running to Startup Configuration Endpoint

    ## Description

    Endpoint to copy running configuration to startup configuration for specified switches.

    ## Path

    - /api/v1/manage/inventory/switchActions/copyRunStart

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageInventorySwitchActionsCopyRunStart()

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "switchIds": ["SAL1948TRTT", "SAL1947TRAB"]
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageInventorySwitchActionsCopyRunStart"] = Field(
        default="EpManageInventorySwitchActionsCopyRunStart", description="Class name for backward compatibility"
    )
    query_params: CredentialsSwitchesQueryParams = Field(default_factory=CredentialsSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        base_path = BasePath.manage_inventory("switchActions", "copyRunStart")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST
