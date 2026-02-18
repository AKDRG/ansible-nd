# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from copy import deepcopy
from typing import Optional, List, Dict, Any, Union, Tuple

from .nd_v2 import NDModule
from .results import Results
from .schema.switch_inventory_models import (
    SwitchRole,
    SnmpV3AuthProtocol,
    PlatformType,
    RemoteCredentialStore,
    SwitchDiscoveryModel,
    SwitchDataModel,
    AddSwitchesRequestModel,
    ShallowDiscoveryRequestModel,
    BootstrapImportSwitchModel,
    ImportBootstrapSwitchesRequestModel,
    RMASwitchModel,
    ListAllSwitchesResponseModel,
    SwitchConfigModel,
    SwitchCredentialsRequestModel,
    POAPConfigModel,
    RMAConfigModel,
    ConfigDataModel,
)
from .switch_utils import PayloadUtils, FabricUtils, SwitchWaitUtils, SwitchOperationError
from .ep.ep_api_v1_manage_fabric_switches import (
    EpManageFabricSwitchesGet,
    EpManageFabricSwitchesAdd,
    EpManageFabricSwitchDelete,
    EpManageFabricSwitchUpdateRole,
)
from .ep.ep_api_v1_manage_fabric_discovery import EpManageFabricShallowDiscovery
from .ep.ep_api_v1_manage_fabric_switch_actions import (
    EpManageFabricSwitchProvisionRMA,
    EpManageFabricSwitchActionsImportBootstrap,
)
from .ep.ep_api_v1_manage_credentials import EpManageCredentialsSwitchesCreate


