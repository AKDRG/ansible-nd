# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
ND Manage Fabric Bootstrap endpoint models.

This module contains endpoint definitions for switch bootstrap operations
within fabrics in the ND Manage API.

Endpoints covered:
- List bootstrap switches (POAP/PnP)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type  # pylint: disable=invalid-name
__author__ = "Akshayanat C S"

from typing import Literal

from ansible_collections.cisco.nd.plugins.module_utils.enums import HttpVerbEnum
from ansible_collections.cisco.nd.plugins.module_utils.ep.base_paths_manage import BasePath
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_mixins import FabricNameMixin
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_query_params import BootstrapQueryParams
from ansible_collections.cisco.nd.plugins.module_utils.pydantic_compat import BaseModel, ConfigDict, Field

# Common config for basic validation
COMMON_CONFIG = ConfigDict(validate_assignment=True)


class EpManageFabricBootstrapGet(FabricNameMixin, BaseModel):
    """
    # Summary

    List Bootstrap Switches Endpoint

    ## Description

    Endpoint to list switches currently going through bootstrap loop via POAP (NX-OS) or PnP (IOS-XE).

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/bootstrap

    ## Verb

    - GET

    ## Usage

    ```python
    request = EpManageFabricBootstrapGet()
    request.fabric_name = "MyFabric"
    request.query_params.max = 50

    path = request.path
    verb = request.verb
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricBootstrapGet"] = Field(
        default="EpManageFabricBootstrapGet", description="Class name for backward compatibility"
    )
    query_params: BootstrapQueryParams = Field(default_factory=BootstrapQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path with query parameters."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "bootstrap")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.GET
