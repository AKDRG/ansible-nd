# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
ND Manage Fabric Config endpoint models.

This module contains endpoint definitions for fabric configuration operations
in the ND Manage API.

Endpoints covered:
- Config save (recalculate)
- Config deploy
- Get fabric info
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type  # pylint: disable=invalid-name
__author__ = "Akshayanat C S"

from typing import Literal

from ansible_collections.cisco.nd.plugins.module_utils.enums import HttpVerbEnum
from ansible_collections.cisco.nd.plugins.module_utils.ep.base_paths_manage import BasePath
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_mixins import FabricNameMixin
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_query_params import FabricConfigDeployQueryParams
from ansible_collections.cisco.nd.plugins.module_utils.pydantic_compat import BaseModel, ConfigDict, Field

# Common config for basic validation
COMMON_CONFIG = ConfigDict(validate_assignment=True)


class EpManageFabricConfigSave(FabricNameMixin, BaseModel):
    """
    # Summary

    Fabric Config Save Endpoint

    ## Description

    Endpoint to save (recalculate) fabric configuration.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/config-save

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageFabricConfigSave()
    request.fabric_name = "MyFabric"

    path = request.path
    verb = request.verb
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricConfigSave"] = Field(
        default="EpManageFabricConfigSave", description="Class name for backward compatibility"
    )

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "config-save")
        return base_path

    @property
    def verb(self) -> str:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageFabricConfigDeploy(FabricNameMixin, BaseModel):
    """
    # Summary

    Fabric Config Deploy Endpoint

    ## Description

    Endpoint to deploy pending configuration to switches in a fabric.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/config-deploy

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageFabricConfigDeploy()
    request.fabric_name = "MyFabric"
    request.query_params.force_show_run = "true"
    request.query_params.incl_all_msd_switches = "false"

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "switches": ["SAL1948TRTT", "SAL1947TRAB"]
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricConfigDeploy"] = Field(
        default="EpManageFabricConfigDeploy", description="Class name for backward compatibility"
    )
    query_params: FabricConfigDeployQueryParams = Field(default_factory=FabricConfigDeployQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "config-deploy")
        return f"{base_path}{self.query_params.query_string}"

    @property
    def verb(self) -> str:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageFabricGet(FabricNameMixin, BaseModel):
    """
    # Summary

    Get Fabric Info Endpoint

    ## Description

    Endpoint to retrieve fabric information.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}

    ## Verb

    - GET

    ## Usage

    ```python
    request = EpManageFabricGet()
    request.fabric_name = "MyFabric"

    path = request.path
    verb = request.verb
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricGet"] = Field(
        default="EpManageFabricGet", description="Class name for backward compatibility"
    )

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        return BasePath.manage_fabrics(self.fabric_name)

    @property
    def verb(self) -> str:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.GET


class EpManageFabricInventoryDiscover(FabricNameMixin, BaseModel):
    """
    # Summary

    Fabric Inventory Discover Endpoint

    ## Description

    Endpoint to get discovery status for switches in a fabric.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/inventory/discover

    ## Verb

    - GET

    ## Usage

    ```python
    request = EpManageFabricInventoryDiscover()
    request.fabric_name = "MyFabric"

    path = request.path
    verb = request.verb
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricInventoryDiscover"] = Field(
        default="EpManageFabricInventoryDiscover", description="Class name for backward compatibility"
    )

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "inventory", "discover")
        return base_path

    @property
    def verb(self) -> str:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.GET
