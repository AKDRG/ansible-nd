#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Akshayant Chengam Sarvanan (@achengam) <achengam@cisco.com>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type
__copyright__ = "Copyright (c) 2025 Cisco and/or its affiliates."
__author__ = "Akshayanat Chengam Saravanan"

DOCUMENTATION = """

---
module: nd_manage_switches
short_description: Manage switches in Cisco Nexus Dashboard.
version_added: "1.0.0"
author: Akshayanat Chengam Saravanan (@achengam)
description:
- Add, delete, override, and query switches in Cisco Nexus Dashboard.
- Supports Pydantic model validation for switch configurations.
- Provides utility functions for merging models and handling default values.
- Uses state-based operations with intelligent diff calculation for optimal API calls.
options:
    fabric:
        description:
        - Name of the target fabric for Inventory operations
        type: str
        required: yes
    state:
        choices:
        - merged
        - overridden
        - deleted
        - query
        default: merged
        description:
        - The state of ND and switch(es) after module completion.
        - merged and query are the only states supported for POAP.
        - merged is the only state supported for RMA.
        type: str
    save:
        default: true
        description:
        - Save/Recalculate the configuration of the fabric after the inventory is updated
        type: bool
        required: false
    deploy:
        default: true
        description:
        - Deploy the pending configuration of the fabric after inventory is updated
        type: bool
        required: false
    config:
        description:
        - List of managed switches. Optional for state deleted
        type: list
        elements: dict
        suboptions:
            seed_ip:
                description:
                - Seed Name(supports IP address, dns_name) of the switch
                which needs to be managed in the ND Fabric
                type: str
                required: true
            auth_proto:
                default: 'MD5'
                description:
                - Name of the authentication protocol to be used.
                - For POAP and RMA configurations authentication protocol should be I(MD5).
                choices: ['MD5', 'SHA', 'MD5_DES', 'MD5_AES', 'SHA_DES', 'SHA_AES']
                type: str
                required: false
            user_name:
                description:
                - Login username to the switch.
                - For POAP and RMA configurations username should be I(admin)
                type: str
                required: true
            password:
                description:
                - Login password to the switch
                type: str
                required: true
            role:
                default: leaf
                description:
                - Role which needs to be assigned to the switch
                choices: 
                - leaf
                - spine
                - border
                - border_spine
                - border_gateway
                - border_gateway_spine
                - super_spine
                - border_super_spine
                - border_gateway_super_spine
                - access
                - aggregation
                - edge_router
                - core_router
                - tor
                type: str
                required: false
            preserve_config:
                default: false
                description:
                - Set this to false for greenfield deployment and true for brownfield deployment
                type: bool
                required: false
            poap:
                description:
                - Configurations of switch to Bootstrap/Pre-provision.
                - Please note that POAP and DHCP configurations needs to enabled in fabric configuration
                before adding/preprovisioning switches through POAP.
                - Idempotence checks against inventory is only for B(IP Address) for Preprovision configs.
                - Idempotence checks against inventory is only for B(IP Address) and B(Serial Number) for Bootstrap configs.
                type: list
                elements: dict
                suboptions:
                    serial_number:
                        description:
                        - Serial number of switch to Bootstrap.
                        - When C(preprovision_serial) is provided along with C(serial_number),
                        then the Preprovisioned switch(with serial number as in C(preprovision_serial)) will be swapped
                        with a actual switch(with serial number in C(serial_number)) through bootstrap.
                        - Swap feature is supported only on NDFC and is not supported on DCNM 11.x versions.
                        type: str
                        required: false
                    preprovision_serial:
                        description:
                        - Serial number of switch to Pre-provision.
                        - When C(preprovision_serial) is provided along with C(serial_number),
                        then the Preprovisioned switch(with serial number as in C(preprovision_serial)) will be swapped
                        with a actual switch(with serial number in C(serial_number)) through bootstrap.
                        - Swap feature is supported only on NDFC and is not supported on DCNM 11.x versions.
                        type: str
                        required: false
                    model:
                        description:
                        - Model of switch to Bootstrap/Pre-provision.
                        type: str
                        required: false
                    version:
                        description:
                        - Software version of switch to Bootstrap/Pre-provision.
                        type: str
                        required: false
                    hostname:
                        description:
                        - Hostname of switch to Bootstrap/Pre-provision.
                        type: str
                        required: false
                    image_policy:
                        description:
                        - Name of the image policy to be applied on switch during Bootstrap/Pre-provision.
                        type: str
                        required: false
                    gateway_ip:
                        description:
                        - Gateway IP with mask for the switch to Bootstrap/Pre-provision.
            rma:
                description:
                - RMA an existing switch with a new one
                - Please note that the existing switch should be configured and deployed in maintenance mode
                - Please note that the existing switch being replaced should be shutdown state or out of network
                type: list
                elements: dict
                suboptions:
                    discovery_username:
                        description:
                        - Username for device discovery during POAP and RMA discovery
                        type: str
                        required: false
                    discovery_password:
                        description:
                        - Password for device discovery during POAP and RMA discovery
                        type: str
                        required: false
                    serial_number:
                        description:
                        - Serial number of switch to Bootstrap for RMA.
                        type: str
                        required: true
                    model:
                        description:
                        - Model of switch to Bootstrap for RMA.
                        type: str
                        required: true
                    version:
                        description:
                        - Software version of switch to Bootstrap for RMA.
                        type: str
                        required: true
                    image_policy:
                        description:
                        - Name of the image policy to be applied on switch during Bootstrap for RMA.
                        type: str
                        required: false

  query_poap:
    default: false
    description:
    - Query for Bootstrap(POAP) capable switches available.
    type: bool
    required: false
"""

EXAMPLES = """
# The following two switches will be merged into the existing fabric
- name: Merge switch into fabric
  cisco.nd.nd_manage_switches:
    fabric: vxlan-fabric
    state: merged
    config:
    - seed_ip: 192.168.0.1
      auth_proto: MD5 # choose from [MD5, SHA, MD5_DES, MD5_AES, SHA_DES, SHA_AES]
      user_name: switch_username
      password: switch_password
      max_hops: 0
      role: spine
      preserve_config: False # boolean, default is  true
    - seed_ip: 192.168.0.2
      auth_proto: MD5 # choose from [MD5, SHA, MD5_DES, MD5_AES, SHA_DES, SHA_AES]
      user_name: switch_username
      password: switch_password
      max_hops: 0
      role: leaf
      preserve_config: False # boolean, default is true

# The following two switches will be added or updated in the existing fabric and all other
# switches will be removed from the fabric
- name: Override Switch
  cisco.nd.nd_manage_switches:
    fabric: vxlan-fabric
    state: overridden
    config:
    - seed_ip: 192.168.0.1
      auth_proto: MD5 # choose from [MD5, SHA, MD5_DES, MD5_AES, SHA_DES, SHA_AES]
      user_name: switch_username
      password: switch_password
      max_hops: 0
      role: spine
      preserve_config: False # boolean, default is  true
    - seed_ip: 192.168.0.2
      auth_proto: MD5 # choose from [MD5, SHA, MD5_DES, MD5_AES, SHA_DES, SHA_AES]
      user_name: switch_username
      password: switch_password
      max_hops: 0
      role: leaf
      preserve_config: False # boolean, default is true

# The following two switches will be deleted in the existing fabric
- name: Delete selected switches
  cisco.nd.nd_manage_switches:
    fabric: vxlan-fabric
    state: deleted # merged / deleted / overridden / query
    config:
    - seed_ip: 192.168.0.1
    - seed_ip: 192.168.0.2

# All the switches will be deleted in the existing fabric
- name: Delete all the switches
  cisco.nd.nd_manage_switches:
    fabric: vxlan-fabric
    state: deleted

# The following two switches information will be queried in the existing fabric
- name: Query switch into fabric
  cisco.nd.nd_manage_switches:
    fabric: vxlan-fabric
    state: query
    config:
    - seed_ip: 192.168.0.1
      role: spine
    - seed_ip: 192.168.0.2
      role: leaf

# All the existing switches will be queried in the existing fabric
- name: Query all the switches in the fabric
  cisco.nd.nd_manage_switches:
    fabric: vxlan-fabric
    state: query
"""
import copy
import inspect
import logging
import re
import traceback
import sys
import json
import pydantic
import time

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.cisco.nd.plugins.module_utils.nd import NDModule
from ansible.module_utils.basic import missing_required_lib

from ..module_utils.common.log import Log

# Individual Model Imports
from ansible_collections.cisco.nd.plugins.module_utils.common.models.input_switch_config_list import InputSwitchConfigurationListModel as InputSwitchConfigurationList
from ansible_collections.cisco.nd.plugins.module_utils.common.models.discovered_switch_list import DiscoveredSwitchListModel as DiscoveredSwitchList
from ansible_collections.cisco.nd.plugins.module_utils.common.models.want_switch_ip_list import WantSwitchIPListModel as WantSwitchIPList
from ansible_collections.cisco.nd.plugins.module_utils.common.models.poap_config import POAPConfigModel as POAPConfig
from ansible_collections.cisco.nd.plugins.module_utils.common.models.rma_config import RMAConfigModel as RMAConfig
from ansible_collections.cisco.nd.plugins.module_utils.common.models.compare_switch_config import CompareSwitchConfigModel as CompareSwitchConfig
from ansible_collections.cisco.nd.plugins.module_utils.common.models.input_switch_config_with_poap import InputSwitchConfigWithPOAPModel as InputSwitchConfigWithPOAP
from ansible_collections.cisco.nd.plugins.module_utils.common.models.input_switch_config_list_with_poap import InputSwitchConfigurationListWithPOAPModel as InputSwitchConfigurationListWithPOAP
from ansible_collections.cisco.nd.plugins.module_utils.common.models.have_switch_config_list import HaveSwitchConfigListModel as HaveSwitchConfigList

# API Endpoint Imports
from ansible_collections.cisco.nd.plugins.module_utils.common.api.v1.manage.fabrics.actions.shallow_discovery import ShallowDiscovery
from ansible_collections.cisco.nd.plugins.module_utils.common.api.v1.manage.fabrics.actions.config_save import FabricConfigSave
from ansible_collections.cisco.nd.plugins.module_utils.common.api.v1.manage.fabrics.actions.deploy import FabricDeploy
from ansible_collections.cisco.nd.plugins.module_utils.common.api.v1.manage.fabrics.switch_actions.deploy import SwitchDeploy
from ansible_collections.cisco.nd.plugins.module_utils.common.api.v1.manage.fabrics.switch_actions.remove import SwitchRemove
from ansible_collections.cisco.nd.plugins.module_utils.common.api.v1.manage.credentials.switches import SaveSwitchCredentials
from ansible_collections.cisco.nd.plugins.module_utils.common.api.v1.manage.fabrics.switches import SwitchesQuery
from ansible_collections.cisco.nd.plugins.module_utils.common.api.v1.manage.fabrics.switches import SwitchesAdd


try:
    from pydantic import BaseModel, ValidationError
except ImportError:
    HAS_PYDANTIC = False
    PYDANTIC_IMPORT_ERROR = traceback.format_exc()
else:
    HAS_PYDANTIC = True
    PYDANTIC_IMPORT_ERROR = None

try:
    from deepdiff import DeepDiff
except ImportError:
    HAS_DEEPDIFF = False
    DEEPDIFF_IMPORT_ERROR = traceback.format_exc()
else:
    HAS_DEEPDIFF = True
    DEEPDIFF_IMPORT_ERROR = None


# Utility Classes for handling switch operations

class PayloadUtils:
    """
    Utility class for building API payloads for switch operations.
    """
    
    def __init__(self, logger=None):
        self.class_name = self.__class__.__name__
        self.log = logger or logging.getLogger(f"nd.{self.class_name}")
    
    @staticmethod
    def group_switches_build_payload(switches_list, grouping_keys, switch_keys, ip_key, logger=None):
        """
        Static method to group switches by common attributes for API payload construction.
        
        This method is commonly used across different operations:
        - Discovery: group by credentials for shallow discovery
        - Addition: group by credentials and config for bulk adding
        - Credentials: group by credentials for bulk credential saving
        - Deletion: group switches for bulk removal
        """
        log = logger or logging.getLogger("nd.PayloadUtils")
        
        log.debug(f"Grouping {len(switches_list)} switches by {grouping_keys}")
        
        grouped = {}
        
        for switch in switches_list:
            # Create grouping key
            group_key = tuple(switch.get(key) for key in grouping_keys)
            
            # Initialize group
            if group_key not in grouped:
                payload_key = {ip_key: []}
                
                # Add operation-specific flags
                if 'switches' in ip_key:
                    payload_key.update({"useCredentialForWrite": True})
                
                # Add grouping attributes
                for g_key in grouping_keys:
                    payload_key.update({g_key: switch.get(g_key, None)})
                    
                grouped[group_key] = payload_key

            # Add switch data based on collection type
            if 'seedIpCollection' in ip_key:
                grouped[group_key][ip_key].append(switch.get('ip'))
            elif 'switchIds' in ip_key:
                grouped[group_key][ip_key].append({'switchId': switch.get('switchId')})
            else:
                switch_info = {key: switch.get(key) for key in switch_keys if key in switch}
                grouped[group_key][ip_key].append(switch_info)

        payloads = list(grouped.values())
        log.info(f"Created {len(payloads)} grouped payloads from {len(switches_list)} switches")
        
        return payloads

class FabricUtils:
    """
    Helper class for fabric-related operations.
    """
    
    def __init__(self, nd, logger=None):
        self.class_name = self.__class__.__name__
        self.log = logger or logging.getLogger(f"nd.{self.class_name}")
        self.nd = nd
        self.fabric = nd.params["fabric"]
        self.fabric_details = None
        
    def get_fabric_details(self):
        """
        Retrieve fabric details from ND API.
        
        Returns:
            dict: Fabric details including greenfieldDebugFlag
        """
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        path = f"/api/v1/manage/fabrics/{self.fabric}"
        
        try:
            response = self.nd.request(path, method="GET")
            self.fabric_details = response
            
            greenfield_flag = response.get("management", {}).get("greenfieldDebugFlag", "").lower()
            msg = f"Fabric {self.fabric} greenfieldDebugFlag: {greenfield_flag}"
            self.log.info(msg)
            
            return response
            
        except Exception as e:
            msg = f"Failed to retrieve fabric details: {str(e)}"
            self.log.error(msg)
            self.nd.fail_json(msg=msg, exception=str(e))
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)
    
    def is_greenfield_debug_enabled(self):
        """
        Check if greenfield debug flag is enabled.
        
        Returns:
            bool: True if greenfield debug flag is enabled
        """
        if not self.fabric_details:
            self.get_fabric_details()
            
        greenfield_flag = self.fabric_details.get("management", {}).get("greenfieldDebugFlag", "").lower()
        return greenfield_flag == "enable"


class SwitchUtils:
    """
    Helper class for managing switch operations.

    This class provides methods to handle switch wait operations.
    """

    def __init__(self, nd, wait_payload, logger=None):
        self.class_name = self.__class__.__name__
        self.nd = nd
        self.log = logger or logging.getLogger(f"nd.{self.class_name}")
        self.wait_payload = wait_payload
        self.fabric = self.wait_payload["fabric"]
        self.switch_sns = self.wait_payload["switchSerialNumbers"]
        self.max_attempts = self.wait_payload.get("maxAttempts", 300)
        self.check_interval = self.wait_payload.get("checkInterval", 5)
        self.path = f"/api/v1/manage/fabrics/{self.fabric}/switches"

        # Get fabric details for greenfield debug flag
        self.fabric_utils = FabricUtils(nd, logger)
        self.fabric_details = self.fabric_utils.get_fabric_details()
        self.greenfield_debug_enabled = self.fabric_utils.is_greenfield_debug_enabled()
        
        self.log.info(f"Monitoring {len(self.switch_sns)} switches for readiness: {self.switch_sns}")
        self.log.info(f"Greenfield debug flag enabled: {self.greenfield_debug_enabled}")

    def check_switches_state(self, switch_sns, switch_data, target_state):
        """Check if switches have reached the target state and remove them from monitoring"""
        remaining_switches = []
        
        for sn in switch_sns:
            switch_found = False
            self.log.debug(f"Checking switch {sn} for state {target_state}")
            for switch in switch_data:
                if switch.get("serialNumber") == sn:
                    discovery_status = switch.get("additionalData", {}).get("discoveryStatus", "").lower()
                    self.log.debug(f"Switch {sn} discovery status: {discovery_status}")
                    switch_found = True
                    if discovery_status == target_state:
                        self.log.info(f"Switch {sn} reached {target_state} state")
                    else:
                        remaining_switches.append(sn)
                    break
            
            if not switch_found:
                remaining_switches.append(sn)

        return remaining_switches

    def check_migration_mode(self, switch_sns, switch_data, required_mode):
        """
        Check if switches are still in migration mode.
        This check is performed first as switches enter migration mode even when 
        greenfield debug flag is enabled.
        
        Returns:
            list: Switch serial numbers still in migration mode
        """
        
        for sn in switch_sns:
            for switch in switch_data:
                if switch.get("serialNumber") == sn:
                    mode = switch["additionalData"]["systemMode"]
                    if mode == required_mode:
                        switch_sns.remove(sn)
                        self.log.debug(f"Switch {sn} still in migration mode")
                    break

        return switch_sns

    def trigger_rediscovery(self, switch_sns):
        """Trigger rediscovery for specified switches"""
        if not switch_sns:
            return
            
        self.log.info(f"Triggering rediscovery for switches: {switch_sns}")
        
        payload = {"switchIds": switch_sns}
        path = f"/api/v1/manage/fabrics/{self.fabric}/switchActions/rediscover"
        
        response = self.nd.request(path, method="POST", data=payload)
    
        self.log.info(f"Rediscovery triggered successfully for switches: {switch_sns}")


    def wait_for_switch_import(self):
        """
        Wait for switches to exit migration mode and become manageable.
        
        This method will poll the switch state until they are ready or the max attempts are reached.
        """
        self.log.info("Waiting for switches to exit migration mode and become manageable")

        attempt = 1
        pending_switches = self.switch_sns.copy()
        switch_state = "unreachable"
        check_migration = True
        migration_mode = "migration"
        switches_in_migration = self.switch_sns.copy()

        while attempt <= self.max_attempts and pending_switches and switch_state:
            self.log.debug(f"Checking switch migration status - attempt {attempt}/{self.max_attempts}")
            
            response = self.nd.request(self.path, method="GET")
            switch_data = response.get("switches")

            if not switch_data:
                msg = "No switch data found for Fabric"
                self.nd.fail(msg)

            if check_migration:
                self.log.debug(f"Switches still in migration mode: {switches_in_migration}, mode: {migration_mode}")
                switches_in_migration = self.check_migration_mode(switches_in_migration, switch_data, migration_mode)
                if not switches_in_migration:
                    if migration_mode != "normal":
                        migration_mode = "normal"
                        switches_in_migration = self.switch_sns.copy()
                        self.log.debug(f"Switches exited migrated mode: {switches_in_migration}")
                    else:
                        check_migration = False
                
                time.sleep((self.check_interval)*2)
                continue

            # If greenfield debug flag is enabled, we can skip reload detection
            if self.greenfield_debug_enabled:
                self.log.debug("Greenfield debug flag enabled, ready to continue")
                return True

            # If greenfield debug flag is disabled, wait for reload detection.
            # Each switch's discovery will show unreachable for a period before becoming ok due to reload.
            pending_switches = self.check_switches_state(pending_switches, switch_data, switch_state)

            if pending_switches:
                self.trigger_rediscovery(pending_switches)
                self.log.info(f"Switches still pending: {pending_switches}, waiting...")
                time.sleep((self.check_interval)*3.5)
            else:
                if switch_state == "ok":
                    time.sleep((self.check_interval)*4)
                    self.log.info("All switches are now manageable")
                    return True
                pending_switches = self.switch_sns.copy()
                switch_state = "ok"
            
            attempt += 1

        return False


# Error handler class for handling errors during Merge, Delete, 
# Override operations.
class SwitchOperationError(Exception):
    """Custom exception for switch operation conflicts and errors"""
    def __init__(self, message):
        super().__init__(message)


class GetHave:
    """
    Class to retrieve and process switch state information from Nexus Dashboard (ND).

    This class handles the retrieval of switch state information from the Nexus Dashboard
    API and processes the response into a list of SwitchModel objects.

    Attributes:
        class_name (str): Name of the class.
        log (Logger): Logger instance for this class.
        path (str): API endpoint path for switch information.
        verb (str): HTTP method used for the request (GET).
        switch_state (dict): Raw switch state data retrieved from ND.
        have (list): List of processed SwitchModel objects.
        nd: Nexus Dashboard instance for making API requests.

    Methods:
        refresh(): Fetches the current switch state from Nexus Dashboard.
        validate_nd_state(): Processes the switch state data into SwitchModel objects.
    """

    def __init__(self, nd, logger=None):
        self.class_name = self.__class__.__name__
        self.log = logger or logging.getLogger(f"nd.{self.class_name}")

        self.verb = "GET"
        self.switch_state = []
        self.poap_switch_state = []
        self.have_switches = []           # Normal switches
        self.have_poap_switches = []      # POAP configurations
        self.have_switches_dict = {
            "switches": [],
            "poap_switches": []
        }
        self.nd = nd
        self.fabric = nd.params["fabric"]
        self.state = nd.params["state"]
        self.query_poap = nd.params["query_poap"]

        msg = "ENTERED GetHave(): "
        self.log.debug(msg)

    def refresh(self):
        """
        Refreshes the switch state by fetching the latest data from the ND API.

        This method updates the internal switch_state attribute with fresh data
        retrieved from the network controller using the configured path and HTTP verb.

        Returns:
            None: Updates the self.switch_state attribute directly.
        """
        self.class_name = self.__class__.__name__
        method_name = inspect.stack()[0][3]  # pylint: disable=unused-variable

        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        get_switches = SwitchesQuery()
        get_switches.fabric_name = self.fabric

        response = self.nd.request(get_switches.path, method=get_switches.verb)
        self.switch_state = response.get("switches")

        if self.query_poap:
            self.path = "/appcenter/cisco/ndfc/api/v1/lan-fabric/rest/control/fabrics/AK-Test/inventory/poap"
            response = self.nd.request(self.path, method=self.verb)
            self.poap_switch_state = response

        self.log.debug("Fabric's Switch Data retrieved: %s", self.switch_state)

    def process_validate_nd_data(self) -> list[dict]:
        """
        Validate and transform raw switch data from ND API into the required format.
            
        Returns:
            list[dict]: List of validated and flattened switch configurations
            
        Raises:
            ValueError: If validation fails
            
        Example:
            >>> ND_Data = [
            ...     {
            ...         "fabricManagementIp": "192.168.10.201",
            ...         "fabricName": "AK-ND4",
            ...         "hostname": "leaf1",
            ...         "model": "N9K-C9300v",
            ...         "serialNumber": "9ZCG8V03ENP",
            ...         "softwareVersion": "10.3(1)",
            ...         "switchRole": "leaf",
            ...         "additionalData": {
            ...             "discoveryStatus": "ok",
            ...             "systemMode": "normal"
            ...         }
            ...     }
            ... ]
            >>> validated = HaveSwitchConfigList.from_nested_list(ND_Data)
        """
        if self.switch_state:
            try:
                validated_config = HaveSwitchConfigList.from_nested_list(self.switch_state)
            except Exception as e:
                msg = f"Validation failed for ND switch configuration: {str(e)}"
                self.log.error(msg)
                self.nd.fail_json(msg=msg, exception=str(e), traceback=traceback.format_exc())
            if self.state == "query":
                self.have_switches = self.switch_state
            else:
                for switch in validated_config.switches:
                    switch_dict = switch.model_dump()
                    self.have_switches.append(switch_dict)
                    self.log.debug("Switch : %s", switch_dict)
        if self.poap_switch_state:
            try:
                validated_poap_config = HaveSwitchConfigList.from_nested_list(self.poap_switch_state)
            except Exception as e:
                msg = f"Validation failed for ND Poap switch configuration: {str(e)}"
                self.log.error(msg)
                self.nd.fail_json(msg=msg, exception=str(e), traceback=traceback.format_exc())
        
        self.have_switches_dict["switches"] = self.have_switches
        self.have_switches_dict["poap_switches"] = self.poap_switch_state

    def has_any_switches(self):
        """
        Check if there are any switches configured.
        
        Returns:
            bool: True if any switches are configured
        """
        return bool(self.have_switches)

    def get_all_switches(self):
        """
        Get all switches across all categories.
        
        Returns:
            dict: Dictionary containing all switch types
        """
        return self.have_switches_dict

    def get_switch_counts(self):
        """
        Get counts of different switch types.
        
        Returns:
            dict: Dictionary with counts for each switch type
        """
        return {
            "normal": len(self.have_switches),
            "poap": len(self.poap_switch_state),
            "total": len(self.have_switches) + len(self.poap_switch_state)
        }

class GetWant:
    """
    Class to retrieve and process switch state information from configuration (ND).

    This class handles the validation of switch state information from the input configuration 
    and processes the response into different types of switch configurations:
    - Normal switch configurations
    - POAP (PowerOn Auto Provisioning) configurations
    - RMA (Return Material Authorization) configurations

    Attributes:
        class_name (str): Name of the class.
        log (Logger): Logger instance for this class.
        switch_state_want (list): Raw switch configuration from input
        config_state (str): The state operation (merged, deleted, etc.)
        nd: Nexus Dashboard instance for making API requests.
        fabric (str): Target fabric name
        want_switches (list): List of processed normal switch configurations
        want_poap_switches (list): List of processed POAP configurations
        want_rma_switches (list): List of processed RMA configurations
        switch_ip_role_map (dict): Mapping of switch IPs to their configurations
    """

    def __init__(self, nd, logger=None):
        self.class_name = self.__class__.__name__
        self.log = logger or logging.getLogger(f"nd.{self.class_name}")

        self.verb = ""
        self.switch_state_want = nd.params.get("config")
        self.config_state = nd.params.get("state")
        self.nd = nd
        self.fabric = nd.params.get("fabric")
        
        # Different types of switch configurations
        self.want_switches = []           # Normal switches
        self.want_poap_switches = []      # POAP configurations
        self.want_rma_switches = []       # RMA configurations
        
        self.want_snos = []
        self.switch_config_map = {}
        self.input_validation = []
        self.validated_switches = []
        
        # Configuration type flags
        self.has_normal_switches = False
        self.has_poap_switches = False
        self.has_rma_switches = False

        msg = "ENTERED GetWant(): "
        self.log.debug(msg)

    def validate_input_state(self):
        """
        Validates the input switch state configuration and categorizes switches by type.
        
        This method processes different types of switch configurations:
        - Normal switch management (add/delete/query regular switches)
        - POAP configurations (bootstrap/pre-provision switches)
        - RMA configurations (replace existing switches)
        
        Returns:
            None
        """
        self.class_name = self.__class__.__name__
        method_name = inspect.stack()[0][3]

        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        if not self.switch_state_want:
            return

        # Handle delete and query operations (simple IP validation)
        if self.config_state in ["deleted", "query"]:
            self.validate_simple_switch_operations()
        else:
            # Handle merged/overridden operations (full configuration validation)
            self.validate_complex_switch_operations()

    def validate_simple_switch_operations(self):
        """Validate switch configurations for delete and query operations."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        try:
            self.input_validation = WantSwitchIPList(switches=self.switch_state_want)
            self.has_normal_switches = True
            
        except Exception as e:
            msg = f"Switch IP validation failed: {str(e)}"
            self.log.error(msg)
            self.nd.fail_json(msg=msg, exception=str(e), traceback=traceback.format_exc())

        self.log.debug(f"Switch IP validation passed: {self.input_validation.switches}")
        
        for switch in self.input_validation.switches:
            switch_dict = switch.model_dump()
            self.log.debug("Adding switch to want list: %s", switch_dict.get("ip"))
            self.want_switches.append(switch_dict)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def validate_complex_switch_operations(self):
        """Validate switch configurations for merged and overridden operations."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        # First, categorize switches by configuration type
        self.categorize_switch_configurations()
        
        # Validate each category separately
        if self.has_normal_switches:
            self.validate_normal_switches()
        
        if self.has_poap_switches:
            self.validate_poap_switches()
        
        if self.has_rma_switches:
            self.validate_rma_switches()
        
        # Perform discovery validation for normal switches
        if self.has_normal_switches:
            self.validate_discovery()
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def categorize_switch_configurations(self):
        """Categorize switch configurations into normal, POAP, and RMA types."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        normal_switches = []
        poap_switches = []
        rma_switches = []
        
        for switch_config in self.switch_state_want:
            # Check if this switch has POAP configuration
            if 'poap' in switch_config and switch_config['poap']:
                poap_switches.append(switch_config)
                self.has_poap_switches = True
                self.log.debug(f"Categorized switch {switch_config.get('seed_ip')} as POAP")
            
            # Check if this switch has RMA configuration
            elif 'rma' in switch_config and switch_config['rma']:
                rma_switches.append(switch_config)
                self.has_rma_switches = True
                self.log.debug(f"Categorized switch {switch_config.get('seed_ip')} as RMA")
            
            # Otherwise, it's a normal switch configuration
            else:
                normal_switches.append(switch_config)
                self.has_normal_switches = True
                self.log.debug(f"Categorized switch {switch_config.get('seed_ip')} as normal")
        
        # Store categorized configurations
        self.normal_switch_configs = normal_switches
        self.poap_switch_configs = poap_switches
        self.rma_switch_configs = rma_switches
        
        msg = f"Categorized switches - Normal: {len(normal_switches)}, POAP: {len(poap_switches)}, RMA: {len(rma_switches)}"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def validate_normal_switches(self):
        """Validate normal switch configurations."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        if not self.normal_switch_configs:
            return
        
        try:
            # Validate normal switch configurations
            self.input_validated_switches = InputSwitchConfigurationList(switches=self.normal_switch_configs)
            
            for switch in self.input_validated_switches.switches:
                switch_dict = switch.model_dump()
                self.log.debug("Adding normal switch to validated list: %s", switch_dict.get("ip"))
                
                # Build config mapping for normal switches
                discover_config = {
                    "switchRole": switch_dict.get("switchRole").lower(),
                    "username": switch_dict.get("username"),
                    "password": switch_dict.get("password"),
                    "platformType": switch_dict.get("platformType"),
                    "snmpV3AuthProtocol": switch_dict.get("snmpV3AuthProtocol"),
                    "preserveConfig": switch_dict.get("preserveConfig")
                }
            
                # Store both the switch dict and role mapping
                self.switch_config_map[switch_dict.get("ip")] = discover_config
                
                # Store the validated switch dict instead of Pydantic object
                self.validated_switches.append(switch_dict)
                
        except Exception as e:
            msg = f"Normal switch configuration validation failed: {str(e)}"
            self.log.error(msg)
            self.nd.fail_json(msg=msg, exception=str(e), traceback=traceback.format_exc())
        
        msg = f"Validated {(self.validated_switches)} normal switches"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def validate_poap_switches(self):
        """Validate POAP switch configurations."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        if not self.poap_switch_configs:
            return
        
        try:
            # Validate POAP switch configurations using enhanced model
            poap_validation = InputSwitchConfigurationListWithPOAP(switches=self.poap_switch_configs)
            self.want_poap_switches = poap_validation.get_merged_configs()

            self.log.debug(f"Added POAP switch {self.want_poap_switches}")
                
        except Exception as e:
            msg = f"POAP switch configuration validation failed: {str(e)}"
            self.log.error(msg)
            self.nd.fail_json(msg=msg, exception=str(e), traceback=traceback.format_exc())
        
        msg = f"Validated {len(self.want_poap_switches)} POAP configurations"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def validate_rma_switches(self):
        """Validate RMA switch configurations."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        if not self.rma_switch_configs:
            return
        
        try:
            # Validate RMA switch configurations using enhanced model
            rma_validation = InputSwitchConfigurationListWithPOAP(switches=self.rma_switch_configs)
            
            for switch in rma_validation.switches:
                switch_dict = switch.model_dump()
                self.log.debug("Processing RMA switch: %s", switch_dict.get("ip"))
                
                # Process each RMA configuration for this switch
                if switch_dict.get("rma"):
                    for rma_config in switch_dict["rma"]:
                        # Create an RMA switch entry
                        rma_switch = {
                            "ip": switch_dict.get("ip"),
                            "username": switch_dict.get("username"),
                            "password": switch_dict.get("password"),
                            "platformType": switch_dict.get("platformType"),
                            "snmpV3AuthProtocol": switch_dict.get("snmpV3AuthProtocol"),
                            "switchRole": switch_dict.get("switchRole"),
                            "preserveConfig": switch_dict.get("preserveConfig"),
                            "rma_config": rma_config,
                            "operation_type": "rma"
                        }
                        
                        self.want_rma_switches.append(rma_switch)
                        self.log.debug(f"Added RMA switch {switch_dict.get('ip')} replacing {rma_config['old_serial']}")
                
        except Exception as e:
            msg = f"RMA switch configuration validation failed: {str(e)}"
            self.log.error(msg)
            self.nd.fail_json(msg=msg, exception=str(e), traceback=traceback.format_exc())
        
        msg = f"Validated {len(self.want_rma_switches)} RMA configurations"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def validate_discovery(self):
        """
        Validates the discovery state by extracting switch information for normal switches only.
        
        Note: POAP and RMA switches follow different workflows and don't require
        traditional discovery validation.

        Returns:
            None
        """
        self.class_name = self.__class__.__name__
        method_name = inspect.stack()[0][3]

        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        if not self.validated_switches:
            msg = "No normal switches to validate discovery for"
            self.log.debug(msg)
            return

        # Define the grouping keys
        payload_grouping_keys = ['password', 'platformType', 'snmpV3AuthProtocol', 'username']
            
        # Define the switch-specific keys (to be moved to switches array)
        payload_switch_keys = ['ip']
        ip_key = 'seedIpCollection'
        
        msg = "validated_switches: %s" % self.validated_switches
        self.log.debug(msg)

        shallow_discovery = ShallowDiscovery()
        shallow_discovery.fabric_name = self.fabric

        # Build the payload for shallow discovery
        payload_list = PayloadUtils.group_switches_build_payload(
            self.validated_switches, 
            payload_grouping_keys, 
            payload_switch_keys, 
            ip_key
        )

        for payload in payload_list:
            payload.update({"maxHop": 0})
            self.log.debug("Requesting discovery for switches: %s", payload)
            response = self.nd.request(shallow_discovery.path, method=shallow_discovery.verb, data=payload)
            msg = "Discovery response: %s" % response
            self.log.debug(msg)
            
            try:
                ValidatedDiscoveredSwitch = DiscoveredSwitchList(switches=response.get("switches"))
                for switch in ValidatedDiscoveredSwitch.switches:
                    switch_dict = switch.model_dump()
                    
                    # Idempotence Won't Work
                    # Validate switch manageability
                    # if switch_dict.get("statusReason") != "manageable":
                    #     if self.config_state == "overridden" and "already managed" in switch_dict.get("statusReason", ""):
                    #         msg = f"Switch {switch_dict['ip']} is already managed and will be overridden in {self.fabric}."
                    #         self.log.debug(msg)
                    #     else:
                    #         msg = f"Switch {switch_dict['ip']} is: {switch_dict['statusReason']}"
                    #         self.log.error(msg)
                    #         self.nd.fail_json(msg=msg)
                    
                    # Update switch with input information
                    switch_config = self.switch_config_map.get(switch_dict["ip"], {})
                    enhanced_switch = {
                        **switch_dict,
                        **switch_config
                    }            
                    
                    self.log.debug("Adding normal switch to want list: %s", switch_dict.get("ip"))
                    self.want_switches.append(enhanced_switch)
                    self.log.debug(f"Want_Switches: {self.want_switches}")
                    self.want_snos.append(switch_dict.get("ip"))
                    
            except ValidationError as e:
                msg = f"Validation error occurred while processing discovered switches: {str(e)}"
                self.log.error(msg)
                self.nd.fail_json(msg=msg, exception=str(e), traceback=traceback.format_exc())

        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def get_all_switches(self):
        """
        Get all switches across all categories.
        
        Returns:
            dict: Dictionary containing all switch types
        """
        return {
            "normal": self.want_switches,
            "poap": self.want_poap_switches,
            "rma": self.want_rma_switches
        }

    def get_switch_counts(self):
        """
        Get counts of different switch types.
        
        Returns:
            dict: Dictionary with counts for each switch type
        """
        return {
            "normal": len(self.want_switches),
            "poap": len(self.want_poap_switches),
            "rma": len(self.want_rma_switches),
            "total": len(self.want_switches) + len(self.want_poap_switches) + len(self.want_rma_switches)
        }

    def has_any_switches(self):
        """
        Check if there are any switches configured.
        
        Returns:
            bool: True if any switches are configured
        """
        return bool(self.want_switches or self.want_poap_switches or self.want_rma_switches)

    def log_validation_summary(self):
        """Log a summary of the validation results."""
        counts = self.get_switch_counts()
        
        msg = f"Switch validation summary - Normal: {counts['normal']}, POAP: {counts['poap']}, RMA: {counts['rma']}, Total: {counts['total']}"
        self.log.info(msg)
        
        if self.has_poap_switches:
            poap_operations = {}
            for switch in self.want_poap_switches:
                op_type = switch.get("operation_type", "unknown")
                poap_operations[op_type] = poap_operations.get(op_type, 0) + 1
            
            msg = f"POAP operations breakdown: {poap_operations}"
            self.log.info(msg)

class Common:
    """
    Enhanced Common utility class that provides shared functionality for all state operations 
    in the Cisco ND switch management, now including POAP and RMA operations.

    This class handles the core logic for processing switch configurations across different operational states
    (merged, deleted, overridden, query) for normal switches, POAP configurations, and RMA operations.

    Attributes:
        result (dict): Dictionary to store operation results including changed state, diffs, API responses and warnings.
        task_params (dict): Parameters provided from the Ansible task.
        state (str): The desired state operation (merged, replaced, deleted, overridden, or query).
        requests (dict): Container for API request operations.
        have (list): List of switch objects representing the current state of switches.
        want_switches (dict): Dictionary containing different types of switch configurations.
        fabric (str): Name of the fabric being managed.
        diff_result (dict): Result of DeepDiff comparison between have and want states.
    """

    def __init__(self, task_params=None, have_state=None, want_state=None, logger=None):
        self.class_name = self.__class__.__name__
        method_name = inspect.stack()[0][3]
        
        self.log = logger or logging.getLogger(f"nd.{self.class_name}")

        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        self.result = dict(changed=False, diff=[], response=[], warnings=[])
        self.task_params = task_params
        self.state = task_params["state"]
        self.requests = {}
        self.fabric = task_params.get("fabric")

        self.have = have_state.get_all_switches()
        self.have_switches = self.have.get("switches")
        self.want_switches = want_state.get_all_switches()

        # Separate different types of switch configurations
        self.want_normal_switches = self.want_switches.get("normal", [])
        self.want_poap_switches = self.want_switches.get("poap", [])
        self.want_rma_switches = self.want_switches.get("rma", [])

        # Track different operations needed
        self.normal_switches_to_add = []
        self.normal_switches_to_remove = []
        self.poap_switches_to_process = []
        self.rma_switches_to_process = []
        
        self.diff_result = {}

        msg = f"Initializing Common with state: {self.state}, fabric: {self.fabric}"
        self.log.info(msg)

        self.comparison_keys_exclude = []

        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def create_switch_index(self, switches):
        """
        Create an index of switches by IP address for fast lookup.
        
        Args:
            switches (list): List of switch dictionaries
            
        Returns:
            dict: Dictionary indexed by IP address
        """
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name} with {len(switches)} switches"
        self.log.debug(msg)
        
        index = {}
        for switch in switches:
            try:
                compare_switch = CompareSwitchConfig(**switch)
                ip = compare_switch.ip
                normalized_data = compare_switch.model_dump()
                index[ip] = {"normalized_sw": normalized_data, "original_sw": switch}
                self.log.debug(f"Added switch {ip} to index")
            except Exception as e:
                msg = f"Failed to create CompareSwitchConfig for switch {switch}: {e}"
                raise SwitchOperationError(msg)

        msg = f"Created index with {len(index)} switches: {list(index.keys())}"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        return index

    def calculate_diff(self):
        """
        Calculate the differences between have and want states for all switch types.
        
        This operation determines all the changes needed across different states by
        comparing each switch dictionary based on IP address and processing different
        types of switch configurations (normal, POAP, RMA).
        """
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        msg = f"Have state: {len(self.have_switches)} switches, Want state: Normal={len(self.want_normal_switches)}, POAP={len(self.want_poap_switches)}, RMA={len(self.want_rma_switches)}"
        self.log.info(msg)

        # Create indexed version of have switches comparison
        have_index = self.create_switch_index(self.have_switches)
        self.log.debug(f"Have switches: {list(have_index.keys())}")

        if self.want_normal_switches:
            want_normal_index = self.create_switch_index(self.want_normal_switches)
            self.log.debug(f"Want normal switches: {list(want_normal_index.keys())}")
            self.calculate_normal_switches_diff(have_index, want_normal_index)

        if self.want_poap_switches:
            want_poap_index = self.create_switch_index(self.want_poap_switches)
            self.log.debug(f"Want poap switches: {list(want_poap_index.keys())}")
            self.calculate_poap_diff(have_index, want_poap_index)

        if self.want_rma_switches:
            want_rma_index = self.create_switch_index(self.want_rma_switches)
            self.log.debug(f"Want rma switches: {list(want_rma_index.keys())}")
            self.calculate_rma_switches_diff(have_index, want_rma_index)

        # Log summary of all changes
        self.log_diff_summary()
            
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def update_keys_to_compare(self, keys_to_include):
        """Get keys to exclude based on operation state and context."""

        base_keys = ['ip', 'switchRole', 'serialNumber', 'hostname', 'model', 'softwareVersion']

        compare_keys = list(set(base_keys) - set(keys_to_include))

        return compare_keys

    def exclude_keys_diff(self, obj, path):
        """
        Callback function for DeepDiff to exclude certain keys from comparison.
        
        Args:
            obj: The object being compared
            path: The path to the object in the comparison
            
        Returns:
            bool: True if the object should be excluded from comparison
        """
        
        # Check if the path contains any of the keys to exclude
        if hasattr(path, 't1') and hasattr(path, 't2'):
            # This is for handling the path object from DeepDiff
            path_str = str(path)
        else:
            path_str = str(path)
        
        return any(key in path_str for key in self.comparison_keys_exclude)

    def check_switch_conflicts(self, have_index, want_index):
        """
        Check for conflicting switches between the 'have' and 'want' states.

        Args:
            have_index: The indexed representation of the 'have' state switches
            want_index: The indexed representation of the 'want' state switches

        Returns:
            list: A list of DeepDiff objects representing the differences for each conflicting switch
        """
        common_switches = set(have_index.keys()) & set(want_index.keys())
        switch_diff_list = []
        
        for ip in common_switches:
            have_switch_normalized = have_index[ip]['normalized_sw']
            want_switch_normalized = want_index[ip]['normalized_sw']
            if self.state == "deleted" or self.state == "query":
                if want_switch_normalized.get("switchRole"):
                    keys_to_include = ['ip', 'switchRole']
                    self.comparison_keys_exclude = self.update_keys_to_compare(keys_to_include)
                else:
                    keys_to_include = ['ip']
                    self.comparison_keys_exclude = self.update_keys_to_compare(keys_to_include)
            # Calculate diff for this specific switch
            switch_diff = DeepDiff(
                have_switch_normalized,
                want_switch_normalized,
                ignore_order=True,
                verbose_level=2,
                exclude_obj_callback=self.exclude_keys_diff
            )
            self.log.debug(f"Switch diff for {ip}: {switch_diff}")
            if switch_diff:
                switch_diff_list.append(ip)

        return switch_diff_list

    def calculate_normal_switches_diff(self, have_index, want_index):
        """Calculate differences for normal switch configurations."""
        method_name = inspect.stack()[0][3]
        # Initialize diff result structure for normal switches
        self.diff_result['normal_switches'] = {
            'switch_add': [],
            'switch_remove': [],
            'switch_update': []
        }

        # First check for conflicting switches and differences
        # Find switches that exist in both have and want and calculate individual diffs
        conflict_switches = self.check_switch_conflicts(have_index, want_index)
        self.log.debug(f"Conflict switches found: {conflict_switches}")
        if conflict_switches:
            if self.state != "overridden":
                msg = f"Switch(es) in playbook has conflicting state(s)."
                raise SwitchOperationError(msg)
            else:
                for switch_ip in conflict_switches:
                    # If there are differences in overridden state, 
                    # remove and add the switch back in the Fabric.
                    have_switch_original = have_index[switch_ip]['original_sw']
                    want_switch_original = want_index[switch_ip]['original_sw']
                    self.normal_switches_to_remove.append(have_switch_original)
                    self.normal_switches_to_add.append(want_switch_original)
                    self.log.debug(f"Normal switch {switch_ip} prepared for override")
                    self.diff_result['normal_switches']['switch_update'].append(switch_ip)

        if self.state == "merged" or self.state == "overridden":
            # Find normal switches to add (in want but not in have)
            switches_to_add = set(want_index.keys()) - set(have_index.keys())
            for ip in switches_to_add:
                want_switch_original = want_index[ip]['original_sw']
                self.normal_switches_to_add.append(want_switch_original)
                self.diff_result['normal_switches']['switch_add'].append(ip)
                self.log.debug(f"Normal switch {ip} marked for addition")

        if self.state == "deleted" or self.state == "overridden":
            # Find normal switches to remove
            if not want_index and self.state == "deleted":
                # Delete all switches if no want state specified
                want_index = have_index

            if self.state == "overridden":
                switches_to_delete = set(have_index.keys()) - set(want_index.keys())
            elif self.state == "deleted":
                switches_to_delete = set(want_index.keys())
                if not (set(want_index.keys()) & set(have_index.keys()) == set(want_index.keys())):
                    msg = "Cannot delete switch(es) that are not in the fabric."
                    raise SwitchOperationError(msg)

            for ip in switches_to_delete:
                have_switch_original = have_index[ip]['original_sw']
                self.normal_switches_to_remove.append(have_switch_original)
                self.diff_result['normal_switches']['switch_remove'].append(ip)
                self.log.debug(f"Normal switch {ip} marked for removal")

        msg = f"Normal switches diff - Add: {len(self.normal_switches_to_add)}, Remove: {len(self.normal_switches_to_remove)}"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def calculate_poap_diff(self, have_index, want_index):
        """Calculate differences for POAP switch configurations."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        self.diff_result['poap_switches'] = {
            'switches_to_preprovision': [],
        }

        # First check for conflicting switches and differences
        # Find switches that exist in both have and want and calculate individual diffs
        conflict_switches = self.check_switch_conflicts(have_index, want_index)

        if conflict_switches:
            for switch_ip in conflict_switches:
                msg = f"POAP Switch {switch_ip} has conflicts in the Fabric"
                raise SwitchOperationError(msg)

        for poap_switch in self.want_poap_switches:
            switch_ip = poap_switch.get("ip")
            self.poap_switches_to_process.append(poap_switch)
            self.diff_result['poap_switches']['switches_to_preprovision'].append(switch_ip)


        msg = f"POAP switches to process: {self.poap_switches_to_process}"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def calculate_rma_switches_diff(self):
        """Calculate differences for RMA switch configurations."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        if not self.want_rma_switches:
            msg = "No RMA switches to process"
            self.log.debug(msg)
            return

        # RMA switches are always processed (replacement operations)
        # Validate that old switches exist in the current state
        self.diff_result['rma_switches'] = {
            'switches_to_replace': []
        }

        have_serials = {switch.get("serialNumber") for switch in self.have_switches if switch.get("serialNumber")}
        
        for rma_switch in self.want_rma_switches:
            rma_config = rma_switch.get("rma_config", {})
            old_serial = rma_config.get("old_serial")
            new_serial = rma_config.get("serial_number")
            switch_ip = rma_switch.get("ip")
            
            # Validate that the old switch exists
            if old_serial not in have_serials:
                msg = f"RMA operation failed: Old switch with serial {old_serial} not found in fabric"
                raise SwitchOperationError(msg)

            self.diff_result['rma_switches']['switches_to_replace'].append(switch_ip)
            self.log.debug(f"RMA switch {switch_ip} marked for replacement (old: {old_serial}, new: {new_serial})")
            self.rma_switches_to_process.append(rma_switch)

        msg = f"RMA switches to process: {len(self.rma_switches_to_process)}"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def log_diff_summary(self):
        """Log a comprehensive summary of all diff calculations."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        total_changes = 0
        
        # Normal switches summary
        if 'normal_switches' in self.diff_result:
            normal_add = len(self.diff_result['normal_switches'].get('switch_add', []))
            normal_remove = len(self.diff_result['normal_switches'].get('switch_remove', []))
            normal_update = len(self.diff_result['normal_switches'].get('switch_update', []))
            total_changes += normal_add + normal_remove + normal_update
            
            msg = f"Normal switches - Add: {normal_add}, Remove: {normal_remove}, Update: {normal_update}"
            self.log.info(msg)
        
        # POAP switches summary
        if 'poap_switches' in self.diff_result:
            # poap_bootstrap = len(self.diff_result['poap_switches'].get('switches_to_bootstrap', []))
            poap_preprovision = len(self.diff_result['poap_switches'].get('switches_to_preprovision', []))
            # poap_swap = len(self.diff_result['poap_switches'].get('switches_to_swap', []))
            total_changes += poap_preprovision 
            
            msg = f"POAP switches - Preprovision: {poap_preprovision}"
            self.log.info(msg)
        
        # RMA switches summary
        if 'rma_switches' in self.diff_result:
            rma_replace = len(self.diff_result['rma_switches'].get('switches_to_replace', []))
            total_changes += rma_replace
            
            msg = f"RMA switches - Replace: {rma_replace}"
            self.log.info(msg)
        
        msg = f"Total changes across all switch types: {total_changes}"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def get_normal_switches_to_add(self):
        """Returns the list of normal switches that need to be added."""
        return self.normal_switches_to_add

    def get_normal_switches_to_delete(self):
        """Returns the list of normal switches that need to be deleted."""
        return self.normal_switches_to_remove

    def get_poap_switches_to_process(self):
        """Returns the list of POAP switches that need to be processed."""
        return self.poap_switches_to_process

    def get_rma_switches_to_process(self):
        """Returns the list of RMA switches that need to be processed."""
        return self.rma_switches_to_process

    def has_changes(self):
        """
        Check if there are any changes needed based on the diff.
        
        Returns:
            bool: True if changes are needed, False otherwise
        """
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        has_normal_changes = bool(self.normal_switches_to_add or self.normal_switches_to_remove)
        has_poap_changes = bool(self.poap_switches_to_process)
        has_rma_changes = bool(self.rma_switches_to_process)
        
        has_changes = has_normal_changes or has_poap_changes or has_rma_changes
        
        msg = f"Changes detected - Normal: {has_normal_changes}, POAP: {has_poap_changes}, RMA: {has_rma_changes}, Total: {has_changes}"
        self.log.debug(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        return has_changes

    def build_list_payload(self, switches_list, payload_key, payload_val):
        """
        Builds a list payload for API requests.
        
        Args:
            switches_list (list): List of switch dictionaries
            payload_key (str): Key name for the IP collection in payload
            payload_val (str): Value to associate with the payload key

        Returns:
            list: List of payload dictionaries
        """
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name} with {len(switches_list)} switches"
        self.log.debug(msg)

        payload_values = []

        for switch in switches_list:
            payload_values.append(switch.get(payload_val))
        
        payload = {payload_key: payload_values}

        msg = f"Built {payload} payload"
        self.log.info(msg)

        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        return payload

    # def build_api_path(self, operation_type, switch_id=None):
    #     """
    #     Build API paths for different operations including POAP and RMA.
        
    #     Args:
    #         operation_type (str): Type of operation
    #         switch_id (str, optional): Switch ID for specific operations
            
    #     Returns:
    #         str: API path for the operation
    #     """
    #     method_name = inspect.stack()[0][3]
        
    #     msg = f"ENTERED: {self.class_name}.{method_name} for operation: {operation_type}"
    #     self.log.debug(msg)
        
    #     base_path = f"/api/v1/manage"
    #     fabric_path = f"fabrics/{self.fabric}"
        
    #     path_mapping = {
    #         # Normal switch operations
    #         "add_switches": f"{base_path}/{fabric_path}/switches",
    #         "shallow_discover_switches": f"{base_path}/{fabric_path}/actions/shallowDiscovery",
    #         "rediscover_switches": f"{base_path}/{fabric_path}/switchActions/rediscover",
    #         "save_switch_credentials": f"{base_path}/credentials/switches",
    #         "delete_switches": f"{base_path}/{fabric_path}/switchActions/remove",
    #         "save_fabric_config": f"{base_path}/{fabric_path}/actions/configSave",
    #         "deploy_switch_config": f"{base_path}/{fabric_path}/switchActions/deploy",
            
    #         # POAP operations
    #         "poap_bootstrap": f"{base_path}/{fabric_path}/bootstrapSwitches",
    #         "poap_query": f"{base_path}/{fabric_path}/poap/available",
            
    #         # RMA operations
    #         "rma_replace": f"{base_path}/{fabric_path}/rma/replace",
    #     }
        
    #     api_path = path_mapping.get(operation_type)
        
    #     if api_path:
    #         self.log.debug(f"Built API path for {operation_type}: {api_path}")
    #     else:
    #         self.log.error(f"Unknown operation type: {operation_type}")
        
    #     msg = f"EXITED: {self.class_name}.{method_name}"
    #     self.log.debug(msg)
        
    #     return api_path

    def create_request_entry(self, verb, path, payload=None, request_key=None):
        """
        Create standardized request entries for self.requests.
        
        Args:
            verb (str): HTTP verb (GET, POST, PUT, DELETE, WAIT)
            path (str): API endpoint path
            payload (dict, optional): Request payload
            request_key (str, optional): Key for the request in self.requests
            
        Returns:
            str: The request key used
        """
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        request_key = request_key or f"{verb.lower()}_{len(self.requests)}"
        
        self.requests[request_key] = {
            "verb": verb,
            "path": path,
            "payload": payload or {}
        }
        
        msg = f"Created request '{request_key}': {verb} {path}"
        self.log.debug(msg)
        
        if payload:
            self.log.debug(f"Request payload size: {len(str(payload))} characters")
        
        msg = f"EXITED: {self.class_name}.{method_name} - key: {request_key}"
        self.log.debug(msg)
        
        return request_key

class Merged:
    """
    Enhanced Merged state handler for normal switches, POAP, and RMA operations.
    
    In merged state:
    - Add normal switches that don't exist
    - Process POAP configurations (bootstrap/preprovision/swap)
    - Process RMA configurations (replace existing switches)
    """

    def __init__(self, task_params, have_state, want_state, logger=None, common_util=None):
        self.class_name = self.__class__.__name__
        method_name = inspect.stack()[0][3]
        
        self.log = logger or logging.getLogger(f"nd.{self.class_name}")

        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        # Get switch counts for logging
        counts = want_state.get_switch_counts()
        msg = f"Initializing Merged state"
        self.log.info(msg)
        msg = f"Want state: Normal={counts['normal']}, POAP={counts['poap']}, RMA={counts['rma']}, Total={counts['total']}"
        self.log.info(msg)

        # Initialize different switch operation lists
        self.normal_switches_to_add = []
        self.poap_switches_to_process = []
        self.rma_switches_to_process = []

        if not want_state.has_any_switches():
            msg = "No switches to merge. Exiting."
            self.log.info(msg)
            return
        
        if common_util:
            self.common = common_util
        else:
            self.common = Common(task_params, have_state, want_state, logger)
        
            # Perform diff calculations for different switch types
            self.common.calculate_diff()
        
        msg = f"Common diff calculation completed. Changes detected: {self.common.has_changes()}"
        self.log.info(msg)

        # Get different types of switches to process
        self.normal_switches_to_add = self.common.get_normal_switches_to_add()
        self.poap_switches_to_process = self.common.get_poap_switches_to_process()
        self.rma_switches_to_process = self.common.get_rma_switches_to_process()

        self.fabric = self.common.fabric
        self.deploy = task_params.get("deploy")
        self.save = task_params.get("save")

        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def process_merged_request(self):
        """Prepare requests for all types of switch operations in merged state."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        # Process normal switches
        if self.normal_switches_to_add:
            msg = f"Preparing to add {len(self.normal_switches_to_add)} normal switches"
            self.log.info(msg)
            self.process_normal_switches()
        
        # Process POAP switches
        if self.poap_switches_to_process:
            msg = f"Preparing to process {len(self.poap_switches_to_process)} POAP switches"
            self.log.info(msg)
            self.process_poap_switches()
        
        # Process RMA switches
        if self.rma_switches_to_process:
            msg = f"Preparing to process {len(self.rma_switches_to_process)} RMA switches"
            self.log.info(msg)
            self.process_rma_switches()

        if not (self.normal_switches_to_add or self.poap_switches_to_process or self.rma_switches_to_process):
            msg = "No switches to process in merged state. Exiting."
            self.log.info(msg)
            return

        msg = f"All switch operation requests prepared"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def process_normal_switches(self):
        """Process normal switch operations."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        # Prepare creation requests for normal switches
        self.prepare_normal_switch_add_requests()

        # Prepare wait requests to ensure switches are manageable
        self.prepare_normal_switch_wait_requests()

        # Prepare requests to save switch credentials
        self.prepare_normal_switch_credential_requests()

        if self.save:
            # Prepare requests to save fabric configuration
            self.prepare_config_save_requests()

        if self.deploy:
            # Prepare requests to deploy fabric configuration
            self.prepare_config_deploy_requests(self.normal_switches_to_add)

        msg = f"Normal switch requests prepared for {len(self.normal_switches_to_add)} switches"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def process_poap_switches(self):
        """Process POAP switch operations."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
    
        # Process each type of POAP operation
        if self.poap_switches_to_process:
            self.prepare_poap_preprovision_requests(self.poap_switches_to_process)

        msg = f"POAP requests prepared - {len(self.poap_switches_to_process)}"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def process_rma_switches(self):
        """Process RMA switch operations."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        # Prepare RMA replacement requests
        self.prepare_rma_replace_requests(self.rma_switches_to_process)

        msg = f"RMA requests prepared for {len(self.rma_switches_to_process)} switches"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def prepare_normal_switch_add_requests(self):
        """Prepare POST requests for adding normal switches."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        msg = f"Preparing add requests for {len(self.normal_switches_to_add)} normal switches"
        self.log.info(msg)

        # Group switches for bulk creation
        payload_grouping_keys = ['password', 'platformType', 'preserveConfig', 'snmpV3AuthProtocol', 'username']
        payload_switch_keys = ['hostname', 'ip', 'model', 'serialNumber', 'softwareVersion', 'switchRole']
        
        payloads = PayloadUtils.group_switches_build_payload(
            self.normal_switches_to_add, 
            payload_grouping_keys, 
            payload_switch_keys, 
            'switches'
        )
        
        add_switches = SwitchesAdd()
        add_switches.fabric_name = self.fabric
        
        for i, payload in enumerate(payloads):
            request_key = f"add_normal_switches_batch_{i}"
            self.common.create_request_entry(add_switches.verb, add_switches.path, payload, request_key)

            switch_count = len(payload.get('switches', []))
            msg = f"Normal switches batch {i+1}: {switch_count} switches queued for addition"
            self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name} - {len(payloads)} batches prepared"
        self.log.debug(msg)

    def prepare_normal_switch_credential_requests(self):
        """Prepare requests for saving normal switch credentials."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        add_switches = []

        for switch_data in self.normal_switches_to_add:
            switch_cred_data = switch_data.copy()
            switch_cred_data["switchUsername"] = switch_cred_data.pop("username")
            switch_cred_data["switchPassword"] = switch_cred_data.pop("password")
            switch_cred_data["switchId"] = switch_cred_data.get("serialNumber")
            add_switches.append(switch_cred_data)

        # Group switches for bulk credential saving
        payload_grouping_keys = ['switchPassword', 'switchUsername']
        payload_switch_keys = ['switchId']
        
        payloads = PayloadUtils.group_switches_build_payload(
            add_switches, 
            payload_grouping_keys, 
            payload_switch_keys, 
            'switchIds'
        )
        
        save_switch_cred = SaveSwitchCredentials()

        for i, payload in enumerate(payloads):
            request_key = f"save_normal_switch_cred_batch_{i}"
            self.common.create_request_entry(save_switch_cred.verb, save_switch_cred.path, payload, request_key)

            msg = f"Normal switches credentials batch {i+1} queued"
            self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name} - {len(payloads)} batches prepared"
        self.log.debug(msg)

    def prepare_normal_switch_wait_requests(self):
        """Prepare wait requests for normal switches to become manageable."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        switch_sns = [switch.get("serialNumber") for switch in self.normal_switches_to_add if switch.get("serialNumber")]

        if not switch_sns:
            msg = "No serial numbers found for normal switches wait request"
            self.log.warning(msg)
            return

        wait_payload = {
            "switchSerialNumbers": switch_sns,
            "fabric": self.fabric,
            "maxAttempts": 300,
            "checkInterval": 5,
            "checkMigrationMode": True,
            "checkManageableState": True
        }

        self.common.create_request_entry("WAIT", None, wait_payload, "wait_for_normal_switches_ready")

        msg = f"Wait request prepared for {len(switch_sns)} normal switches: {switch_sns}"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def prepare_poap_preprovision_requests(self, preprovision_switches):
        """Prepare requests for POAP preprovision operations."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        payload = {"switches": []}
        for poap_switch in preprovision_switches:
            payload["switches"].append(poap_switch)

        path = self.common.build_api_path("poap_bootstrap")
        request_key = f"poap_bootstrap"
            
        self.common.create_request_entry("POST", path, payload, request_key)

        msg = f"POAP bootstrap request prepared for switches"
        self.log.info(msg)

        msg = f"EXITED: {self.class_name}.{method_name} - {len(preprovision_switches)} bootstrap requests prepared"
        self.log.debug(msg)

    def prepare_rma_replace_requests(self, rma_switches):
        """Prepare requests for RMA replace operations."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        for i, rma_switch in enumerate(rma_switches):
            rma_config = rma_switch.get("rma_config", {})
            
            # Build RMA replace payload
            payload = {
                "oldSerial": rma_config.get("old_serial"),
                "newSerial": rma_config.get("serial_number"),
                "model": rma_config.get("model"),
                "version": rma_config.get("version"),
                "imagePolicy": rma_config.get("image_policy"),
                "configData": rma_config.get("config_data", {}),
                "discoveryAuthProtocol": "MD5",
                "discoveryUsername": rma_config.get("discovery_username", "admin"),
                "discoveryPassword": rma_config.get("discovery_password")
            }
            
            path = self.common.build_api_path("rma_replace")
            request_key = f"rma_replace_{i}"
            
            self.common.create_request_entry("POST", path, payload, request_key)
            
            msg = f"RMA replace request prepared: {payload.get('oldSerial')} -> {payload.get('newSerial')}"
            self.log.info(msg)

        msg = f"EXITED: {self.class_name}.{method_name} - {len(rma_switches)} RMA requests prepared"
        self.log.debug(msg)

    def prepare_config_save_requests(self):
        """Prepare requests to save configuration for specified switches."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        fabric_config_save = FabricConfigSave()
        fabric_config_save.fabric_name = self.fabric

        self.common.create_request_entry(fabric_config_save.verb, fabric_config_save.path, None, "save_fabric_config")

        msg = f"Configuration save request prepared for fabric"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def prepare_config_deploy_requests(self, switches):
        """Prepare requests to deploy configuration for specified switches."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        if not switches:
            return

        payload = {"switchIds": []}
        for switch in switches:
            switch_id = switch.get("serialNumber")
            if switch_id:
                payload["switchIds"].append(switch_id)
                self.log.debug(f"Switch SN {switch_id} queued for deployment")

        if not payload["switchIds"]:
            msg = "No valid switch IDs for config deploy request"
            self.log.warning(msg)
            return

        switch_deploy = SwitchDeploy()
        switch_deploy.fabric_name = self.fabric

        self.common.create_request_entry(switch_deploy.verb, switch_deploy.path, payload, "deploy_switch_config")

        msg = f"Configuration deploy request prepared for {len(payload['switchIds'])} switches"
        self.log.info(msg)
        
        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

class Deleted:
    """
    Handle deleted state operations using the common diff logic.
    
    In deleted state:
    - Remove switches that exist in the current state
    - Fail if switches do not exist in the current state
    """

    def __init__(self, task_params, have_state, want_state, logger=None, common_util=None):
        self.class_name = self.__class__.__name__
        method_name = inspect.stack()[0][3]
        
        self.log = logger or logging.getLogger(f"nd.{self.class_name}")

        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        msg = f"Initializing Deleted state"
        self.log.info(msg)

        self.switches_to_delete = []

        if not have_state:
            msg = "No switches existing in fabric to delete. Exiting."
            raise SwitchOperationError(msg)

        self.log.debug(f"want state {want_state}")

        if common_util:
            self.common = common_util
            self.switches_to_delete = self.common.get_normal_switches_to_delete()
        else:
            self.common = Common(task_params, have_state, want_state, logger)
    
            if not want_state.has_any_switches():
                # Delete all switches in Fabric
                all_switches = have_state.get_all_switches()
                self.switches_to_delete = all_switches.get("switches")
            else:
                # Perform diff calculations for different switch types
                self.common.calculate_diff()
                self.switches_to_delete = self.common.get_normal_switches_to_delete()
    
        self.fabric = self.common.fabric

        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def process_deleted_request(self):
        """Prepare DELETE requests for removing switches."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        if self.switches_to_delete:
            # Prepare deletion requests for new switches
            self.prepare_remove_requests()
        else:
            msg = "No switches to delete. Exiting."
            self.log.info(msg)
            return

        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def prepare_remove_requests(self):
        """
        Prepare DELETE requests for removing switches.
        Used by Deleted and Overridden states.
        """
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        payload = self.common.build_list_payload(self.switches_to_delete, "switchIds", "serialNumber")
        
        msg = f"Preparing remove requests for {len(self.switches_to_delete)} switches"
        self.log.info(msg)

        switch_remove = SwitchRemove()
        switch_remove.fabric_name = self.fabric
        request_key = f"delete_switches"
            
        self.common.create_request_entry(switch_remove.verb, switch_remove.path, payload, request_key)

        msg = f"EXITED: {self.class_name}.{method_name} delete requests prepared"
        self.log.debug(msg)

class Overridden:
    """
    Handle overridden state operations using the common diff logic.
    
    In overridden state:
    - Add switches that don't exist
    - Remove switches that exist but are not in the desired state
    - Update existing switches to match the desired configuration
    """

    def __init__(self, task_params, have_state, want_state, logger=None, common_util=None):
        self.class_name = self.__class__.__name__
        method_name = inspect.stack()[0][3]
        
        self.log = logger or logging.getLogger(f"nd.{self.class_name}")

        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)
        
        msg = f"Initializing Overridden state"
        self.log.info(msg)

        if not want_state.has_any_switches():
            msg = "No switches to override. Exiting."
            self.log.error(msg)
            return

        self.common = Common(task_params, have_state, want_state, logger)
        # Perform diff calculations for different switch types
        self.common.calculate_diff()

        self.deleted_task = Deleted(task_params, have_state, want_state, logger, self.common)

        self.merged_task = Merged(task_params, have_state, want_state, logger, self.common)

        msg = f"EXITED: {self.class_name}.{method_name} - {len(self.common.requests)} requests prepared"
        self.log.debug(msg)

    def process_overridden_request(self):
        """Prepare requests for adding, removing and updating switches in overridden state."""
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        # Process the deleted task first to remove any switches that are not in the desired state
        self.deleted_task.process_deleted_request()

        # Process the merged task to add switches in the desired state
        self.merged_task.process_merged_request()

        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

