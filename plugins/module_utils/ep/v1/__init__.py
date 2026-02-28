# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Allen Robel (@arobel) <arobel@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
ND API v1 endpoint definitions.

This module provides all endpoint classes and helpers for ND API v1
(ND 3.0+, NDFC 12+).

Import from this module to explicitly use v1 endpoints:

```python
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1 import (
    EpInfraAaaLocalUsersGet,
    BasePathInfra,
)
```

Or import from the parent ep module for current stable version:

```python
from ansible_collections.cisco.nd.plugins.module_utils.ep import (
    EpInfraAaaLocalUsersGet,
    BasePathInfra,
)
```
"""

from __future__ import absolute_import, annotations, division, print_function

# pylint: disable=invalid-name
__metaclass__ = type
# pylint: enable=invalid-name

from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.base_paths_infra import BasePath as BasePathInfra
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.base_paths_manage import BasePath as BasePathManage
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.ep_infra_aaa import (
    EpInfraAaaLocalUsersDelete,
    EpInfraAaaLocalUsersGet,
    EpInfraAaaLocalUsersPost,
    EpInfraAaaLocalUsersPut,
)
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.ep_infra_clusterhealth import (
    ClusterHealthConfigEndpointParams,
    ClusterHealthStatusEndpointParams,
    EpInfraClusterhealthConfigGet,
    EpInfraClusterhealthStatusGet,
)
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.ep_manage_switches import (
    EpManageSwitchesGet,
    SwitchesEndpointParams,
)

# Fabric Config endpoints
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.ep_manage_fabric_config import (
    EpManageFabricConfigDeploy,
    EpManageFabricConfigSave,
    EpManageFabricGet,
    EpManageFabricInventoryDiscover,
)

# Fabric Switches endpoints
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.ep_manage_fabric_switches import (
    EpManageFabricSwitchDelete,
    EpManageFabricSwitchesAdd,
    EpManageFabricSwitchesGet,
    EpManageFabricSwitchesSummary,
    EpManageFabricSwitchGet,
    EpManageFabricSwitchUpdateRole,
)

# Fabric Switch Actions endpoints
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.ep_manage_fabric_switch_actions import (
    EpManageFabricSwitchActionsChangeRoles,
    EpManageFabricSwitchActionsImportBootstrap,
    EpManageFabricSwitchActionsPreProvision,
    EpManageFabricSwitchActionsRediscover,
    EpManageFabricSwitchActionsRediscoverInterfaces,
    EpManageFabricSwitchActionsReload,
    EpManageFabricSwitchActionsRemove,
    EpManageFabricSwitchChangeSerialNumber,
    EpManageFabricSwitchInterfaceGet,
    EpManageFabricSwitchInterfacesGet,
    EpManageFabricSwitchProvisionRMA,
)

# Fabric Discovery endpoints
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.ep_manage_fabric_discovery import (
    EpManageFabricShallowDiscovery,
)

# Fabric Bootstrap endpoints
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.ep_manage_fabric_bootstrap import (
    EpManageFabricBootstrapGet,
)

# Credentials endpoints
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.ep_manage_credentials import (
    EpManageCredentialsSwitchesCreate,
    EpManageCredentialsSwitchesGet,
    EpManageCredentialsSwitchesRemove,
    EpManageCredentialsSwitchValidate,
)

# Inventory endpoints
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.ep_manage_inventory import (
    EpManageFabricInventorySummary,
    EpManageInventorySwitchActionsCopyRunStart,
    EpManageInventorySwitchActionsDeploy,
    EpManageInventorySwitchActionsPreview,
    EpManageInventorySwitchActionsRediscover,
    EpManageInventorySwitchActionsRemove,
    EpManageInventorySwitchesGet,
    EpManageInventorySwitchesLicenses,
    EpManageInventorySwitchesSummary,
)

__all__ = [
    # BasePath helpers
    "BasePathInfra",
    "BasePathManage",
    # Infra AAA endpoints
    "EpInfraAaaLocalUsersGet",
    "EpInfraAaaLocalUsersPost",
    "EpInfraAaaLocalUsersPut",
    "EpInfraAaaLocalUsersDelete",
    # Infra ClusterHealth endpoints
    "EpInfraClusterhealthConfigGet",
    "EpInfraClusterhealthStatusGet",
    "ClusterHealthConfigEndpointParams",
    "ClusterHealthStatusEndpointParams",
    # Manage Switches endpoints
    "EpManageSwitchesGet",
    "SwitchesEndpointParams",
    # Fabric Config endpoints
    "EpManageFabricConfigSave",
    "EpManageFabricConfigDeploy",
    "EpManageFabricGet",
    "EpManageFabricInventoryDiscover",
    # Fabric Switches endpoints
    "EpManageFabricSwitchesGet",
    "EpManageFabricSwitchesAdd",
    "EpManageFabricSwitchGet",
    "EpManageFabricSwitchDelete",
    "EpManageFabricSwitchesSummary",
    "EpManageFabricSwitchUpdateRole",
    # Fabric Switch Actions endpoints
    "EpManageFabricSwitchActionsRediscover",
    "EpManageFabricSwitchActionsRediscoverInterfaces",
    "EpManageFabricSwitchActionsReload",
    "EpManageFabricSwitchActionsRemove",
    "EpManageFabricSwitchActionsChangeRoles",
    "EpManageFabricSwitchActionsImportBootstrap",
    "EpManageFabricSwitchActionsPreProvision",
    "EpManageFabricSwitchProvisionRMA",
    "EpManageFabricSwitchChangeSerialNumber",
    "EpManageFabricSwitchInterfacesGet",
    "EpManageFabricSwitchInterfaceGet",
    # Fabric Discovery endpoints
    "EpManageFabricShallowDiscovery",
    # Fabric Bootstrap endpoints
    "EpManageFabricBootstrapGet",
    # Credentials endpoints
    "EpManageCredentialsSwitchesGet",
    "EpManageCredentialsSwitchesCreate",
    "EpManageCredentialsSwitchesRemove",
    "EpManageCredentialsSwitchValidate",
    # Inventory endpoints
    "EpManageInventorySwitchesGet",
    "EpManageInventorySwitchesSummary",
    "EpManageInventorySwitchesLicenses",
    "EpManageFabricInventorySummary",
    "EpManageInventorySwitchActionsRediscover",
    "EpManageInventorySwitchActionsRemove",
    "EpManageInventorySwitchActionsDeploy",
    "EpManageInventorySwitchActionsPreview",
    "EpManageInventorySwitchActionsCopyRunStart",
]
