# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
ND Manage Fabric Discovery endpoint models.

This module contains endpoint definitions for switch discovery operations
within fabrics in the ND Manage API.

Endpoints covered:
- Shallow discovery
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type  # pylint: disable=invalid-name
__author__ = "Akshayanat C S"

from typing import Literal

from ansible_collections.cisco.nd.plugins.module_utils.enums import HttpVerbEnum
from ansible_collections.cisco.nd.plugins.module_utils.ep.base_paths_manage import BasePath
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_mixins import FabricNameMixin
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_query_params import FabricSwitchesQueryParams
from ansible_collections.cisco.nd.plugins.module_utils.pydantic_compat import BaseModel, ConfigDict, Field

# Common config for basic validation
COMMON_CONFIG = ConfigDict(validate_assignment=True)


class EpManageFabricShallowDiscovery(FabricNameMixin, BaseModel):
    """
    # Summary

    Shallow Discovery Endpoint

    ## Description

    Endpoint to shallow discover switches given seed switches with hop count.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/actions/shallowDiscovery

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageFabricShallowDiscovery()
    request.fabric_name = "MyFabric"

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "maxHop": 2,
        "password": "mysecret",
        "platformType": "nx-os",
        "seedIpCollection": ["10.23.244.2", "10.23.245.2"],
        "snmpV3AuthProtocol": "md5",
        "username": "admin"
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricShallowDiscovery"] = Field(
        default="EpManageFabricShallowDiscovery", description="Class name for backward compatibility"
    )
    query_params: FabricSwitchesQueryParams = Field(default_factory=FabricSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "actions", "shallowDiscovery")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST
