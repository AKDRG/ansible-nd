# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
ND Manage Credentials endpoint models.

This module contains endpoint definitions for switch credential operations
in the ND Manage API.

Endpoints covered:
- List switch credentials
- Create switch credentials
- Remove switch credentials
- Validate switch credentials
"""

from __future__ import absolute_import, annotations, division, print_function

# pylint: disable=invalid-name
__metaclass__ = type
__author__ = "Akshayanat C S"
# pylint: enable=invalid-name

from typing import Literal

from ansible_collections.cisco.nd.plugins.module_utils.enums import HttpVerbEnum
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_mixins import SwitchIdMixin
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_query_params import CredentialsSwitchesQueryParams
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.base_paths_manage import BasePath
from ansible_collections.cisco.nd.plugins.module_utils.pydantic_compat import BaseModel, ConfigDict, Field

# Common config for basic validation
COMMON_CONFIG = ConfigDict(validate_assignment=True)


class _EpManageCredentialsSwitchesBase(BaseModel):
    """
    Base class for Credentials Switches endpoints.

    Provides common functionality for all HTTP methods on the
    /api/v1/manage/credentials/switches endpoint.
    """

    model_config = COMMON_CONFIG

    @property
    def _base_path(self) -> str:
        """Build the base endpoint path."""
        return BasePath.manage_credentials("switches")


class EpManageCredentialsSwitchesGet(_EpManageCredentialsSwitchesBase):
    """
    # Summary

    List Switch Credentials Endpoint

    ## Description

    Endpoint to list switch credentials for users.

    ## Path

    - /api/v1/manage/credentials/switches

    ## Verb

    - GET

    ## Usage

    ```python
    request = EpManageCredentialsSwitchesGet()

    path = request.path
    verb = request.verb
    ```
    """

    class_name: Literal["EpManageCredentialsSwitchesGet"] = Field(
        default="EpManageCredentialsSwitchesGet", description="Class name for backward compatibility"
    )
    query_params: CredentialsSwitchesQueryParams = Field(default_factory=CredentialsSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{self._base_path}?{query_string}"
        return self._base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.GET


class EpManageCredentialsSwitchesCreate(_EpManageCredentialsSwitchesBase):
    """
    # Summary

    Create Switch Credentials Endpoint

    ## Description

    Endpoint to save switch credentials for the user.

    ## Path

    - /api/v1/manage/credentials/switches

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageCredentialsSwitchesCreate()

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example (Local Credentials)

    ```json
    {
        "switchIds": ["SAL1948TRTT", "SAL1947TRAB"],
        "switchPassword": "test",
        "switchUsername": "admin"
    }
    ```

    ## Request Body Example (CyberArk)

    ```json
    {
        "remoteCredentialStoreKey": "NexusDashboard/root/P_H_NexusDashboard-Dev/misc-unmanaged-cisco.com-admin",
        "remoteCredentialStoreType": "cyberark",
        "switchIds": ["SAL1948TRTT", "SAL1947TRAB"]
    }
    ```
    """

    class_name: Literal["EpManageCredentialsSwitchesCreate"] = Field(
        default="EpManageCredentialsSwitchesCreate", description="Class name for backward compatibility"
    )
    query_params: CredentialsSwitchesQueryParams = Field(default_factory=CredentialsSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{self._base_path}?{query_string}"
        return self._base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageCredentialsSwitchesRemove(BaseModel):
    """
    # Summary

    Remove Switch Credentials Endpoint

    ## Description

    Endpoint to delete switch credentials for the user.

    ## Path

    - /api/v1/manage/credentials/switches/actions/remove

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageCredentialsSwitchesRemove()

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

    class_name: Literal["EpManageCredentialsSwitchesRemove"] = Field(
        default="EpManageCredentialsSwitchesRemove", description="Class name for backward compatibility"
    )
    query_params: CredentialsSwitchesQueryParams = Field(default_factory=CredentialsSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        base_path = BasePath.manage_credentials("switches", "actions", "remove")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageCredentialsSwitchValidate(SwitchIdMixin, BaseModel):
    """
    # Summary

    Validate Switch Credentials Endpoint

    ## Description

    Endpoint to validate switch credentials for a specific switch.

    ## Path

    - /api/v1/manage/credentials/switches/{switchId}/actions/validate

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageCredentialsSwitchValidate()
    request.switch_id = "SAL1948TRTT"

    path = request.path
    verb = request.verb
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageCredentialsSwitchValidate"] = Field(
        default="EpManageCredentialsSwitchValidate", description="Class name for backward compatibility"
    )
    query_params: CredentialsSwitchesQueryParams = Field(default_factory=CredentialsSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.switch_id is None:
            raise ValueError("switch_id must be set before accessing path")

        base_path = BasePath.manage_credentials("switches", self.switch_id, "actions", "validate")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST
