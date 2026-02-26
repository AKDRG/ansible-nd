# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Akshayant Chengam Saravanan (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Switch Utility Classes for ND Switch Resource Module.

This module provides utility classes for:
- Building simple API payloads (PayloadUtils)
- Fabric-level operations like save/deploy (FabricUtils)
- Waiting for switch operations to complete (SwitchWaitUtils)

Note: Most payload building is now handled by schema models in
switch_inventory_models.py with their to_payload() methods:
- ShallowDiscoveryRequestModel for discovery
- AddSwitchesRequestModel for adding switches
- BootstrapImportSwitchModel / ImportBootstrapSwitchesRequestModel for POAP
- RMASwitchModel for RMA operations
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
import time
from typing import Dict, Any, List, Optional

from ansible_collections.cisco.nd.plugins.module_utils.ep.ep_api_v1_manage_fabric_config import (
    EpManageFabricConfigSave,
    EpManageFabricConfigDeploy,
    EpManageFabricGet,
    EpManageFabricInventoryDiscover,
)
from ansible_collections.cisco.nd.plugins.module_utils.ep.ep_api_v1_manage_fabric_switches import (
    EpManageFabricSwitchesGet,
)
from ansible_collections.cisco.nd.plugins.module_utils.ep.ep_api_v1_manage_fabric_switch_actions import (
    EpManageFabricSwitchActionsRediscover,
)


class SwitchOperationError(Exception):
    """Exception raised for switch operation failures."""
    pass