class NDSwitchResourceModule():
    """
    Specialized Module for Switch Management.
    
    Extends NDModule with switch-specific operations:
    - Discovery before adding switches
    - Wait for switch migration/manageability
    - Save credentials
    - Config save and deploy
    - POAP operations
    - RMA operations
    
    Uses schema models from switch_inventory_models.py:
    - SwitchDataModel: For existing switch inventory data
    - SwitchDiscoveryModel: For switch discovery/add operations
    - BootstrapImportSwitchModel: For POAP operations
    - RMASwitchModel: For RMA operations
    
    Usage:
        nd_module = NDSwitchResourceModule(
            module=ansible_module,
            fabric="my-fabric",
            model_class=SwitchDataModel,
        )
        
        nd_module.manage_state(
            state="merged",
            new_configs=configs,
        )
        
        nd_module.exit_json()
    """
    
    def __init__(
        self,
        nd: NDModule,
        results: Results,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the Switch Resource Module.
        
        Args:
            module: Ansible module instance
            logger: Optional logger instance
        """
        # super().__init__(nd.module)
        
        self.log = logger or logging.getLogger("nd.NDSwitchResourceModule")
        self.nd = nd

        # Store references for convenience
        self.module = nd.module

        # Configuration
        # self.model_class = SwitchDataModel
        self.config = self.nd.module.params.get("config", {})
        self.fabric = self.nd.module.params.get("fabric")
        self.state = self.nd.module.params.get("state")
        self.save_config_flag = self.nd.module.params.get("save", True)
        self.deploy_config_flag = self.nd.module.params.get("deploy", True)
        self.results = results
        self.operation
        # Initialize collections
        try:
            self.proposed: List[SwitchDataModel] = []

            self.existing: List[SwitchDataModel] = [
                SwitchDataModel.model_validate(sw) for sw in self._query_all_switches()
            ]

            self.previous: List[SwitchDataModel] = deepcopy(self.existing)
            
        except Exception as e:
            self.log.error(f"Failed to initialize collections: {e}")
            self.existing: List[SwitchDataModel] = []
            self.previous: List[SwitchDataModel] = []
            self.proposed: List[SwitchConfigModel] = []
        
        # Operation tracking
        self.nd_logs: List[Dict[str, Any]] = []
        
        # Current operation context
        self.current_identifier: Optional[str] = None
        
        # Track discovered switches for correlation
        self.discovered_switches: Dict[str, Dict[str, Any]] = {}
        
        # Initialize utility instances
        self.payload_utils = PayloadUtils(self.log)
        self.fabric_utils = FabricUtils(self, self.fabric, self.log)
        self.wait_utils = SwitchWaitUtils(self, self.fabric, self.log)
        
        self.log.info(f"Initialized NDSwitchResourceModule for fabric: {self.fabric}")
    
    # =========================================================================
    # Configuration Validation
    # =========================================================================
    
    def _validate_configs(self, config: Union[Dict[str, Any], List[Dict[str, Any]]]) -> List[SwitchConfigModel]:
        """
        Validate input ansible config and return validated SwitchConfigModel instances.
        
        Args:
            config: Raw configuration from ansible module params. Can be:
                    - Single dict with switch config
                    - List of dicts with multiple switch configs
                    
        Returns:
            List of validated SwitchConfigModel instances
            
        Raises:
            ValidationError: If config validation fails or mixed operation types detected
            
        Example config structure:
            {
                "fabric": "MyFabric",
                "seed_ip": "10.1.1.1",
                "user_name": "admin",
                "password": "secret",
                "auth_proto": "MD5",
                "role": "leaf",
                "preserve_config": true,
                "poap": [
                    {
                        "serial_number": "SAL123456",
                        "hostname": "leaf1",
                        "model": "N9K-C93180YC-FX",
                        "version": "9.3(10)",
                        "image_policy": "NX-OS_9.3.10"
                    }
                ],
                "rma": [
                    {
                        "old_serial": "SAL111111",
                        "serial_number": "SAL222222",
                        "model": "N9K-C93180YC-FX",
                        "version": "9.3(10)",
                        "image_policy": "NX-OS_9.3.10"
                    }
                ]
            }
        """
        self.log.debug(f"ENTER: _validate_configs()")
        self.log.debug(f"Input config type: {type(config).__name__}")
        self.log.debug(f"Input config: {config}")
        
        validated_configs: List[SwitchConfigModel] = []
        operation_types: set = set()

        # Normalize config to list
        configs_list = config if isinstance(config, list) else [config]
        self.log.debug(f"Normalized to {len(configs_list)} configuration(s)")

        for idx, cfg in enumerate(configs_list):
            self.log.debug(f"Validating config {idx + 1}/{len(configs_list)}: seed_ip={cfg.get('seed_ip')}")
            try:
                # Validate with SwitchConfigModel
                validated = SwitchConfigModel.model_validate(cfg)
                validated_configs.append(validated)

                # Determine operation type for this config
                if validated.poap and len(validated.poap) > 0:
                    operation_types.add("poap")
                elif validated.rma and len(validated.rma) > 0:
                    operation_types.add("rma")
                else:
                    operation_types.add("normal")

            except Exception as e:
                error_msg = f"Configuration validation failed for config index {idx}: {str(e)}"
                self.log.error(error_msg)
                if hasattr(self.nd, 'module'):
                    self.nd.module.fail_json(msg=error_msg)
                else:
                    raise ValueError(error_msg) from e

        # Check for mixed operation types
        if len(operation_types) > 1:
            error_msg = (
                f"Mixed operation types detected in configuration: {', '.join(sorted(operation_types))}. "
                "POAP, RMA, and Normal switch operations cannot be mixed in the same task. "
                "Please separate them into different tasks or playbook runs."
            )
            self.log.error(error_msg)
            if hasattr(self.nd, 'module'):
                self.nd.module.fail_json(msg=error_msg)
            else:
                raise ValueError(error_msg)
        else:
            if "poap" in operation_types and (self.state != "merged" and self.state != "query"):
                error_msg = (
                    "POAP operations should use 'merged' state to ensure proper handling. "
                    f"Current state: {self.state}"
                )
                self.log.error(error_msg)
                if hasattr(self.nd, 'module'):
                    self.nd.module.fail_json(msg=error_msg)
            elif "rma" in operation_types and self.state != "merged":
                error_msg = (
                    "RMA operations should use 'merged' state to ensure proper handling. "
                    f"Current state: {self.state}"
                )
                self.log.error(error_msg)
                if hasattr(self.nd, 'module'):
                    self.nd.module.fail_json(msg=error_msg)

        if not validated_configs:
            self.log.warning("No valid configurations found in input")
        else:
            operation_type = list(operation_types)[0] if operation_types else "unknown"
            self.log.info(
                f"Successfully validated {len(validated_configs)} configuration(s) "
                f"with operation type: {operation_type}"
            )
        
        self.log.debug(f"EXIT: _validate_configs() -> {len(validated_configs)} configs, operation_type={list(operation_types)[0] if operation_types else 'unknown'}")
        return validated_configs, operation_type
    
    # =========================================================================
    # State Management
    # =========================================================================
    
    def manage_state(
        self
    ) -> None:
        """
        Main entry point for state management.
        
        Args:
            state: Desired state (merged, overridden, deleted, query)
            new_configs: List of switch configurations
            unwanted_keys: Keys to exclude from diff comparison
            override_exceptions: Switches to exclude from override deletion
        """
        self.log.info(f"Managing state: {self.state}")

        if self.state != "query":
            proposed_config, self.operation_type = self._validate_configs(self.config)
            discovered_data = self._discover_switches(proposed_config)
            try:
                for switch_proposed_config in proposed_config:
                    seed_ip = switch_proposed_config.seed_ip
                    discovered_switch = discovered_data.get(seed_ip)
                    discovered_switch["role"] = switch_proposed_config.role  # Add role from proposed config for comparison
                    if discovered_switch:
                        discovered_model = SwitchDataModel.from_response(discovered_switch)
                        self.proposed.append(discovered_model)
                    else:
                        self.log.warning(f"No discovered data for switch with seed IP {seed_ip}")
                        # Might be pre-provisioned, check in existing inventory by seed_ip
                        existing_match = next(
                            (sw for sw in self.existing if sw.fabric_management_ip == seed_ip), 
                            None
                        )
                        if existing_match:
                            self.proposed.append(existing_match)
                            self.log.warning(f"Switch with seed IP {seed_ip} not discovered but found in existing inventory - adding to proposed for comparison")
                        else:
                            msg = f"Switch with seed IP {seed_ip} not discovered and not found in existing inventory."
                            self.log.error(msg)
                            self.nd.module.fail_json(msg=msg)
                    self.log.debug(f"Transformed discovered data to model for switch: {discovered_model}")
            except Exception as e:
                self.log.error(f"Failed to transform discovered data to model for switch: {discovered_switch}: {e}")
            
            diff = self._compute_changes(self.proposed, self.existing)

            if self.state == "merged":
                return self._handle_merged_state(diff, proposed_config)
            elif self.state == "deleted":
                return self._handle_deleted_state(diff)
            elif self.state == "overridden":
                return self._handle_overridden_state(diff, proposed_config)

        elif self.state == "query":
            return self._handle_query_state()
        else:
            self.nd.module.fail_json(msg=f"Unsupported state: {self.state}")

    def _compute_changes(
        self,
        proposed: List[SwitchDataModel],
        existing: List[SwitchDataModel]
    ) -> Dict[str, List[SwitchDataModel]]:
        """
        Compare two lists of SwitchDataModel efficiently.
        
        Returns:
            {
                "to_add": [switches in proposed but not in existing],
                "to_update": [switches in both with differences],
                "to_delete": [switches in existing but not in proposed],
                "migration_mode": [switches in Migration mode],
                "idempotent": [switches with no changes]
            }
        """
        # Build index by switch_id for O(1) lookups
        existing_by_id = {sw.switch_id: sw for sw in existing}
        proposed_by_id = {sw.switch_id: sw for sw in proposed}
        
        # Also index by IP (for switches not yet discovered)
        existing_by_ip = {sw.fabric_management_ip: sw for sw in existing}
        
        # Fields to exclude from comparison
        exclude_fields = {
            "mode", "systemUpTime", "lastUpdated", 
            "alertSuspend", "anomalyLevel", "advisoryLevel"
        }
        
        changes = {
            "to_add": [],
            "to_update": [],
            "to_delete": [],
            "migration_mode": [],
            "idempotent": []
        }
        
        # Process proposed switches
        for prop_sw in proposed:
            # Try to find match by switch_id first
            existing_sw = existing_by_id.get(prop_sw.switch_id)
            
            # If not found by switch_id, try by IP
            if not existing_sw:
                existing_sw = existing_by_ip.get(prop_sw.fabric_management_ip)
            
            if existing_sw:
                # Check migration mode first
                if existing_sw.mode == "Migration":
                    changes["migration_mode"].append(prop_sw)
                    continue
                
                # Compare models using dict comparison
                prop_dict = prop_sw.model_dump(
                    by_alias=True,
                    exclude_none=True,
                    exclude=exclude_fields
                )
                
                existing_dict = existing_sw.model_dump(
                    by_alias=True,
                    exclude_none=True,
                    exclude=exclude_fields
                )
                
                if prop_dict == existing_dict:
                    changes["idempotent"].append(prop_sw)
                else:
                    changes["to_update"].append(prop_sw)
            else:
                # Not in existing - needs to be added
                changes["to_add"].append(prop_sw)
        
        # Find switches in existing but not in proposed (for overridden state)
        proposed_ids = {sw.switch_id for sw in proposed}
        for existing_sw in existing:
            if existing_sw.switch_id not in proposed_ids:
                changes["to_delete"].append(existing_sw)
        
        return changes

    def _handle_query_state(self) -> None:
        """Handle query state - return existing switches."""
        self.log.debug("ENTER: _handle_query_state()")
        self.log.info("Handling query state")
        self.log.debug(f"Found {len(self.existing)} existing switches")
        
        self.results.current = [sw.model_dump(by_alias=True) for sw in self.existing]
        self.log.debug(f"Returning {len(self.results.current)} switches in results")
        
        self.results.register_final_result()
        self.log.debug("EXIT: _handle_query_state()")

    def _discover_switches(self, switch_configs: list[SwitchConfigModel]) -> Dict[str, Dict[str, Any]]:
        """
        Discover switches based on proposed configurations to get serial numbers and other details.
        """

        # Step 1: Group switches by credentials for bulk operations
        self.log.debug("Step 1: Grouping switches by credentials")
        switch_credential_groups = self._group_switches_by_credentials(switch_configs)
        self.log.debug(f"Created {len(switch_credential_groups)} credential group(s)")
        
        # Step 2: Bulk discover switches (one API call per credential group)
        self.log.debug("Step 2: Bulk discovering switches")
        all_discovered = {}
        for group_key, switches in switch_credential_groups.items():
            username, password_hash, auth_proto, platform_type, preserve_config = group_key
            # Get actual password from first switch in group (all have same password)
            password = switches[0].password
            
            self.log.debug(f"Discovering group: {len(switches)} switches with username={username}")
            discovered_batch = self._bulk_discover_switches(
                switches=switches,
                username=username,
                password=password,
                auth_proto=auth_proto,
                platform_type=platform_type
            )
            all_discovered.update(discovered_batch)
            
        self.log.debug(f"Total discovered: {len(all_discovered)} switches")
        return all_discovered

    def _handle_merged_state(
        self
    ) -> None:
        """
        Handle merged state - add or update switches.
        Uses discovery-first approach with Pydantic model comparison.
        
        Comparison logic (similar to DCNM get_diff_merge):
        1. Discover all proposed switches to get serial numbers
        2. Transform discovered data to SwitchDataModel for comparison
        3. Compare discovered vs existing using all fields:
           - IP address, serial number, platform, version, hostname, role
        4. If ALL match -> skip (idempotent)
        5. If switch in "Migration" mode -> special handling
        6. If any field differs -> add to diff_create
        """
        self.log.debug("ENTER: _handle_merged_state()")
        self.log.info("Handling merged state")
        self.log.debug(f"Proposed configs: {len(self.proposed)}")
        self.log.debug(f"Existing switches: {len(self.existing)}")
        
        if not self.proposed:
            self.log.info("No configurations provided for merged state")
            self.results.changed = False
            self.results.register_final_result()
            self.log.debug("EXIT: _handle_merged_state() - no configs")
            return self.results

        # Phase 2: Compare discovered vs existing using Pydantic models
        self.log.debug("Phase 2: Comparing discovered vs existing switches")
        diff_create = []
        migration_mode_switches = []
        
        # Phase 4: Process Migration mode switches (special workflow)
        if migration_mode_switches:
            self.log.info(f"Processing {len(migration_mode_switches)} migration mode switches")
            for mig_sw in migration_mode_switches:
                # Assign role
                self.log.info(
                    f"Assigning role to migration switch: "
                    f"{mig_sw['switch_config'].seed_ip} ({mig_sw['serial_number']})"
                )
                self._update_switch_role(
                    mig_sw["switch_config"], 
                    mig_sw["serial_number"]
                )
                
                # Wait for switch to be manageable
                self.log.debug(f"Waiting for switch {mig_sw['serial_number']} to be manageable")
                SwitchWaitUtils.wait_for_switch_manageable(
                    self.nd, self.fabric, mig_sw["serial_number"]
                )
            
            # Config save and deploy for migration switches
            if self.nd.module.params.get("save", True):
                self.log.info("Saving configuration for migration switches")
                self._config_save()
            if self.nd.module.params.get("deploy", True):
                self.log.info("Deploying configuration for migration switches")
                self._config_deploy()
        
        # Phase 5: Process remaining switches (standard workflow)
        non_migration_switches = [
            sw for sw in diff_create 
            if not any(m["switch_config"] == sw for m in migration_mode_switches)
        ]
        
        if non_migration_switches:
            self.log.debug(f"Phase 5: Processing {len(non_migration_switches)} non-migration switches")
            try:
                self._create_switch()
                self.log.debug("Switch processing completed successfully")
            except Exception as e:
                self.log.error(f"Failed to process switches: {e}")
                self.nd.module.fail_json(msg=f"Failed to process switches: {e}")
        
        # Set changed flag
        self.results.changed = True
        
        # Return results
        self.results.register_final_result()
        self.log.debug(f"EXIT: _handle_merged_state() - completed with changed={self.results.changed}")
        return self.results
    
    def _handle_overridden_state(self) -> None:
        """
        Handle overridden state - replace all switches with desired config.
        Override means: ensure only the switches in proposed config exist, delete all others.
        """
        self.log.info("Handling overridden state")
        
        if not self.proposed:
            self.log.warning("No configurations provided for overridden state")
            self.results.changed = False
            self.results.register_final_result()
            return self.results
        
        # Get identifiers from proposed configs
        proposed_identifiers = set()
        for switch_config in self.proposed:
            proposed_identifiers.add(switch_config.seed_ip)
        
        # Delete switches not in proposed config
        for existing_switch in self.existing:
            # Get identifier from existing switch
            identifier = None
            if hasattr(existing_switch, 'fabric_management_ip'):
                identifier = existing_switch.fabric_management_ip
            elif hasattr(existing_switch, 'ip'):
                identifier = existing_switch.ip
            
            if identifier and identifier not in proposed_identifiers:
                self.log.info(f"Deleting switch (overridden): {identifier}")
                self.current_identifier = identifier
                try:
                    self._delete_switch(existing_switch)
                    self._log_operation("delete", identifier)
                except Exception as e:
                    self.log.error(f"Failed to delete switch {identifier}: {e}")
        
        # Now merge the proposed configurations (add/update switches)
        # Reuse merged state logic
        return self._handle_merged_state()
    
    def _handle_deleted_state(self) -> None:
        """
        Handle deleted state - remove specified switches.
        If no config provided, this is an error (don't delete all switches by default).
        """
        self.log.info("Handling deleted state")
        
        if not self.proposed:
            # Don't delete all switches by default - require explicit configuration
            self.log.warning("No configurations provided for deleted state - nothing to delete")
            self.results.changed = False
            self.results.register_final_result()
            return
        
        # Delete specified switches
        switches_deleted = False
        for switch_config in self.proposed:
            identifier = switch_config.seed_ip
            self.current_identifier = identifier
            
            # Find switch by seed_ip in existing inventory
            existing_switch = None
            for switch in self.existing:
                if hasattr(switch, 'fabric_management_ip') and switch.fabric_management_ip == identifier:
                    existing_switch = switch
                    break
            
            if existing_switch:
                self.log.info(f"Deleting switch: {identifier}")
                try:
                    self._delete_switch(existing_switch)
                    self._log_operation("delete", identifier)
                    switches_deleted = True
                except Exception as e:
                    self.log.error(f"Failed to delete switch {identifier}: {e}")
            else:
                self.log.info(f"Switch not found for deletion: {identifier}")
        
        # Final save and deploy if any deletions occurred
        if switches_deleted:
            self._finalize_operations()
            self.results.changed = True
        else:
            self.results.changed = False
        
        self.results.register_final_result()
    
    # =========================================================================
    # Switch Operations
    # =========================================================================
    
    def _create_switch(self) -> Optional[Dict[str, Any]]:
        """
        Create (add) switch with full workflow.
        
        Supports different input types:
        - SwitchConfigModel: For playbook config (validates and routes to normal/POAP/RMA)
        - SwitchDiscoveryModel: For normal switch discovery/add
        - Dict: Legacy support
        """
        self.log.debug("ENTER: _create_switch()")
        self.log.debug(f"Operation type: {self.operation_type}")
        
        try:
            self.log.info(f"Creating switch with operation type: {self.operation_type}")
            
            if self.operation_type == "normal":
                result = self._create_normal_switch()
            elif self.operation_type == "poap":
                result = self._create_poap_switch()
            elif self.operation_type == "rma":
                result = self._create_rma_switch()
            else:
                raise SwitchOperationError(f"Unknown operation type: {self.operation_type}")
            
            self.log.debug(f"EXIT: _create_switch() -> success")
            return result
                
        except Exception as e:
            self.log.error(f"Switch creation failed: {e}")
            raise SwitchOperationError(f"Create failed: {e}") from e
    
    def _determine_operation_type(self, switch: Union[SwitchConfigModel, SwitchDiscoveryModel, Dict[str, Any]]) -> str:
        """
        Determine the operation type from switch configuration.
        
        Returns:
            'normal': Standard switch discovery and add
            'poap': Bootstrap/preprovision via POAP
            'rma': Return Material Authorization (switch replacement)
        """
        # SwitchConfigModel has poap and rma fields
        if isinstance(switch, SwitchConfigModel):
            if switch.poap and len(switch.poap) > 0:
                return 'poap'
            if switch.rma and len(switch.rma) > 0:
                return 'rma'
            return 'normal'
        
        # Legacy dict support
        if isinstance(switch, dict):
            if 'poap' in switch or 'bootstrap' in switch:
                return 'poap'
            if 'rma' in switch or 'old_serial' in switch or 'oldSerial' in switch:
                return 'rma'
        
        return 'normal'
    
    def _delete_switch(self, switch: Union[SwitchDataModel, SwitchDiscoveryModel]) -> None:
        """
        Delete (remove) switch from fabric.
        """
        self.log.debug("ENTER: _delete_switch()")
        
        if self.nd.module.check_mode:
            self.log.debug("Check mode: Skipping actual deletion")
            self.log.debug("EXIT: _delete_switch() - check mode")
            return
        
        try:
            # Get serial number - use switch_id for SwitchDataModel
            serial_number = None
            if hasattr(switch, 'switch_id'):
                serial_number = switch.switch_id
            elif hasattr(switch, 'serial_number'):
                serial_number = switch.serial_number
            
            if not serial_number:
                self.log.warning(f"Cannot delete switch {self.current_identifier}: no serial number/switch_id")
                self.log.debug("EXIT: _delete_switch() - no serial number")
                return
            
            self.log.debug(f"Deleting switch with serial number: {serial_number}")
            
            # Remove switch from fabric using ep class
            endpoint = EpManageFabricSwitchDelete()
            endpoint.fabric_name = self.fabric
            endpoint.switch_id = serial_number
            
            self.log.info(f"Removing switch {serial_number} from fabric {self.fabric}")
            self.log.debug(f"Delete endpoint: {endpoint.path}")
            
            # Make the request
            self.nd.request(path=endpoint.path, verb=endpoint.verb)
            
            # Get response and result from RestSend
            response = self.nd.rest_send.response_current
            result = self.nd.rest_send.result_current
            
            # Register the task result
            self.results.action = "delete"
            self.results.response_current = response
            self.results.result_current = result
            self.results.diff_current = {"deleted": serial_number}
            self.results.register_task_result()
            
            self.log.debug(f"Switch {serial_number} deleted successfully")
            self.log.debug("EXIT: _delete_switch()")
            
        except Exception as e:
            self.log.error(f"Delete failed for {self.current_identifier}: {e}")
            raise SwitchOperationError(f"Delete failed for {self.current_identifier}: {e}") from e
    
    # =========================================================================
    # Normal Switch Operations
    # =========================================================================
    
    def _group_switches_by_credentials(self, switches: List[SwitchConfigModel]) -> Dict[Tuple, List[SwitchConfigModel]]:
        """
        Group switches by common credentials and configuration.
        
        Groups switches that share the same:
        - username
        - password (hashed for grouping key)
        - snmp_v3_auth_protocol
        - platform_type
        - preserve_config (for add operations)
        
        Args:
            switches: List of validated SwitchConfigModel instances
            
        Returns:
            Dict mapping (username, password_hash, auth_proto, platform_type, preserve_config) → List[switches]
            
        Example:
            {
                ('admin', 'hash123', 'MD5', 'nx-os', True): [switch1, switch2, switch3],
                ('admin', 'hash456', 'SHA', 'nx-os', True): [switch4, switch5]
            }
        """
        groups: Dict[Tuple, List[SwitchConfigModel]] = {}
        
        for switch in switches:
            # Extract grouping fields
            username = switch.user_name or 'admin'
            password = switch.password or ''
            auth_proto = switch.auth_proto or SnmpV3AuthProtocol.MD5
            platform_type = switch.platform_type or PlatformType.NX_OS
            preserve_config = switch.preserve_config if switch.preserve_config is not None else True
            
            # Create grouping key (use hash of password for security)
            password_hash = hash(password)
            group_key = (username, password_hash, auth_proto, platform_type, preserve_config)
            
            # Add switch to group
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(switch)
        
        self.log.info(
            f"Grouped {len(switches)} switches into {len(groups)} credential group(s)"
        )
        
        for idx, (key, group_switches) in enumerate(groups.items(), 1):
            username, _, auth_proto, platform_type, preserve_config = key
            # Safely get enum values (handle both enum and string types)
            auth_value = auth_proto.value if hasattr(auth_proto, 'value') else str(auth_proto)
            platform_value = platform_type.value if hasattr(platform_type, 'value') else str(platform_type)
            self.log.debug(
                f"Group {idx}: {len(group_switches)} switches with "
                f"username={username}, auth={auth_value}, "
                f"platform={platform_value}, preserve_config={preserve_config}"
            )
        
        return groups
    
    def _create_normal_switch(self) -> Dict[str, Any]:
        """
        Create normal switches with optimized bulk workflow:
        1. Group switches by credentials
        2. Bulk discovery (one API call per group)
        3. Bulk add to fabric (one API call per group)
        4. Wait for manageability
        5. Save credentials
        """
        self.log.debug("ENTER: _create_normal_switch()")
        self.log.info(f"Creating {len(self.proposed)} normal switch(es)")
        
        # Step 3: Bulk add discovered switches to fabric (one API call per credential group)
        self.log.debug("Step 3: Bulk adding switches to fabric")
        all_responses = []
        all_serial_numbers = []
        
        for group_key, switches in credential_groups.items():
            username, password_hash, auth_proto, platform_type, preserve_config = group_key
            password = switches[0].password
            
            # Filter switches that were successfully discovered
            discovered_switches = [
                (sw, all_discovered.get(sw.seed_ip))
                for sw in switches
                if all_discovered.get(sw.seed_ip)
            ]
            
            if not discovered_switches:
                self.log.warning(f"No switches discovered in group, skipping add")
                continue
            
            response = self._bulk_add_switches_to_fabric(
                switches=discovered_switches,
                username=username,
                password=password,
                auth_proto=auth_proto,
                platform_type=platform_type,
                preserve_config=preserve_config
            )
            all_responses.append(response)
            
            # Collect serial numbers for wait operation
            for _, discovered in discovered_switches:
                if discovered and discovered.get("serialNumber"):
                    all_serial_numbers.append(discovered.get("serialNumber"))
        
        # Step 4: Wait for all switches to be manageable
        self.log.debug("Step 4: Waiting for switches to become manageable")
        if all_serial_numbers:
            self.log.debug(f"Waiting for {len(all_serial_numbers)} switch(es): {all_serial_numbers}")
            success = self.wait_utils.wait_for_switch_manageable(all_serial_numbers)
            if not success:
                self.log.warning("Some switches did not become fully manageable")
            else:
                self.log.debug("All switches are now manageable")
        
        # Step 5: Save credentials for all switches
        self.log.debug("Step 5: Saving credentials for switches")
        for group_key, switches in credential_groups.items():
            username, password_hash, auth_proto, platform_type, preserve_config = group_key
            password = switches[0].password
            
            for switch in switches:
                discovered = all_discovered.get(switch.seed_ip)
                if discovered and discovered.get("serialNumber"):
                    self._save_switch_credentials(switch, discovered.get("serialNumber"))
        
        self.log.debug(f"EXIT: _create_normal_switch() -> {len(all_responses)} responses")
        return {"responses": all_responses, "discovered": all_discovered}
    
    def _get_switch_field(self, switch: Union[SwitchConfigModel, SwitchDiscoveryModel, Dict[str, Any]], field_names: List[str]) -> Optional[Any]:
        """
        Extract a field value from switch config (model or dict).
        Tries multiple field names for compatibility.
        """
        for name in field_names:
            # For Pydantic models (including SwitchConfigModel)
            if hasattr(switch, name):
                value = getattr(switch, name)
                if value is not None:
                    return value
            # For dictionaries
            elif isinstance(switch, dict):
                # Try both snake_case and camelCase
                if name in switch and switch[name] is not None:
                    return switch[name]
                # Convert snake_case to camelCase
                camel = ''.join(word.capitalize() if i > 0 else word for i, word in enumerate(name.split('_')))
                if camel in switch and switch[camel] is not None:
                    return switch[camel]
        return None
    
    def _bulk_discover_switches(
        self,
        switches: List[SwitchConfigModel],
        username: str,
        password: str,
        auth_proto: SnmpV3AuthProtocol,
        platform_type: PlatformType
    ) -> Dict[str, Dict[str, Any]]:
        """
        Discover multiple switches with same credentials in one API call.
        
        Args:
            switches: List of switches to discover
            username: Discovery username
            password: Discovery password
            auth_proto: SNMP v3 authentication protocol
            platform_type: Platform type (nx-os, ios-xe, etc.)
            
        Returns:
            Dict mapping seed_ip → discovered_data
        """
        self.log.debug("ENTER: _bulk_discover_switches()")
        self.log.debug(f"Discovering {len(switches)} switches in bulk")
        
        # Build endpoint using ep class
        endpoint = EpManageFabricShallowDiscovery()
        endpoint.fabric_name = self.fabric
        
        # Extract seed IPs from all switches
        seed_ips = [switch.seed_ip for switch in switches]
        self.log.debug(f"Seed IPs: {seed_ips}")
        
        # Get max_hops from first switch (or use default)
        max_hops = switches[0].max_hops if hasattr(switches[0], 'max_hops') else 0
        
        # Build shallow discovery request using schema model
        discovery_request = ShallowDiscoveryRequestModel(
            seedIpCollection=seed_ips,
            maxHop=max_hops,
            platformType=platform_type,
            snmpV3AuthProtocol=auth_proto,
            username=username,
            password=password
        )
        
        payload = discovery_request.to_payload()
        self.log.info(
            f"Bulk discovering {len(seed_ips)} switches: {', '.join(seed_ips)}"
        )
        self.log.debug(f"Discovery endpoint: {endpoint.path}")
        self.log.debug(f"Discovery payload (password masked): {self._mask_password(payload)}")
        
        try:
            # Make the request
            self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)
            
            # Get response and result from RestSend
            response = self.nd.rest_send.response_current
            result = self.nd.rest_send.result_current
            
            # Register the task result
            self.results.action = "discover"
            self.results.response_current = response
            self.results.result_current = result
            self.results.diff_current = payload
            self.results.register_task_result()
            
            # Extract discovered switches from response
            # Response structure: {"DATA": {"switches": [...]}, "body": {"switches": [...]}}
            discovered_results = {}
            switches_data = []
            
            if response:
                # Try DATA.switches first (primary location)
                if isinstance(response, dict):
                    if "DATA" in response and isinstance(response["DATA"], dict):
                        switches_data = response["DATA"].get("switches", [])
                    elif "body" in response and isinstance(response["body"], dict):
                        switches_data = response["body"].get("switches", [])
                    elif "switches" in response:
                        switches_data = response.get("switches", [])
            
            self.log.debug(f"Extracted {len(switches_data)} switches from discovery response")
            
            # Process each discovered switch
            for discovered in switches_data:
                if not isinstance(discovered, dict):
                    continue
                    
                ip = discovered.get("ip")
                status = discovered.get("status", "").lower()
                serial_number = discovered.get("serialNumber")
                
                # Validate discovery response has required fields
                if not serial_number:
                    self.log.error(f"Switch {ip} discovery missing serial number")
                    continue
                
                if not ip:
                    self.log.error(f"Switch with serial {serial_number} missing IP address")
                    continue
                
                if status in ["manageable", "ok"]:
                    discovered_results[ip] = discovered
                    self.log.info(f"Switch {ip} ({serial_number}) discovered successfully - status: {status}")
                elif status == "alreadymanaged":
                    self.log.info(f"Switch {ip} ({serial_number}) is already managed")
                    discovered_results[ip] = discovered
                else:
                    reason = discovered.get("statusReason", "Unknown")
                    self.log.error(
                        f"Switch {ip} discovery failed - status: {status}, reason: {reason}"
                    )
            
            # Check for any seed IPs that weren't in the response
            for seed_ip in seed_ips:
                if seed_ip not in discovered_results:
                    self.log.warning(f"Switch {seed_ip} not found in discovery response")
            
            self.log.info(
                f"Bulk discovery completed: {len(discovered_results)}/{len(seed_ips)} switches successful"
            )
            self.log.debug(f"Discovered switches: {list(discovered_results.keys())}")
            self.log.debug(f"EXIT: _bulk_discover_switches() -> {len(discovered_results)} discovered")
            return discovered_results
            
        except Exception as e:
            self.log.error(f"Bulk discovery failed: {e}")
            raise
    
    def _discover_switch(self, switch: Union[SwitchConfigModel, SwitchDiscoveryModel, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Discover a single switch using shallow discovery and return discovery response.
        
        NOTE: For bulk operations, use _bulk_discover_switches instead.
        Uses ShallowDiscoveryRequestModel for the API payload.
        """
        # Build endpoint using ep class
        endpoint = EpManageFabricShallowDiscovery()
        endpoint.fabric_name = self.fabric
        
        # Extract fields from switch config
        seed_ip = self._get_switch_field(switch, ['ip', 'seed_ip'])
        username = self._get_switch_field(switch, ['username', 'user_name'])
        password = self._get_switch_field(switch, ['password'])
        auth_proto = self._get_switch_field(switch, ['snmp_v3_auth_protocol', 'snmpV3AuthProtocol', 'auth_proto'])
        platform_type = self._get_switch_field(switch, ['platform_type', 'platformType'])
        max_hops = self._get_switch_field(switch, ['max_hop', 'maxHop', 'max_hops']) or 0
        
        # Build shallow discovery request using schema model
        discovery_request = ShallowDiscoveryRequestModel(
            seedIpCollection=[seed_ip],
            maxHop=max_hops,
            platformType=platform_type or PlatformType.NX_OS,
            snmpV3AuthProtocol=auth_proto or SnmpV3AuthProtocol.MD5,
            username=username,
            password=password
        )
        
        payload = discovery_request.to_payload()
        self.log.info(f"Discovering switch: {seed_ip}")
        
        try:
            # Make the request
            self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)
            
            # Get response and result from RestSend
            response = self.nd.rest_send.response_current
            result = self.nd.rest_send.result_current
            
            # Register the task result
            self.results.action = "discover"
            self.results.response_current = response
            self.results.result_current = result
            self.results.diff_current = payload
            self.results.register_task_result()
            
            # Wait for discovery to complete
            discovered = self.wait_utils.wait_for_discovery(seed_ip)
            
            if discovered:
                status = discovered.get("status", "").lower()
                serial_number = discovered.get("serialNumber")
                
                # Validate discovery response
                if not serial_number:
                    self.log.error(f"Switch {seed_ip} discovery missing serial number")
                    return None
                
                if status in ["manageable", "ok"]:
                    self.discovered_switches[seed_ip] = discovered
                    self.log.info(f"Switch {seed_ip} ({serial_number}) discovered successfully")
                    return discovered
                elif status == "alreadymanaged":
                    self.log.info(f"Switch {seed_ip} ({serial_number}) is already managed")
                    return discovered
                else:
                    reason = discovered.get("statusReason", "Unknown")
                    self.log.error(f"Switch {seed_ip} status: {status}, reason: {reason}")
                    return None
            
            return None
            
        except Exception as e:
            self.log.error(f"Discovery failed for {seed_ip}: {e}")
            raise
    
    def _bulk_add_switches_to_fabric(
        self,
        switches: List[Tuple[SwitchConfigModel, Dict[str, Any]]],
        username: str,
        password: str,
        auth_proto: SnmpV3AuthProtocol,
        platform_type: PlatformType,
        preserve_config: bool
    ) -> Dict[str, Any]:
        """
        Add multiple discovered switches to fabric in one API call.
        
        Args:
            switches: List of (switch_config, discovered_data) tuples
            username: Discovery username
            password: Discovery password
            auth_proto: SNMP v3 authentication protocol
            platform_type: Platform type
            preserve_config: Whether to preserve existing config
            
        Returns:
            API response
        """
        self.log.debug("ENTER: _bulk_add_switches_to_fabric()")
        self.log.debug(f"Adding {len(switches)} switches to fabric")
        
        # Build endpoint using ep class
        endpoint = EpManageFabricSwitchesAdd()
        endpoint.fabric_name = self.fabric
        
        # Create SwitchDiscoveryModel for each switch with validation
        switch_discoveries = []
        for switch_config, discovered in switches:
            # Validate required fields from discovery
            required_fields = ["hostname", "ip", "serialNumber", "model"]
            missing_fields = [f for f in required_fields if not discovered.get(f)]
            
            if missing_fields:
                self.log.warning(
                    f"Skipping switch - missing required fields from discovery: {', '.join(missing_fields)}"
                )
                continue
            
            switch_role = switch_config.role if hasattr(switch_config, 'role') else None
            
            switch_discovery = SwitchDiscoveryModel(
                hostname=discovered.get("hostname"),
                ip=discovered.get("ip"),
                serialNumber=discovered.get("serialNumber"),
                model=discovered.get("model"),
                softwareVersion=discovered.get("softwareVersion"),
                switchRole=switch_role
            )
            switch_discoveries.append(switch_discovery)
            self.log.debug(f"Prepared switch for add: {discovered.get('serialNumber')} ({discovered.get('hostname')})")
        
        # Validate we have switches to add
        if not switch_discoveries:
            self.log.error("No valid switches to add after validation")
            raise SwitchOperationError("No valid switches to add - all failed validation")
        
        # Create AddSwitchesRequestModel
        add_request = AddSwitchesRequestModel(
            switches=switch_discoveries,
            platformType=platform_type,
            preserveConfig=preserve_config,
            snmpV3AuthProtocol=auth_proto,
            username=username,
            password=password
        )
        
        payload = add_request.to_payload()
        serial_numbers = [d.get("serialNumber") for _, d in switches]
        self.log.info(
            f"Bulk adding {len(switches)} switches to fabric {self.fabric}: {', '.join(serial_numbers)}"
        )
        self.log.debug(f"Add endpoint: {endpoint.path}")
        self.log.debug(f"Add payload (password masked): {self._mask_password(payload)}")
        
        # Make the request
        self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)
        
        # Get response and result from RestSend
        response = self.nd.rest_send.response_current
        result = self.nd.rest_send.result_current
        
        # Register the task result
        self.results.action = "create"
        self.results.response_current = response
        self.results.result_current = result
        self.results.diff_current = payload
        self.results.register_task_result()
        
        return response
    
    def _add_switch_to_fabric(self, switch: Union[SwitchConfigModel, SwitchDiscoveryModel, Dict[str, Any]], discovered: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a single discovered switch to fabric using AddSwitchesRequestModel.
        
        NOTE: For bulk operations, use _bulk_add_switches_to_fabric instead.
        """
        # Build endpoint using ep class
        endpoint = EpManageFabricSwitchesAdd()
        endpoint.fabric_name = self.fabric
        
        # Extract fields from switch config
        switch_role = self._get_switch_field(switch, ['switch_role', 'switchRole', 'role'])
        preserve_config = self._get_switch_field(switch, ['preserve_config', 'preserveConfig']) or False
        platform_type = self._get_switch_field(switch, ['platform_type', 'platformType'])
        auth_proto = self._get_switch_field(switch, ['snmp_v3_auth_protocol', 'snmpV3AuthProtocol', 'auth_proto'])
        username = self._get_switch_field(switch, ['username', 'user_name'])
        password = self._get_switch_field(switch, ['password'])
        
        # Create SwitchDiscoveryModel from discovered data
        switch_discovery = SwitchDiscoveryModel(
            hostname=discovered.get("hostname"),
            ip=discovered.get("ip"),
            serialNumber=discovered.get("serialNumber"),
            model=discovered.get("model"),
            softwareVersion=discovered.get("softwareVersion"),
            switchRole=switch_role
        )
        
        # Create AddSwitchesRequestModel
        add_request = AddSwitchesRequestModel(
            switches=[switch_discovery],
            platformType=platform_type or PlatformType.NX_OS,
            preserveConfig=preserve_config,
            snmpV3AuthProtocol=auth_proto or SnmpV3AuthProtocol.MD5,
            username=username,
            password=password
        )
        
        payload = add_request.to_payload()
        self.log.info(f"Adding switch {discovered.get('serialNumber')} to fabric {self.fabric}")
        
        # Make the request
        self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)
        
        # Get response and result from RestSend
        response = self.nd.rest_send.response_current
        result = self.nd.rest_send.result_current
        
        # Register the task result
        self.results.action = "create"
        self.results.response_current = response
        self.results.result_current = result
        self.results.diff_current = payload
        self.results.register_task_result()
        
        return response
    
    def _save_switch_credentials(self, switch: Union[SwitchConfigModel, SwitchDiscoveryModel, Dict[str, Any]], serial_number: str) -> None:
        """
        Save credentials for a switch.
        """
        self.log.debug(f"ENTER: _save_switch_credentials() for serial: {serial_number}")
        
        password = self._get_switch_field(switch, ['password'])
        if not serial_number or not password:
            self.log.debug(f"EXIT: _save_switch_credentials() - missing serial_number or password")
            return
        
        # Build endpoint using ep class
        endpoint = EpManageCredentialsSwitchesCreate()
        
        username = self._get_switch_field(switch, ['username', 'user_name']) or "admin"
        
        # Build credentials payload using Pydantic model
        # API expects switchUsername/switchPassword (not username/password)
        creds_request = SwitchCredentialsRequestModel(
            switchIds=[serial_number],
            switchUsername=username,
            switchPassword=password
        )
        payload = creds_request.to_payload()
        
        self.log.info(f"Saving credentials for switch {serial_number}")
        self.log.debug(f"Credentials endpoint: {endpoint.path}")
        self.log.debug(f"Credentials payload (password masked): {self._mask_password(payload)}")
        
        try:
            # Make the request
            self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)
            
            # Get response and result from RestSend
            response = self.nd.rest_send.response_current
            result = self.nd.rest_send.result_current
            
            # Register the task result
            self.results.action = "save_credentials"
            self.results.response_current = response
            self.results.result_current = result
            self.results.diff_current = {"switchIds": [serial_number], "username": payload["switchUsername"]}
            self.results.register_task_result()
            self.log.debug(f"Credentials saved successfully for {serial_number}")
            self.log.debug("EXIT: _save_switch_credentials()")
        except Exception as e:
            self.log.warning(f"Failed to save credentials for {serial_number}: {e}")
    
    def _update_switch_role(self, switch: Union[SwitchConfigModel, SwitchDiscoveryModel, Dict[str, Any]], serial_number: str) -> None:
        """
        Update switch role.
        """
        # Build endpoint using ep class
        endpoint = EpManageFabricSwitchUpdateRole()
        endpoint.fabric_name = self.fabric
        endpoint.switch_id = serial_number
        
        switch_role = self._get_switch_field(switch, ['switch_role', 'switchRole', 'role'])
        
        # SwitchRole enum values are already in API format (camelCase)
        role_value = switch_role.value if isinstance(switch_role, SwitchRole) else (switch_role or "leaf")
        
        payload = {
            "role": role_value
        }
        
        self.log.info(f"Updating role for switch {serial_number} to {role_value}")
        
        try:
            # Make the request
            self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)
            
            # Get response and result from RestSend
            response = self.nd.rest_send.response_current
            result = self.nd.rest_send.result_current
            
            # Register the task result
            self.results.action = "update_role"
            self.results.response_current = response
            self.results.result_current = result
            self.results.diff_current = {"switchId": serial_number, "role": role_value}
            self.results.register_task_result()
        except Exception as e:
            self.log.warning(f"Failed to update role for {serial_number}: {e}")
    
    # =========================================================================
    # POAP Operations
    # =========================================================================
    
    def _create_poap_switch(self) -> Dict[str, Any]:
        """
        Create POAP (bootstrap/preprovision) switches using POAPConfigModel.
        Processes all switches in self.proposed that have POAP configurations.
        """
        self.log.debug("ENTER: _create_poap_switch()")
        self.log.info(f"Creating POAP switches for {len(self.proposed)} configuration(s)")
        
        all_responses = []
        
        # Process each switch configuration
        for switch in self.proposed:
            seed_ip = switch.seed_ip
            self.log.info(f"Processing POAP switch: {seed_ip}")
            self.log.debug(f"Switch config: {switch.model_dump(by_alias=True)}")
            
            responses = []
            
            # Handle different input formats
            poap_configs: List[POAPConfigModel] = []
            
            if isinstance(switch, SwitchConfigModel):
                # Use validated POAPConfigModel from SwitchConfigModel
                if switch.poap:
                    poap_configs = switch.poap
            elif isinstance(switch, BootstrapImportSwitchModel):
                # Legacy support - convert to dict for processing
                poap_configs = [switch]  # type: ignore
            elif isinstance(switch, dict):
                # Legacy dict support - validate as POAPConfigModel
                if 'poap' in switch:
                    raw_configs = switch['poap'] if isinstance(switch['poap'], list) else [switch['poap']]
                    for raw_config in raw_configs:
                        try:
                            poap_configs.append(POAPConfigModel.model_validate(raw_config))
                        except Exception as e:
                            self.log.error(f"Invalid POAP config: {e}")
                            raise
                elif 'bootstrap' in switch:
                    raw_configs = switch['bootstrap'] if isinstance(switch['bootstrap'], list) else [switch['bootstrap']]
                    for raw_config in raw_configs:
                        try:
                            poap_configs.append(POAPConfigModel.model_validate(raw_config))
                        except Exception as e:
                            self.log.error(f"Invalid bootstrap config: {e}")
                            raise
            
            for poap_config in poap_configs:
                response = self._poap_bootstrap(switch, poap_config)
                responses.append(response)
            
            all_responses.extend(responses)
        
        self.log.debug(f"EXIT: _create_poap_switch() -> {len(all_responses)} responses")
        return {"poap_responses": all_responses}
    
    def _poap_bootstrap(self, switch: Union[SwitchConfigModel, BootstrapImportSwitchModel, Dict[str, Any]], poap_config: Union[POAPConfigModel, BootstrapImportSwitchModel]) -> Dict[str, Any]:
        """
        Bootstrap a switch via POAP using POAPConfigModel and BootstrapImportSwitchModel.
        """
        self.log.debug("ENTER: _poap_bootstrap()")
        
        # Build endpoint using ep class
        endpoint = EpManageFabricSwitchActionsImportBootstrap()
        endpoint.fabric_name = self.fabric
        
        # Build BootstrapImportSwitchModel from POAPConfigModel or legacy config
        if isinstance(poap_config, BootstrapImportSwitchModel):
            bootstrap_model = poap_config
        elif isinstance(poap_config, POAPConfigModel):
            # Extract fields from validated POAPConfigModel
            serial_number = poap_config.serial_number
            hostname = poap_config.hostname
            ip = self._get_switch_field(switch, ['ip', 'seed_ip'])
            model = poap_config.model
            software_version = poap_config.version
            # Get gateway from config_data if present
            gateway_ip_mask = poap_config.config_data.gateway if poap_config.config_data else None
            image_policy = poap_config.image_policy
            switch_role = self._get_switch_field(switch, ['switch_role', 'switchRole', 'role'])
            password = self._get_switch_field(switch, ['password'])
            auth_proto = self._get_switch_field(switch, ['snmp_v3_auth_protocol', 'snmpV3AuthProtocol', 'auth_proto'])
            discovery_username = poap_config.discovery_username
            discovery_password = poap_config.discovery_password
            public_key = ''
            finger_print = ''
            # For bootstrap, serial_number present; for preprovision, preprovision_serial present
            in_inventory = bool(serial_number)
            
            bootstrap_model = BootstrapImportSwitchModel(
                gatewayIpMask=gateway_ip_mask,
                model=model,
                softwareVersion=software_version,
                imagePolicy=image_policy,
                switchRole=switch_role,
                password=password,
                discoveryAuthProtocol=auth_proto or SnmpV3AuthProtocol.MD5,
                hostname=hostname,
                ip=ip,
                serialNumber=serial_number,
                inInventory=in_inventory,
                publicKey=public_key,
                fingerPrint=finger_print
            )
        
        # Create request model
        request_model = ImportBootstrapSwitchesRequestModel(
            switches=[bootstrap_model]
        )
        
        self.log.debug(f"Bootstrap endpoint: {endpoint.path}")
        self.log.debug(f"Bootstrap payload (password masked): {self._mask_password(payload)}")
        payload = request_model.to_payload()
        self.log.info(f"Bootstrapping switch {bootstrap_model.serial_number}")
        
        # Make the request
        self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)
        
        # Get response and result from RestSend
        response = self.nd.rest_send.response_current
        result = self.nd.rest_send.result_current
        
        # Register the task result
        self.results.action = "bootstrap"
        self.results.response_current = response
        self.results.result_current = result
        self.results.diff_current = payload
        self.results.register_task_result()
        
        return response
    
    # =========================================================================
    # RMA Operations
    # =========================================================================
    
    def _create_rma_switch(self) -> Dict[str, Any]:
        """
        Create RMA (switch replacement) operations using RMAConfigModel.
        Processes all switches in self.proposed that have RMA configurations.
        
        Path: POST /fabrics/{fabricName}/switches/{switchId}/actions/provisionRMA
        """
        self.log.debug("ENTER: _create_rma_switch()")
        self.log.info(f"Creating RMA switches for {len(self.proposed)} configuration(s)")
        
        all_responses = []
        
        # Process each switch configuration
        for switch in self.proposed:
            seed_ip = switch.seed_ip
            self.log.info(f"Processing RMA switch: {seed_ip}")
            self.log.debug(f"Switch config: {switch.model_dump(by_alias=True)}")
            
            responses = []
            
            # Handle different input formats
            rma_configs: List[RMAConfigModel] = []
            
            if isinstance(switch, SwitchConfigModel):
                # Use validated RMAConfigModel from SwitchConfigModel
                if switch.rma:
                    rma_configs = switch.rma
            elif isinstance(switch, RMASwitchModel):
                # Legacy support - convert to RMAConfigModel (or process directly)
                rma_configs = [switch]  # type: ignore
            elif isinstance(switch, dict):
                # Legacy dict support - validate as RMAConfigModel
                if 'rma' in switch:
                    raw_configs = switch['rma'] if isinstance(switch['rma'], list) else [switch['rma']]
                    for raw_config in raw_configs:
                        try:
                            rma_configs.append(RMAConfigModel.model_validate(raw_config))
                        except Exception as e:
                            self.log.error(f"Invalid RMA config: {e}")
                            raise
            
            for rma_config in rma_configs:
                # Build RMASwitchModel from RMAConfigModel or legacy config
                if isinstance(rma_config, RMASwitchModel):
                    rma_model = rma_config
                    old_switch_id = rma_config.old_serial if hasattr(rma_config, 'old_serial') else None
                elif isinstance(rma_config, RMAConfigModel):
                    # Extract fields from validated RMAConfigModel
                    old_switch_id = rma_config.old_serial
                    new_switch_id = rma_config.serial_number
                    hostname = self._get_switch_field(switch, ['hostname'])
                    ip = seed_ip
                    model = rma_config.model
                    software_version = rma_config.version
                    gateway_ip_mask = rma_config.config_data.gateway
                    image_policy = rma_config.image_policy
                    switch_role = self._get_switch_field(switch, ['switch_role', 'switchRole', 'role'])
                    password = self._get_switch_field(switch, ['password'])
                    auth_proto = self._get_switch_field(switch, ['snmp_v3_auth_protocol', 'auth_proto'])
                    discovery_username = rma_config.discovery_username
                    discovery_password = rma_config.discovery_password
                    public_key = ''
                    finger_print = ''
                    
                    rma_model = RMASwitchModel(
                        gatewayIpMask=gateway_ip_mask,
                        model=model,
                        softwareVersion=software_version,
                        imagePolicy=image_policy,
                        switchRole=switch_role,
                        password=password,
                        discoveryAuthProtocol=auth_proto or SnmpV3AuthProtocol.MD5,
                        useNewCredentials=bool(discovery_username),
                        discoveryUsername=discovery_username,
                        discoveryPassword=discovery_password,
                        hostname=hostname,
                        ip=ip,
                        newSwitchId=new_switch_id,
                        publicKey=public_key,
                        fingerPrint=finger_print
                    )
            
                # Use the old switch ID in the path with ep class
                endpoint = EpManageFabricSwitchProvisionRMA()
                endpoint.fabric_name = self.fabric
                endpoint.switch_id = old_switch_id
                
                payload = rma_model.to_payload()
                
                self.log.info(
                    f"RMA: Replacing {old_switch_id} with {rma_model.new_switch_id}"
                )
                self.log.debug(f"RMA endpoint: {endpoint.path}")
                self.log.debug(f"RMA payload (password masked): {self._mask_password(payload)}")
                
                # Make the request
                self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)
                
                # Get response and result from RestSend
                response = self.nd.rest_send.response_current
                result = self.nd.rest_send.result_current
                
                # Register the task result
                self.results.action = "rma"
                self.results.response_current = response
                self.results.result_current = result
                self.results.diff_current = payload
                self.results.register_task_result()
                
                responses.append(response)
                self.log.debug(f"RMA request completed for {old_switch_id} -> {rma_model.new_switch_id}")
                
                # Wait for new switch to be manageable
                self.log.debug(f"Waiting for RMA switch {rma_model.new_switch_id} to become manageable")
                success = self.wait_utils.wait_for_switch_manageable([rma_model.new_switch_id])
                if not success:
                    self.log.warning(f"RMA switch {rma_model.new_switch_id} did not become manageable")
                else:
                    self.log.debug(f"RMA switch {rma_model.new_switch_id} is now manageable")
        return {"rma_responses": all_responses}
    
    # =========================================================================
    # Query Operations
    # =========================================================================
    
    def _query_all_switches(self) -> List[Dict[str, Any]]:
        """
        Query all switches from fabric.
        """
        try:
            # Build endpoint using ep class
            endpoint = EpManageFabricSwitchesGet()
            endpoint.fabric_name = self.fabric
            self.log.debug(f"Querying all switches with endpoint: {endpoint.path}")
            self.log.debug(f"Query verb: {endpoint.verb}")
            
            result = self.nd.request(path=endpoint.path, verb=endpoint.verb)
            # result = self.query_obj(endpoint.path)
            switches = result.get("switches", []) if result else []
            self.log.debug(f"Queried {len(switches)} switches from fabric {self.fabric}")
            return switches
        except Exception as e:
            self.log.error(f"Query all failed: {e}")
            return []
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _has_diff(self, existing_config: Dict[str, Any], proposed_config: Dict[str, Any]) -> bool:
        """
        Check if there's a difference between existing and proposed config.
        
        Args:
            existing_config: Current switch configuration from inventory
            proposed_config: Desired switch configuration from user
            
        Returns:
            True if differences found, False otherwise
        """
        self.log.debug("ENTER: _has_diff()")
        
        # Deep copy to avoid modifying original configs
        existing = deepcopy(existing_config)
        proposed = deepcopy(proposed_config)
        
        # Remove password fields (never compare passwords)
        for key in ["password", "discovery_password", "discoveryPassword"]:
            existing.pop(key, None)
            proposed.pop(key, None)
        
        # Remove read-only/computed fields that shouldn't trigger updates
        read_only_fields = [
            "switchId", "switch_id", "serialNumber", "serial_number",
            "model", "softwareVersion", "software_version",
            "status", "mode", "lastUpdated", "last_updated"
        ]
        for field in read_only_fields:
            existing.pop(field, None)
            proposed.pop(field, None)
        
        # Compare
        has_diff = existing != proposed
        
        if has_diff:
            self.log.debug(f"Configuration differences detected")
            self.log.debug(f"Existing (filtered): {existing}")
            self.log.debug(f"Proposed (filtered): {proposed}")
            # Calculate specific differences
            diff_keys = set(existing.keys()) | set(proposed.keys())
            differences = {}
            for key in diff_keys:
                existing_val = existing.get(key)
                proposed_val = proposed.get(key)
                if existing_val != proposed_val:
                    differences[key] = {"existing": existing_val, "proposed": proposed_val}
            self.log.debug(f"Specific differences: {differences}")
        else:
            self.log.debug("No configuration differences detected")
        
        self.log.debug(f"EXIT: _has_diff() -> {has_diff}")
        return has_diff
    
    def _remove_nested_key(self, data: Dict[str, Any], key_path: List[str]) -> None:
        """
        Remove a nested key from dictionary.
        """
        if not key_path or not isinstance(data, dict):
            return
        
        if len(key_path) == 1:
            data.pop(key_path[0], None)
        else:
            if key_path[0] in data:
                self._remove_nested_key(data[key_path[0]], key_path[1:])
    
    def _mask_password(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mask password fields in payload for logging.
        Returns a copy with passwords replaced by '***MASKED***'.
        """
        masked = deepcopy(payload)
        password_fields = ['password', 'discoveryPassword', 'discovery_password']
        
        def mask_recursive(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in password_fields:
                        obj[key] = '***MASKED***'
                    elif isinstance(value, (dict, list)):
                        mask_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    mask_recursive(item)
        
        mask_recursive(masked)
        return masked
    
    def _mask_password(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mask password fields in payload for logging.
        Returns a copy with passwords replaced by '***'.
        """
        masked = deepcopy(payload)
        password_fields = ['password', 'discoveryPassword', 'discovery_password']
        
        def mask_recursive(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in password_fields:
                        obj[key] = '***MASKED***'
                    elif isinstance(value, (dict, list)):
                        mask_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    mask_recursive(item)
        
        mask_recursive(masked)
        return masked
    
    def _log_operation(self, operation: str, identifier: str) -> None:
        """
        Log an operation for result output.
        """
        self.nd_logs.append({
            "operation": operation,
            "identifier": identifier,
            "status": "success"
        })
        self.results.changed = True
    
    def _finalize_operations(self) -> None:
        """
        Finalize operations - save and deploy config.
        """
        if self.nd.module.check_mode:
            return
        
        if self.nd_logs:  # Only if changes were made
            if self.save_config_flag:
                self.fabric_utils.save_config()
            
            if self.deploy_config_flag:
                # Get all serial numbers that were modified
                serial_numbers = []
                for switch in self.existing:
                    if hasattr(switch, 'switch_id') and switch.switch_id:
                        serial_numbers.append(switch.switch_id)
                
                if serial_numbers:
                    self.fabric_utils.deploy_config(serial_numbers)
    
    def exit_json(self) -> None:
        """
        Exit with results.
        """
        result = {
            "logs": self.nd_logs,
            "previous": [sw.model_dump(by_alias=True) for sw in self.previous] if self.previous else [],
            "current": [sw.model_dump(by_alias=True) for sw in self.existing] if self.existing else []
        }
        
        self.nd.module.exit_json(**result)