class Query:
    """
    Handle query state operations using the common diff logic.

    In query state:
    - Retrieve switches that exist in the current state
    - Fail if switches do not exist in the current state
    """

    def __init__(self, task_params, have_state, want_state, logger=None, common_util=None):
        self.class_name = self.__class__.__name__
        method_name = inspect.stack()[0][3]
        
        self.log = logger or logging.getLogger(f"nd.{self.class_name}")

        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        self.result = dict(changed=False, diff=[], response=[], warnings=[])

        msg = f"Initializing Query state"
        self.log.info(msg)

        self.have_switches = []
        self.want_switches = []
        self.queried_switches = {}
        self.query_result = {}

        self.query_all_switches = False
        self.query_poap = task_params.get("query_poap")

        if not have_state:
            msg = "No switches existing in fabric to query. Exiting."
            self.log.error(msg)
            raise SwitchOperationError(msg)

        self.have = have_state.get_all_switches()
        self.have_switches = self.have.get("switches")
        self.have_poap_switches = self.have.get("poap_switches")
        self.want_switch_data = want_state.get_all_switches()
        self.want_switches = self.want_switch_data.get("normal")
        self.log.debug(f"want_switches: {self.want_switches}")

        self.common = Common(task_params, have_state, want_state, logger)

        if not self.want_switches:
            self.query_all_switches = True
        else:
            self.want_switches_ip = [switch.get("ip") for switch in self.want_switches]

        msg = f"EXITED: {self.class_name}.{method_name}"
        self.log.debug(msg)

    def prepare_query_results(self):
        """
        Prepare Query results.
        """
        method_name = inspect.stack()[0][3]
        
        msg = f"ENTERED: {self.class_name}.{method_name}"
        self.log.debug(msg)

        if not self.query_all_switches:
            have_index = self.common.create_switch_index(self.have_switches)
            want_index = self.common.create_switch_index(self.want_switches)
            want_in_have_switches = have_index.keys() & want_index.keys()

            if want_in_have_switches:
                conflict_switches = self.common.check_switch_conflicts(have_index, want_index)
                self.log.debug(f"Conflict switches found: {conflict_switches}")
                if conflict_switches:       
                    for ip in conflict_switches:
                        self.queried_switches.update({ip: "Switch config differing"})
                        self.want_switches_ip.remove(ip)

                for ip in list(want_in_have_switches - set(conflict_switches)):
                    self.queried_switches.update({ip: have_index[ip]['original_sw']})
                    self.want_switches_ip.remove(ip)

                if not self.want_switches_ip:
                    for ip in self.want_switches_ip:
                        self.queried_switches.update({ip: "Switch missing"})

            else:
                msg = f"Switches not found in fabric: {self.want_switches_ip}"
                self.log.error(msg)
                raise SwitchOperationError(msg)
        else:
            for switch in self.have_switches:
                ip = switch.get("fabricManagementIp")
                self.queried_switches.update({ip: switch})
            msg = f"Queried all switches in fabric: {self.queried_switches}"
            self.log.info(msg)

        if self.queried_switches:
            self.query_result["switches"] = self.queried_switches
        if self.query_poap:
            self.query_result["poap_switches"] = self.have_poap_switches

        self.log.debug(f"Queried {self.queried_switches} switches")
        self.log.debug(f"Queried {self.have_poap_switches} POAP switches")
        return self.query_result

    
def main():
    argument_spec = {}
    argument_spec.update(
        fabric=dict(required=True, type="str"),
        state=dict(
            type="str",
            default="merged",
            choices=["merged", "replaced", "deleted", "overridden", "query"],
        ),
        config=dict(required=False, type="list", elements="dict"),
        query_poap=dict(type="bool", default=False),
        save=dict(type="bool", default=True),
        deploy=dict(type="bool", default=True),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if sys.version_info < (3, 9):
        nd.fail_json(msg="Python version 3.9 or higher is required for this nd.")

    if not HAS_PYDANTIC:
        nd.fail_json(msg=missing_required_lib("pydantic"), exception=PYDANTIC_IMPORT_ERROR)
    if not HAS_DEEPDIFF:
        nd.fail_json(msg=missing_required_lib("deepdiff"), exception=DEEPDIFF_IMPORT_ERROR)

    # Logging setup
    try:
        log = Log()
        log.config = "/home/achengam/Desktop/Ansible-ND4/ansible_collections/cisco/nd/logging_config.json"
        log.commit()
        mainlog = logging.getLogger("nd.main")
    except ValueError as error:
        nd.fail_json(str(error))

    mainlog.info("---------------------------------------------")
    mainlog.info("Starting cisco.nd.manage_switches module")
    mainlog.info("---------------------------------------------\n")

    nd = NDModule(module)

    have_switches = GetHave(nd)
    have_switches.refresh()
    have_switches.process_validate_nd_data()

    want_switches = GetWant(nd)
    want_switches.validate_input_state()

    try:
        task = None
        task_params = nd.params
        if task_params.get("state") == "merged":
            task = Merged(task_params, have_switches, want_switches)
            task.process_merged_request()
        elif task_params.get("state") == "deleted":
            task = Deleted(task_params, have_switches, want_switches)
            task.process_deleted_request()
        elif task_params.get("state") == "overridden":
            task = Overridden(task_params, have_switches, want_switches)
            task.process_overridden_request()
        elif task_params.get("state") == "query":
            task = Query(task_params, have_switches, want_switches)
            task.result["response"] = task.prepare_query_results()
            nd.exit_json(**task.result)
        if task is None:
            nd.fail_json(f"Invalid state: {task_params['state']}")
    except SwitchOperationError as e:
        nd.fail_json(msg=str(e))

    if task.common and task.common.requests:
        for request_key, request_data in task.common.requests.items():
            verb = request_data["verb"]
            path = request_data["path"]
            payload = request_data["payload"]

            if verb == "WAIT":
                # Handle wait request specially
                mainlog.info(f"Processing wait request: {request_data}")
                wait_helper = SwitchUtils(nd, payload, mainlog)
                if not wait_helper.wait_for_switch_import():
                    nd.fail_json(msg="Switches did not become manageable within the allowed attempts")
            else:
                #Pretty-print the payload for easier log reading
                pretty_payload = json.dumps(payload, indent=2, sort_keys=True)
                mainlog.info("Calling nd.request with path: %s, verb: %s, and payload:\n%s", path, verb, pretty_payload)
                #Make the API request
                response = nd.request(path, method=verb, data=payload if payload else None)
                task.common.result["response"].append(response)
                task.common.result["changed"] = True
    nd.exit_json(**task.common.result)

if __name__ == "__main__":
    main()