class PayloadUtils:
    """
    Utility class for building simple API payloads.
    
    Note: Complex payloads for discovery, add, POAP, and RMA operations
    are now built using schema models from switch_inventory_models.py.
    This class retains only credential and simple list-based payloads.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.log = logger or logging.getLogger("nd.PayloadUtils")
    
    def build_credentials_payload(
        self,
        serial_numbers: List[str],
        username: str,
        password: str
    ) -> Dict[str, Any]:
        """
        Build payload for saving switch credentials.
        
        Args:
            serial_numbers: List of switch serial numbers
            username: Switch username
            password: Switch password
            
        Returns:
            Credentials API payload
        """
        return {
            "switchIds": serial_numbers,
            "username": username,
            "password": password,
        }
    
    def build_switch_ids_payload(self, serial_numbers: List[str]) -> Dict[str, Any]:
        """
        Build payload with switch IDs for remove/batch operations.
        
        Args:
            serial_numbers: List of switch serial numbers
            
        Returns:
            Switch IDs payload
        """
        return {
            "switchIds": serial_numbers
        }


class FabricUtils:
    """
    Utility class for fabric-level operations.
    """
    
    def __init__(self, nd_module, fabric: str, logger: Optional[logging.Logger] = None):
        """
        Initialize FabricUtils.
        
        Args:
            nd_module: NDModule or NDNetworkResourceModule instance
            fabric: Fabric name
            logger: Optional logger instance
        """
        self.nd = nd_module
        self.fabric = fabric
        self.log = logger or logging.getLogger("nd.FabricUtils")
        
        # Initialize endpoint instances
        self.ep_config_save = EpManageFabricConfigSave()
        self.ep_config_save.fabric_name = fabric
        
        self.ep_config_deploy = EpManageFabricConfigDeploy()
        self.ep_config_deploy.fabric_name = fabric
        
        self.ep_fabric_get = EpManageFabricGet()
        self.ep_fabric_get.fabric_name = fabric
    
    def save_config(self) -> Dict[str, Any]:
        """
        Save (recalculate) fabric configuration.
        
        Returns:
            API response
        """
        self.log.info(f"Saving configuration for fabric: {self.fabric}")
        
        try:
            response = self.nd.request(self.ep_config_save.path, verb=self.ep_config_save.verb)
            self.log.info(f"Config save completed for fabric: {self.fabric}")
            return response
        except Exception as e:
            self.log.error(f"Config save failed for fabric {self.fabric}: {e}")
            raise SwitchOperationError(f"Failed to save config for fabric {self.fabric}: {e}")
    
    def deploy_config(self) -> Dict[str, Any]:
        """
        Deploy pending configuration to switches in the fabric.

        The configDeploy endpoint does not require a request body;
        it deploys all pending changes for the fabric.
            
        Returns:
            API response
        """
        self.log.info(f"Deploying config for fabric: {self.fabric}")
        
        try:
            response = self.nd.request(self.ep_config_deploy.path, verb=self.ep_config_deploy.verb)
            self.log.info(f"Config deploy initiated for fabric: {self.fabric}")
            return response
        except Exception as e:
            self.log.error(f"Config deploy failed: {e}")
            raise SwitchOperationError(f"Failed to deploy config: {e}")
    
    def get_fabric_info(self) -> Dict[str, Any]:
        """
        Get fabric information.
        
        Returns:
            Fabric information dictionary
        """
        try:
            response = self.nd.request(self.ep_fabric_get.path, verb=self.ep_fabric_get.verb)
            return response
        except Exception as e:
            self.log.error(f"Failed to get fabric info: {e}")
            raise SwitchOperationError(f"Failed to get fabric info: {e}")


class SwitchWaitUtils:
    """
    Utility class for waiting on switch operations to complete.
    
    Status values align with schema enums:
    - DiscoveryStatus from switch_inventory_models.py
    - ShallowDiscoveryStatus from switch_inventory_models.py
    """
    
    # Default wait parameters
    DEFAULT_MAX_ATTEMPTS = 60
    DEFAULT_WAIT_INTERVAL = 10  # seconds
    
    # Status values indicating switch is ready
    # Maps to DiscoveryStatus.OK and ShallowDiscoveryStatus.MANAGEABLE
    MANAGEABLE_STATUSES = ["ok", "manageable"]
    
    # Status values indicating operation is in progress
    # Maps to DiscoveryStatus: DISCOVERING, REDISCOVERING
    # Maps to SystemMode: MIGRATION
    IN_PROGRESS_STATUSES = ["inProgress", "migration", "discovering", "rediscovering"]
    
    # Status values indicating failure
    # Maps to DiscoveryStatus: UNREACHABLE, DISCOVERY_TIMEOUT, TIMEOUT, etc.
    # Maps to ShallowDiscoveryStatus: NOT_REACHABLE, NOT_AUTHORIZED
    FAILED_STATUSES = [
        "failed", 
        "unreachable", 
        "authenticationFailed", 
        "timeout",
        "discoveryTimeout",
        "notReacheable",  # Note: typo matches API spec
        "notAuthorized",
        "unknownUserPassword",
        "connectionError",
        "sshSessionError",
    ]
    
    def __init__(
        self,
        nd_module,
        fabric: str,
        logger: Optional[logging.Logger] = None,
        max_attempts: Optional[int] = None,
        wait_interval: Optional[int] = None
    ):
        """
        Initialize SwitchWaitUtils.
        
        Args:
            nd_module: NDModule or NDNetworkResourceModule instance
            fabric: Fabric name
            logger: Optional logger instance
            max_attempts: Maximum number of status check attempts
            wait_interval: Seconds to wait between attempts
        """
        self.nd = nd_module.nd
        self.fabric = fabric
        self.log = logger or logging.getLogger("nd.SwitchWaitUtils")
        self.max_attempts = max_attempts or self.DEFAULT_MAX_ATTEMPTS
        self.wait_interval = wait_interval or self.DEFAULT_WAIT_INTERVAL
        
        # Initialize endpoint instances
        self.ep_switches_get = EpManageFabricSwitchesGet()
        self.ep_switches_get.fabric_name = fabric
        
        self.ep_inventory_discover = EpManageFabricInventoryDiscover()
        self.ep_inventory_discover.fabric_name = fabric
        
        self.ep_rediscover = EpManageFabricSwitchActionsRediscover()
        self.ep_rediscover.fabric_name = fabric
        
        # Cache fabric details for greenfield flag
        self._fabric_details: Optional[Dict[str, Any]] = None
        self._greenfield_debug_enabled: Optional[bool] = None
    
    def wait_for_switch_manageable(
        self,
        serial_numbers: List[str]
    ) -> bool:
        """
        Wait for switches to exit migration mode and become manageable.
        
        This method implements a multi-phase waiting strategy:
        1. Wait for switches to exit "migration" system mode
        2. Wait for switches to enter "normal" system mode
        3. Check greenfield debug flag - if enabled, skip reload detection
        4. If greenfield disabled, wait for discovery status transitions:
           - First wait for "unreachable" (indicates reload)
           - Then wait for "ok" (indicates ready)
        
        Args:
            serial_numbers: List of switch serial numbers to wait for
            
        Returns:
            True if all switches are manageable, False otherwise
        """
        attempts = 300  # Match nd_manage_switches default
        interval = 5   # Match nd_manage_switches default
        
        self.log.info(f"Waiting for switches to exit migration mode and become manageable: {serial_numbers}")
        
        attempt = 1
        pending_switches = serial_numbers.copy()
        switch_state = "unreachable"
        check_migration = True
        migration_mode = "migration"
        switches_in_migration = serial_numbers.copy()
        
        while attempt <= attempts and pending_switches and switch_state:
            self.log.debug(f"Checking switch migration status - attempt {attempt}/{attempts}")
            
            # Get current switch data
            try:
                response = self.nd.request(self.ep_switches_get.path, verb=self.ep_switches_get.verb)
                switch_data = response.get("switches", [])
            except Exception as e:
                self.log.error(f"Failed to get switch data: {e}")
                return False
            
            if not switch_data:
                self.log.error("No switch data found for fabric")
                return False
            
            # Phase 1 & 2: Check migration mode (migration → normal)
            if check_migration:
                self.log.debug(f"Switches still in migration mode: {switches_in_migration}, mode: {migration_mode}")

                if switches_in_migration:
                    if migration_mode != "normal":
                        switches_in_migration = self._check_migration_mode(switches_in_migration, switch_data, migration_mode)
                    else:
                        switches_in_migration = self._check_mode(switches_in_migration, switch_data, migration_mode)

                    time.sleep(interval * 2)  # Wait longer during migration
                    attempt += 1
                    continue
                else:
                    if migration_mode == "migration":
                        self.log.info("All switches exited migration mode, now checking for normal mode")
                        # Switches exited migration, now check normal mode
                        migration_mode = "normal"
                        switches_in_migration = serial_numbers.copy()
                        self.log.debug(f"Switches exited migration mode, checking normal mode: {switches_in_migration}")
                    else:
                        self.log.info("All switches in normal system mode, now checking discovery status")
                        check_migration = False  # Proceed to discovery status checks

                        # Phase 3: Check greenfield debug flag
                        if self._get_greenfield_debug_flag():
                            self.log.info("Greenfield debug flag enabled, skipping reload detection")
                            return True

            # Phase 4: Discovery status checks (unreachable → ok)
            pending_switches = self._check_switches_state(pending_switches, switch_data, switch_state)

            if pending_switches:
                # Trigger rediscovery for pending switches
                self._trigger_rediscovery(pending_switches)
                self.log.info(f"Switches still pending: {pending_switches}, waiting...")
                time.sleep(interval * 3.5)  # Wait longer after rediscovery
            else:
                if switch_state == "ok":
                    # All switches reached "ok" state
                    self.log.info("All switches are now manageable")
                    return True
                # All switches reached "unreachable", now wait for "ok"
                pending_switches = serial_numbers.copy()
                switch_state = "ok"
                self.log.debug("Switches detected as unreachable, now waiting for ok state")
            
            attempt += 1
        
        self.log.warning(f"Timeout waiting for switches: {serial_numbers}")
        return False
    
    def wait_for_discovery(
        self,
        seed_ip: str,
        max_attempts: Optional[int] = None,
        wait_interval: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for switch discovery to complete.
        
        Args:
            seed_ip: IP address of switch being discovered
            max_attempts: Override max attempts
            wait_interval: Override wait interval
            
        Returns:
            Discovery response data if successful, None otherwise
        """
        attempts = max_attempts or 30  # Discovery is usually faster
        interval = wait_interval or 5
        
        self.log.info(f"Waiting for discovery of: {seed_ip}")
        
        for attempt in range(attempts):
            discovery_status = self._get_discovery_status(seed_ip)
            
            if discovery_status and discovery_status.get("status") in self.MANAGEABLE_STATUSES:
                self.log.info(f"Discovery completed for {seed_ip}")
                return discovery_status
            
            if discovery_status and discovery_status.get("status") in self.FAILED_STATUSES:
                self.log.error(f"Discovery failed for {seed_ip}: {discovery_status}")
                return None
            
            self.log.debug(f"Discovery attempt {attempt + 1}/{attempts} for {seed_ip}")
            time.sleep(interval)
        
        self.log.warning(f"Discovery timeout for {seed_ip}")
        return None
    
    def _check_migration_mode(
        self,
        serial_numbers: List[str],
        switch_data: List[Dict[str, Any]],
        required_mode: str
    ) -> List[str]:
        """
        Check if switches are still in specified system mode.
        
        Args:
            serial_numbers: List of switch serial numbers to check
            switch_data: Switch data from API response
            required_mode: Expected mode ('migration' or 'normal')
            
        Returns:
            List of switches still in the required mode
        """
        remaining_switches = []
        
        for sn in serial_numbers:
            for switch in switch_data:
                if switch.get("serialNumber") == sn:
                    additional = switch.get("additionalData", {})
                    mode = additional.get("systemMode", "").lower()
                    
                    if mode == required_mode:
                        remaining_switches.append(sn)
                        self.log.debug(f"Switch {sn} still in {required_mode} mode")
                    break
        
        return remaining_switches

    def _check_mode(
        self,
        serial_numbers: List[str],
        switch_data: List[Dict[str, Any]],
        required_mode: str
    ) -> List[str]:
        """
        Check if switches are still in specified system mode.
        
        Args:
            serial_numbers: List of switch serial numbers to check
            switch_data: Switch data from API response
            required_mode: Expected mode ('migration' or 'normal')
            
        Returns:
            List of switches not in the required mode
        """
        remaining_switches = []
        
        for sn in serial_numbers:
            for switch in switch_data:
                if switch.get("serialNumber") == sn:
                    additional = switch.get("additionalData", {})
                    mode = additional.get("systemMode", "").lower()
                    
                    if mode != required_mode:
                        remaining_switches.append(sn)
                        self.log.debug(f"Switch {sn} still in {required_mode} mode")
                    break
        
        return remaining_switches
    
    def _check_switches_state(
        self,
        serial_numbers: List[str],
        switch_data: List[Dict[str, Any]],
        target_state: str
    ) -> List[str]:
        """
        Check if switches have reached the target discovery state.
        
        Args:
            serial_numbers: List of switch serial numbers to check
            switch_data: Switch data from API response
            target_state: Target discovery status (e.g., 'unreachable', 'ok')
            
        Returns:
            List of switches that have NOT yet reached target state
        """
        remaining_switches = []
        
        for sn in serial_numbers:
            switch_found = False
            self.log.debug(f"Checking switch {sn} for state {target_state}")
            
            for switch in switch_data:
                if switch.get("serialNumber") == sn:
                    additional = switch.get("additionalData", {})
                    discovery_status = additional.get("discoveryStatus", "").lower()
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
    
    def _trigger_rediscovery(self, serial_numbers: List[str]) -> None:
        """
        Trigger rediscovery for specified switches.
        
        Args:
            serial_numbers: List of switch serial numbers to rediscover
        """
        if not serial_numbers:
            return
        
        self.log.info(f"Triggering rediscovery for switches: {serial_numbers}")
        
        payload = {"switchIds": serial_numbers}
        
        try:
            self.nd.request(self.ep_rediscover.path, verb=self.ep_rediscover.verb, data=payload)
            self.log.info(f"Rediscovery triggered successfully for switches: {serial_numbers}")
        except Exception as e:
            self.log.warning(f"Failed to trigger rediscovery: {e}")
    
    def _get_greenfield_debug_flag(self) -> bool:
        """
        Check if greenfield debug flag is enabled in fabric.
        
        The greenfield debug flag, when enabled, allows skipping reload detection
        during switch onboarding, significantly speeding up operations in greenfield
        deployments.
 
        Returns:
            True if greenfield debug flag is enabled, False otherwise
        """
        if self._greenfield_debug_enabled is not None:
            return self._greenfield_debug_enabled

        try:
            if self._fabric_details is None:
                # Use FabricUtils to get fabric info
                fabric_utils = FabricUtils(self.nd, self.fabric, self.log)
                self._fabric_details = fabric_utils.get_fabric_info()

            greenfield_flag = (
                self._fabric_details
                .get("management", {})
                .get("greenfieldDebugFlag", "")
                .lower()
            )

            if greenfield_flag == "enable":
                return True
            return False

        except Exception as e:
            self.log.debug(f"Failed to get greenfield debug flag: {e}")
            return False
    
    def _get_switch_statuses(self, serial_numbers: List[str]) -> Dict[str, str]:
        """
        Get current status of switches.
        
        Args:
            serial_numbers: List of switch serial numbers
            
        Returns:
            Dictionary mapping serial number to status
        """
        try:
            response = self.nd.request(self.ep_switches_get.path, verb=self.ep_switches_get.verb)
            switches = response.get("switches", [])
            
            statuses = {}
            for switch in switches:
                sn = switch.get("serialNumber") or switch.get("switchId")
                if sn in serial_numbers:
                    additional = switch.get("additionalData", {})
                    status = additional.get("discoveryStatus") or switch.get("status", "unknown")
                    statuses[sn] = status
            
            return statuses
            
        except Exception as e:
            self.log.error(f"Failed to get switch statuses: {e}")
            return {sn: "unknown" for sn in serial_numbers}
    
    def _get_discovery_status(self, seed_ip: str) -> Optional[Dict[str, Any]]:
        """
        Get discovery status for a switch.
        
        Args:
            seed_ip: IP address of switch
            
        Returns:
            Discovery status data or None
        """
        try:
            response = self.nd.request(self.ep_inventory_discover.path, verb=self.ep_inventory_discover.verb)
            switches = response.get("switches", [])
            
            for switch in switches:
                if switch.get("ip") == seed_ip or switch.get("ipaddr") == seed_ip:
                    return switch
            
            return None
            
        except Exception as e:
            self.log.debug(f"Discovery status check failed: {e}")
            return None
