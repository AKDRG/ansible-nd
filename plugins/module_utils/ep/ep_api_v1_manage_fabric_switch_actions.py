# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
ND Manage Fabric Switch Actions endpoint models.

This module contains endpoint definitions for switch action operations
within fabrics in the ND Manage API.

Endpoints covered:
- Rediscover switches
- Rediscover switch interfaces
- Reload switches
- Remove switches (bulk delete)
- Import bootstrap (POAP)
- Provision RMA
- Change serial number
- List/get switch interfaces
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type  # pylint: disable=invalid-name
__author__ = "Akshayanat C S"

from typing import Literal

from ansible_collections.cisco.nd.plugins.module_utils.enums import HttpVerbEnum
from ansible_collections.cisco.nd.plugins.module_utils.ep.base_paths_manage import BasePath
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_mixins import FabricNameMixin, SwitchIdMixin, InterfaceNameMixin
from ansible_collections.cisco.nd.plugins.module_utils.ep.endpoint_query_params import (
    FabricSwitchesQueryParams,
    ManageSwitchAddQueryParams,
    SwitchDeleteQueryParams,
)
from ansible_collections.cisco.nd.plugins.module_utils.pydantic_compat import BaseModel, ConfigDict, Field

# Common config for basic validation
COMMON_CONFIG = ConfigDict(validate_assignment=True)


# ============================================================================
# Switch Actions Endpoints
# ============================================================================


class EpManageFabricSwitchActionsRediscover(FabricNameMixin, BaseModel):
    """
    # Summary

    Rediscover Switches Endpoint

    ## Description

    Endpoint to rediscover specified switches in a fabric.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switchActions/rediscover

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageFabricSwitchActionsRediscover()
    request.fabric_name = "MyFabric"

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

    class_name: Literal["EpManageFabricSwitchActionsRediscover"] = Field(
        default="EpManageFabricSwitchActionsRediscover", description="Class name for backward compatibility"
    )
    query_params: FabricSwitchesQueryParams = Field(default_factory=FabricSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "switchActions", "rediscover")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageFabricSwitchActionsRediscoverInterfaces(FabricNameMixin, BaseModel):
    """
    # Summary

    Rediscover Switch Interfaces Endpoint

    ## Description

    Endpoint to rediscover interfaces of a given switch.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switchActions/rediscoverSwitchInterfaces

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageFabricSwitchActionsRediscoverInterfaces()
    request.fabric_name = "MyFabric"

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "switchId": "SAL1948TRTT"
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricSwitchActionsRediscoverInterfaces"] = Field(
        default="EpManageFabricSwitchActionsRediscoverInterfaces", description="Class name for backward compatibility"
    )
    query_params: FabricSwitchesQueryParams = Field(default_factory=FabricSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "switchActions", "rediscoverSwitchInterfaces")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageFabricSwitchActionsReload(FabricNameMixin, BaseModel):
    """
    # Summary

    Reload Switches Endpoint

    ## Description

    Endpoint to reload specified switches in a fabric.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switchActions/reload

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageFabricSwitchActionsReload()
    request.fabric_name = "MyFabric"

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

    class_name: Literal["EpManageFabricSwitchActionsReload"] = Field(
        default="EpManageFabricSwitchActionsReload", description="Class name for backward compatibility"
    )
    query_params: FabricSwitchesQueryParams = Field(default_factory=FabricSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "switchActions", "reload")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageFabricSwitchActionsRemove(FabricNameMixin, BaseModel):
    """
    # Summary

    Remove Switches Endpoint (Bulk Delete)

    ## Description

    Endpoint to delete multiple switches from a fabric.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switchActions/remove

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageFabricSwitchActionsRemove()
    request.fabric_name = "MyFabric"
    request.query_params.force = True
    request.query_params.ticket_id = "CHG12345"

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

    class_name: Literal["EpManageFabricSwitchActionsRemove"] = Field(
        default="EpManageFabricSwitchActionsRemove", description="Class name for backward compatibility"
    )
    query_params: SwitchDeleteQueryParams = Field(default_factory=SwitchDeleteQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path with query parameters."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "switchActions", "remove")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageFabricSwitchActionsChangeRoles(FabricNameMixin, BaseModel):
    """
    # Summary

    Change Switch Roles Endpoint (Bulk)

    ## Description

    Endpoint to change the role of multiple switches in a single request.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switchActions/changeRoles

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageFabricSwitchActionsChangeRoles()
    request.fabric_name = "MyFabric"

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "switchRoles": [
            {
                "role": "leaf",
                "switchId": "SAL1948TRTT"
            },
            {
                "role": "spine",
                "switchId": "SAL1947TRAB"
            }
        ]
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricSwitchActionsChangeRoles"] = Field(
        default="EpManageFabricSwitchActionsChangeRoles",
        description="Class name for backward compatibility"
    )
    query_params: FabricSwitchesQueryParams = Field(
        default_factory=FabricSwitchesQueryParams
    )

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(
            self.fabric_name, "switchActions", "changeRoles"
        )

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageFabricSwitchActionsImportBootstrap(FabricNameMixin, BaseModel):
    """
    # Summary

    Import Bootstrap Switches Endpoint

    ## Description

    Endpoint to import and bootstrap preprovision or bootstrap switches to a fabric.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switchActions/importBootstrap

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageFabricSwitchActionsImportBootstrap()
    request.fabric_name = "MyFabric"
    request.query_params.ticket_id = "CHG12345"

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "switches": [
            {
                "gatewayIpMask": "10.23.244.1/24",
                "hostname": "leaf1-new",
                "imagePolicy": "NX-OS_9.3.10",
                "inInventory": false,
                "ip": "10.23.244.81",
                "model": "N9K-C93180YC-FX",
                "preprovisionSerial": "SAL1948TRTT",
                "softwareVersion": "9.3(10)",
                "switchRole": "leaf"
            }
        ]
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricSwitchActionsImportBootstrap"] = Field(
        default="EpManageFabricSwitchActionsImportBootstrap", description="Class name for backward compatibility"
    )
    query_params: ManageSwitchAddQueryParams = Field(default_factory=ManageSwitchAddQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "switchActions", "importBootstrap")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


# ============================================================================
# Pre-Provision Endpoints
# ============================================================================


class EpManageFabricSwitchActionsPreProvision(FabricNameMixin, BaseModel):
    """
    # Summary

    Pre-Provision Switches Endpoint

    ## Description

    Endpoint to pre-provision switches in a fabric.  Pre-provisioning
    allows you to define switch parameters (serial, IP, model, etc.)
    ahead of time so that when the physical device boots it is
    automatically absorbed into the fabric.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switchActions/preProvision

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageFabricSwitchActionsPreProvision()
    request.fabric_name = "MyFabric"

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "switches": [
            {
                "gatewayIpMask": "10.23.244.1/24",
                "ip": "10.23.244.10",
                "imagePolicy": "imagePolicy1",
                "model": "N9K-C93180YC-FX",
                "password": "mysecret",
                "serialNumber": "SAL1948TRTT",
                "hostname": "leaf1",
                "username": "admin",
                "softwareVersion": "10.3(3)",
                "discoveryAuthProtocol": "md5"
            }
        ]
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricSwitchActionsPreProvision"] = Field(
        default="EpManageFabricSwitchActionsPreProvision",
        description="Class name for backward compatibility",
    )
    query_params: ManageSwitchAddQueryParams = Field(default_factory=ManageSwitchAddQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(
            self.fabric_name, "switchActions", "preProvision"
        )

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


# ============================================================================
# RMA (Return Material Authorization) Endpoints
# ============================================================================


class EpManageFabricSwitchProvisionRMA(FabricNameMixin, SwitchIdMixin, BaseModel):
    """
    # Summary

    Provision RMA for Switch Endpoint

    ## Description

    Endpoint to RMA (Return Material Authorization) an existing switch with a new bootstrapped switch.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switches/{switchId}/actions/provisionRMA

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageFabricSwitchProvisionRMA()
    request.fabric_name = "MyFabric"
    request.switch_id = "SAL1948TRTT"  # Old switch serial number
    request.query_params.ticket_id = "CHG12345"

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "serialNumber": "NEW_SERIAL_NUMBER"
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricSwitchProvisionRMA"] = Field(
        default="EpManageFabricSwitchProvisionRMA", description="Class name for backward compatibility"
    )
    query_params: ManageSwitchAddQueryParams = Field(default_factory=ManageSwitchAddQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")
        if self.switch_id is None:
            raise ValueError("switch_id must be set before accessing path")

        base_path = BasePath.manage_fabrics(
            self.fabric_name, "switches", self.switch_id, "actions", "provisionRMA"
        )

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


class EpManageFabricSwitchChangeSerialNumber(FabricNameMixin, SwitchIdMixin, BaseModel):
    """
    # Summary

    Change Switch Serial Number Endpoint

    ## Description

    Endpoint to change serial number for a pre-provisioned switch.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switches/{switchId}/actions/changeSwitchSerialNumber

    ## Verb

    - POST

    ## Usage

    ```python
    request = EpManageFabricSwitchChangeSerialNumber()
    request.fabric_name = "MyFabric"
    request.switch_id = "SAL1948TRTT"  # Current serial number

    path = request.path
    verb = request.verb
    ```

    ## Request Body Example

    ```json
    {
        "newSerialNumber": "SAL1948TRUU"
    }
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricSwitchChangeSerialNumber"] = Field(
        default="EpManageFabricSwitchChangeSerialNumber", description="Class name for backward compatibility"
    )
    query_params: FabricSwitchesQueryParams = Field(default_factory=FabricSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")
        if self.switch_id is None:
            raise ValueError("switch_id must be set before accessing path")

        base_path = BasePath.manage_fabrics(
            self.fabric_name, "switches", self.switch_id, "actions", "changeSwitchSerialNumber"
        )

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.POST


# ============================================================================
# Switch Interfaces Endpoints
# ============================================================================


class EpManageFabricSwitchInterfacesGet(FabricNameMixin, SwitchIdMixin, BaseModel):
    """
    # Summary

    List Switch Interfaces Endpoint

    ## Description

    Endpoint to list all interfaces of a specific switch.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switches/{switchId}/interfaces

    ## Verb

    - GET

    ## Usage

    ```python
    request = EpManageFabricSwitchInterfacesGet()
    request.fabric_name = "MyFabric"
    request.switch_id = "SAL1948TRTT"

    path = request.path
    verb = request.verb
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricSwitchInterfacesGet"] = Field(
        default="EpManageFabricSwitchInterfacesGet", description="Class name for backward compatibility"
    )
    query_params: FabricSwitchesQueryParams = Field(default_factory=FabricSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")
        if self.switch_id is None:
            raise ValueError("switch_id must be set before accessing path")

        base_path = BasePath.manage_fabrics(self.fabric_name, "switches", self.switch_id, "interfaces")

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.GET


class EpManageFabricSwitchInterfaceGet(FabricNameMixin, SwitchIdMixin, InterfaceNameMixin, BaseModel):
    """
    # Summary

    Get Specific Interface Endpoint

    ## Description

    Endpoint to get details of a specific interface on a switch.

    ## Path

    - /api/v1/manage/fabrics/{fabricName}/switches/{switchId}/interfaces/{interfaceName}

    ## Verb

    - GET

    ## Usage

    ```python
    request = EpManageFabricSwitchInterfaceGet()
    request.fabric_name = "MyFabric"
    request.switch_id = "SAL1948TRTT"
    request.interface_name = "Ethernet1/1"

    path = request.path
    verb = request.verb
    ```
    """

    model_config = COMMON_CONFIG

    class_name: Literal["EpManageFabricSwitchInterfaceGet"] = Field(
        default="EpManageFabricSwitchInterfaceGet", description="Class name for backward compatibility"
    )
    query_params: FabricSwitchesQueryParams = Field(default_factory=FabricSwitchesQueryParams)

    @property
    def path(self) -> str:
        """Build the endpoint path."""
        if self.fabric_name is None:
            raise ValueError("fabric_name must be set before accessing path")
        if self.switch_id is None:
            raise ValueError("switch_id must be set before accessing path")
        if self.interface_name is None:
            raise ValueError("interface_name must be set before accessing path")

        base_path = BasePath.manage_fabrics(
            self.fabric_name, "switches", self.switch_id, "interfaces", self.interface_name
        )

        query_string = self.query_params.to_query_string()
        if query_string:
            return f"{base_path}?{query_string}"
        return base_path

    @property
    def verb(self) -> HttpVerbEnum:
        """Return the HTTP verb for this endpoint."""
        return HttpVerbEnum.GET
