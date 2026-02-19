# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from copy import deepcopy
from typing import Optional, List, Dict, Any, Union, Tuple

from .nd_v2 import NDModule
from .enums import OperationType
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
)
from .ep.ep_api_v1_manage_fabric_discovery import EpManageFabricShallowDiscovery
from .ep.ep_api_v1_manage_fabric_switch_actions import (
    EpManageFabricSwitchProvisionRMA,
    EpManageFabricSwitchActionsImportBootstrap,
    EpManageFabricSwitchActionsRemove,
    EpManageFabricSwitchActionsChangeRoles,
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
                # Validate with SwitchConfigModel — pass state via context
                # so the model can apply state-aware defaults/enforcement
                validated = SwitchConfigModel.model_validate(
                    cfg, context={"state": self.state}
                )
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

        # For query/deleted, config is optional — operate on all switches when absent
        if self.state in ("query", "deleted"):
            proposed_config = None
            if self.config:
                proposed_config, _ = self._validate_configs(self.config)

            if self.state == "deleted":
                return self._handle_deleted_state(proposed_config)
            else:
                return self._handle_query_state(proposed_config)

        # merged / overridden — config is required
        if not self.config:
            self.nd.module.fail_json(
                msg=f"'config' is required for '{self.state}' state."
            )

        proposed_config, self.operation_type = self._validate_configs(self.config)

        discovered_data = self._discover_switches(proposed_config)
        try:
            for switch_proposed_config in proposed_config:
                seed_ip = switch_proposed_config.seed_ip
                discovered_switch = discovered_data.get(seed_ip)
                if discovered_switch:
                    # Add role from proposed config for comparison (if specified)
                    if switch_proposed_config.role is not None:
                        discovered_switch["role"] = switch_proposed_config.role
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
                self.log.debug(f"Transformed discovered data to model for switch: {seed_ip}")
        except Exception as e:
            self.log.error(f"Failed to transform discovered data to model: {e}")
        
        diff = self._compute_changes(self.proposed, self.existing)

        if self.state == "merged":
            return self._handle_merged_state(diff, proposed_config, discovered_data)
        elif self.state == "overridden":
            return self._handle_overridden_state(diff, proposed_config, discovered_data)
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

    def _handle_query_state(
        self,
        proposed_config: Optional[List[SwitchConfigModel]] = None,
    ) -> None:
        """Handle query state - return existing switches.

        Args:
            proposed_config: Optional list of SwitchConfigModel from playbook.
                If ``None``, all switches in the fabric are returned.
                If provided, only switches matching ``seed_ip`` (and
                optionally ``role``) are returned.

        Registers a single QUERY task result containing the matching
        switch inventory in ``response_current["DATA"]`` and an
        empty diff (no changes for query).
        """
        self.log.debug("ENTER: _handle_query_state()")
        self.log.info("Handling query state")
        self.log.debug(f"Found {len(self.existing)} existing switches")

        if proposed_config is None:
            # No config provided — return all switches
            matched_switches = list(self.existing)
            self.log.info("No proposed config — returning all existing switches")
        else:
            # Filter existing switches by proposed seed_ip + optional role
            matched_switches: List[SwitchDataModel] = []
            for cfg in proposed_config:
                match = next(
                    (
                        sw for sw in self.existing
                        if sw.fabric_management_ip == cfg.seed_ip
                    ),
                    None,
                )
                if match is None:
                    self.log.info(
                        f"Switch {cfg.seed_ip} not found in fabric"
                    )
                    continue

                # If the user specified a role, verify it matches
                if cfg.role is not None and match.switch_role != cfg.role:
                    self.log.info(
                        f"Switch {cfg.seed_ip} found but role mismatch: "
                        f"expected {cfg.role.value}, got "
                        f"{match.switch_role.value if match.switch_role else 'None'}"
                    )
                    continue

                matched_switches.append(match)

            self.log.info(
                f"Matched {len(matched_switches)}/{len(proposed_config)} "
                f"switch(es) from proposed config"
            )

        switch_data = [
            sw.model_dump(by_alias=True) for sw in matched_switches
        ]

        # Populate Results with proper metadata
        self.results.action = "query"
        self.results.state = self.state
        self.results.check_mode = self.nd.module.check_mode
        self.results.operation_type = OperationType.QUERY

        self.results.response_current = {
            "RETURN_CODE": 200,
            "MESSAGE": "OK",
            "DATA": switch_data,
        }
        self.results.result_current = {
            "found": len(matched_switches) > 0,
            "success": True,
        }
        self.results.diff_current = {}
        self.results.register_task_result()

        self.log.debug(
            f"Returning {len(switch_data)} switches in results"
        )
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
        self, diff, proposed_config, discovered_data=None
    ) -> None:
        """
        Handle merged state - add new switches and process migration mode switches.
        
        Workflow:
        1. Log idempotent switches (no-op)
        2. Warn about to_update (not supported in merged)
        3. Bulk add new switches (to_add) to fabric
        4. Collect migration mode switches
        5. COMMON post-processing for ALL actionable switches:
           - Wait for manageability
           - Save credentials
           - Assign role
        6. Finalize (config-save + config-deploy)
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
            return

        # Build config lookup: seed_ip -> SwitchConfigModel (for credentials/role)
        config_by_ip = {sw.seed_ip: sw for sw in proposed_config}

        # Phase 1: Log idempotent switches
        for sw in diff.get("idempotent", []):
            self.log.info(
                f"Switch {sw.fabric_management_ip} ({sw.switch_id}) "
                f"is idempotent - no changes needed"
            )

        # Phase 2: Warn about to_update (merged state doesn't support updates)
        if diff.get("to_update"):
            ips = [sw.fabric_management_ip for sw in diff["to_update"]]
            self.log.warning(
                f"Switches require updates which is not supported in merged state. "
                f"Use overridden state for updates. Affected switches: {ips}"
            )

        # Determine switches needing action
        switches_to_add = diff.get("to_add", [])
        migration_switches = diff.get("migration_mode", [])

        if not switches_to_add and not migration_switches:
            self.log.info("No switches need adding or migration processing")
            self.results.changed = False
            self.results.register_final_result()
            return

        # Check mode - preview only
        if self.nd.module.check_mode:
            self.log.info(
                f"Check mode: would add {len(switches_to_add)} and "
                f"process {len(migration_switches)} migration switches"
            )
            self.results.changed = True
            self.results.register_final_result()
            return

        # POAP / RMA have their own workflows - delegate and return
        if self.operation_type == "poap":
            self._create_poap_switch()
            self.results.changed = True
            self.results.register_final_result()
            return
        elif self.operation_type == "rma":
            self._create_rma_switch()
            self.results.changed = True
            self.results.register_final_result()
            return

        # ==================================================================
        # Normal switch workflow
        # ==================================================================
        # switch_actions collects (serial_number, SwitchConfigModel) pairs
        # for COMMON post-processing (wait, save creds, assign role).
        switch_actions: List[Tuple[str, SwitchConfigModel]] = []

        # Phase 3: Bulk add new switches to fabric
        if switches_to_add and discovered_data:
            add_configs = []
            for sw in switches_to_add:
                cfg = config_by_ip.get(sw.fabric_management_ip)
                if cfg:
                    add_configs.append(cfg)
                else:
                    self.log.warning(
                        f"No config found for switch {sw.fabric_management_ip}, skipping add"
                    )

            if add_configs:
                credential_groups = self._group_switches_by_credentials(add_configs)
                for group_key, group_switches in credential_groups.items():
                    username, password_hash, auth_proto, platform_type, preserve_config = group_key
                    password = group_switches[0].password

                    # Build (config, discovered_dict) pairs
                    pairs = []
                    for cfg in group_switches:
                        disc = discovered_data.get(cfg.seed_ip)
                        if disc:
                            pairs.append((cfg, disc))
                        else:
                            self.log.warning(f"No discovery data for {cfg.seed_ip}, skipping")

                    if not pairs:
                        continue

                    self._bulk_add_switches_to_fabric(
                        switches=pairs,
                        username=username,
                        password=password,
                        auth_proto=auth_proto,
                        platform_type=platform_type,
                        preserve_config=preserve_config,
                    )

                    # Collect serial numbers for post-processing
                    for cfg, disc in pairs:
                        sn = disc.get("serialNumber")
                        if sn:
                            switch_actions.append((sn, cfg))
                            self._log_operation("add", cfg.seed_ip)

        # Phase 4: Collect migration switches for post-processing
        for mig_sw in migration_switches:
            cfg = config_by_ip.get(mig_sw.fabric_management_ip)
            if cfg and mig_sw.switch_id:
                switch_actions.append((mig_sw.switch_id, cfg))
                self._log_operation("migrate", mig_sw.fabric_management_ip)

        if not switch_actions:
            self.log.info("No switch actions to process after add/migration collection")
            self.results.changed = False
            self.results.register_final_result()
            return

        # ==================================================================
        # COMMON post-processing for ALL switches (new + migration)
        # ==================================================================
        all_serial_numbers = [sn for sn, _ in switch_actions]

        # Step 1: Wait for all switches to be manageable
        self.log.info(
            f"Waiting for {len(all_serial_numbers)} switch(es) to become manageable: "
            f"{all_serial_numbers}"
        )
        success = self.wait_utils.wait_for_switch_manageable(all_serial_numbers)
        if not success:
            self.log.warning("Some switches did not become fully manageable")

        # Step 2: Save credentials for all switches (bulk, grouped by creds)
        self._bulk_save_credentials(switch_actions)

        # Step 3: Assign roles for all switches (single bulk API call)
        self._bulk_update_roles(switch_actions)

        # Step 4: Finalize (config-save + config-deploy)
        self._finalize_operations(all_serial_numbers)

        self.results.changed = True
        self.results.register_final_result()
        self.log.debug(
            f"EXIT: _handle_merged_state() - completed with changed={self.results.changed}"
        )
    
    def _handle_overridden_state(self, diff, proposed_config, discovered_data=None) -> None:
        """
        Handle overridden state - ensure only proposed switches exist in the fabric.
        
        Workflow:
        1. Delete switches not in proposed config (to_delete)
        2. Delete switches that need updating (to_update), then re-add them
        3. Delegate to _handle_merged_state for adds + migration processing
        """
        self.log.debug("ENTER: _handle_overridden_state()")
        self.log.info("Handling overridden state")

        if not self.proposed:
            self.log.warning("No configurations provided for overridden state")
            self.results.changed = False
            self.results.register_final_result()
            return

        # Check mode - preview only
        if self.nd.module.check_mode:
            n_delete = len(diff.get("to_delete", []))
            n_update = len(diff.get("to_update", []))
            n_add = len(diff.get("to_add", []))
            n_migrate = len(diff.get("migration_mode", []))
            self.log.info(
                f"Check mode: would delete {n_delete}, "
                f"delete-and-re-add {n_update}, "
                f"add {n_add}, migrate {n_migrate}"
            )
            self.results.changed = (n_delete + n_update + n_add + n_migrate) > 0
            self.results.register_final_result()
            return

        # Collect all switches that need deletion
        switches_to_delete: List[SwitchDataModel] = []

        # Phase 1: Switches not in proposed config
        for sw in diff.get("to_delete", []):
            self.log.info(
                f"Marking for deletion (not in proposed): "
                f"{sw.fabric_management_ip} ({sw.switch_id})"
            )
            switches_to_delete.append(sw)
            self._log_operation("delete", sw.fabric_management_ip)

        # Phase 2: Switches that need updating (delete-then-re-add)
        for sw in diff.get("to_update", []):
            existing_sw = next(
                (e for e in self.existing
                 if e.switch_id == sw.switch_id
                 or e.fabric_management_ip == sw.fabric_management_ip),
                None,
            )
            if existing_sw:
                self.log.info(
                    f"Marking for deletion (re-add update): "
                    f"{existing_sw.fabric_management_ip} ({existing_sw.switch_id})"
                )
                switches_to_delete.append(existing_sw)
                self._log_operation("delete_for_update", existing_sw.fabric_management_ip)

            # Move to to_add so merged state will re-add it
            diff["to_add"].append(sw)

        # Bulk delete all collected switches in one API call
        if switches_to_delete:
            self._bulk_delete_switches(switches_to_delete)

        # Clear to_update — they've been moved to to_add
        diff["to_update"] = []

        # Phase 3: Delegate add + migration to merged state
        self._handle_merged_state(diff, proposed_config, discovered_data)
        self.log.debug("EXIT: _handle_overridden_state()")
    
    def _handle_deleted_state(
        self,
        proposed_config: Optional[List[SwitchConfigModel]] = None,
    ) -> None:
        """
        Handle deleted state - remove specified switches.
        
        Args:
            proposed_config: Optional validated SwitchConfigModel list.
                If ``None``, **all** switches in the fabric are deleted.
                If provided, only switches matching ``seed_ip`` are deleted.
                Discovery is skipped for deleted state — matching is done
                against the existing inventory by ``seed_ip``.
        """
        self.log.debug("ENTER: _handle_deleted_state()")
        self.log.info("Handling deleted state")

        # Determine which switches to target
        if proposed_config is None:
            # No config — delete ALL switches in fabric
            switches_to_delete = list(self.existing)
            self.log.info(
                f"No proposed config — targeting all {len(switches_to_delete)} "
                f"existing switch(es) for deletion"
            )
            for sw in switches_to_delete:
                self._log_operation("delete", sw.fabric_management_ip)
        else:
            # Match proposed seed_ips against existing inventory
            switches_to_delete: List[SwitchDataModel] = []
            for switch_config in proposed_config:
                identifier = switch_config.seed_ip
                existing_switch = next(
                    (sw for sw in self.existing if sw.fabric_management_ip == identifier),
                    None,
                )
                if existing_switch:
                    self.log.info(f"Marking for deletion: {identifier} ({existing_switch.switch_id})")
                    switches_to_delete.append(existing_switch)
                    self._log_operation("delete", identifier)
                else:
                    self.log.info(f"Switch not found for deletion: {identifier}")

        if not switches_to_delete:
            self.log.info("No switches to delete")
            self.results.changed = False
            self.results.register_final_result()
            return

        # Check mode - preview only
        if self.nd.module.check_mode:
            self.log.info(f"Check mode: would delete {len(switches_to_delete)} switch(es)")
            self.results.changed = True
            self.results.register_final_result()
            return

        # Bulk delete all collected switches in one API call
        deleted_serial_numbers = self._bulk_delete_switches(switches_to_delete)
        self._finalize_operations(deleted_serial_numbers)
        self.results.changed = True

        self.results.register_final_result()
        self.log.debug("EXIT: _handle_deleted_state()")
    
    # =========================================================================
    # Switch Operations
    # =========================================================================
    
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
    
    def _bulk_delete_switches(
        self,
        switches: List[Union[SwitchDataModel, SwitchDiscoveryModel]],
    ) -> List[str]:
        """
        Delete (remove) multiple switches from fabric in a single API call.

        Uses the ``/switchActions/remove`` bulk endpoint instead of deleting
        one switch at a time.

        Args:
            switches: List of switch models to delete.

        Returns:
            List of serial numbers that were successfully submitted for deletion.
        """
        self.log.debug("ENTER: _bulk_delete_switches()")

        if self.nd.module.check_mode:
            self.log.debug("Check mode: Skipping actual deletion")
            return []

        # Collect serial numbers from switch models
        serial_numbers: List[str] = []
        for switch in switches:
            sn = None
            if hasattr(switch, 'switch_id'):
                sn = switch.switch_id
            elif hasattr(switch, 'serial_number'):
                sn = switch.serial_number

            if sn:
                serial_numbers.append(sn)
            else:
                ip = getattr(switch, 'fabric_management_ip', None) or getattr(switch, 'ip', None)
                self.log.warning(f"Cannot delete switch {ip}: no serial number/switch_id")

        if not serial_numbers:
            self.log.warning("No valid serial numbers found for deletion")
            self.log.debug("EXIT: _bulk_delete_switches() - nothing to delete")
            return []

        # Build bulk-remove endpoint
        endpoint = EpManageFabricSwitchActionsRemove()
        endpoint.fabric_name = self.fabric

        payload = {"switchIds": serial_numbers}

        self.log.info(
            f"Bulk removing {len(serial_numbers)} switch(es) from fabric "
            f"{self.fabric}: {serial_numbers}"
        )
        self.log.debug(f"Delete endpoint: {endpoint.path}")
        self.log.debug(f"Delete payload: {payload}")

        try:
            self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)

            response = self.nd.rest_send.response_current
            result = self.nd.rest_send.result_current

            # Register the task result
            self.results.action = "delete"
            self.results.response_current = response
            self.results.result_current = result
            self.results.diff_current = {"deleted": serial_numbers}
            self.results.register_task_result()

            self.log.info(
                f"Bulk delete submitted for {len(serial_numbers)} switch(es)"
            )
            self.log.debug("EXIT: _bulk_delete_switches()")
            return serial_numbers

        except Exception as e:
            self.log.error(f"Bulk delete failed: {e}")
            raise SwitchOperationError(
                f"Bulk delete failed for {serial_numbers}: {e}"
            ) from e
    
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
            # Extract grouping fields — model provides all defaults
            username = switch.user_name
            password = switch.password
            auth_proto = switch.auth_proto
            platform_type = switch.platform_type
            preserve_config = switch.preserve_config
            
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

        credential_groups = self._group_switches_by_credentials(configs)
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
    
    def _bulk_save_credentials(
        self,
        switch_actions: List[Tuple[str, SwitchConfigModel]],
    ) -> None:
        """
        Save credentials for switches in bulk.

        Groups switches by (username, password) and makes one API call
        per credential group, sending all ``switchIds`` in a single
        ``SwitchCredentialsRequestModel`` payload.

        Args:
            switch_actions: List of (serial_number, SwitchConfigModel) pairs.
        """
        self.log.debug("ENTER: _bulk_save_credentials()")

        # Group serial numbers by (username, password)
        cred_groups: Dict[Tuple[str, str], List[str]] = {}
        for sn, cfg in switch_actions:
            if not cfg.user_name or not cfg.password:
                self.log.debug(
                    f"Skipping credentials for {sn}: missing user_name or password"
                )
                continue
            key = (cfg.user_name, cfg.password)
            cred_groups.setdefault(key, []).append(sn)

        if not cred_groups:
            self.log.debug(
                "EXIT: _bulk_save_credentials() - no credentials to save"
            )
            return

        endpoint = EpManageCredentialsSwitchesCreate()

        for (username, password), serial_numbers in cred_groups.items():
            creds_request = SwitchCredentialsRequestModel(
                switchIds=serial_numbers,
                switchUsername=username,
                switchPassword=password,
            )
            payload = creds_request.to_payload()

            self.log.info(
                f"Saving credentials for {len(serial_numbers)} switch(es): "
                f"{serial_numbers}"
            )
            self.log.debug(f"Credentials endpoint: {endpoint.path}")
            self.log.debug(
                f"Credentials payload (masked): "
                f"{self._mask_password(payload)}"
            )

            try:
                self.nd.request(
                    path=endpoint.path,
                    verb=endpoint.verb,
                    data=payload,
                )

                response = self.nd.rest_send.response_current
                result = self.nd.rest_send.result_current

                self.results.action = "save_credentials"
                self.results.response_current = response
                self.results.result_current = result
                self.results.diff_current = {
                    "switchIds": serial_numbers,
                    "username": username,
                }
                self.results.register_task_result()
                self.log.info(
                    f"Credentials saved for {len(serial_numbers)} switch(es)"
                )
            except Exception as e:
                self.log.warning(
                    f"Failed to save credentials for "
                    f"{serial_numbers}: {e}"
                )

        self.log.debug("EXIT: _bulk_save_credentials()")

    def _bulk_update_roles(
        self,
        switch_actions: List[Tuple[str, SwitchConfigModel]],
    ) -> None:
        """
        Update switch roles in bulk using the ``changeRoles`` endpoint.

        Sends a single API call with all ``switchRoles`` assignments:
        ``{"switchRoles": [{"switchId": "SN", "role": "leaf"}, ...]}``

        Args:
            switch_actions: List of (serial_number, SwitchConfigModel) pairs.
        """
        self.log.debug("ENTER: _bulk_update_roles()")

        # Build the switchRoles array
        switch_roles = []
        for sn, cfg in switch_actions:
            role = self._get_switch_field(cfg, ['role'])
            if not role:
                continue
            role_value = (
                role.value if isinstance(role, SwitchRole) else str(role)
            )
            switch_roles.append(
                {"switchId": sn, "role": role_value}
            )

        if not switch_roles:
            self.log.debug(
                "EXIT: _bulk_update_roles() - no roles to update"
            )
            return

        endpoint = EpManageFabricSwitchActionsChangeRoles()
        endpoint.fabric_name = self.fabric

        payload = {"switchRoles": switch_roles}

        self.log.info(
            f"Bulk updating roles for {len(switch_roles)} switch(es)"
        )
        self.log.debug(f"ChangeRoles endpoint: {endpoint.path}")
        self.log.debug(f"ChangeRoles payload: {payload}")

        try:
            self.nd.request(
                path=endpoint.path,
                verb=endpoint.verb,
                data=payload,
            )

            response = self.nd.rest_send.response_current
            result = self.nd.rest_send.result_current

            self.results.action = "update_role"
            self.results.response_current = response
            self.results.result_current = result
            self.results.diff_current = payload
            self.results.register_task_result()
            self.log.info(
                f"Roles updated for {len(switch_roles)} switch(es)"
            )
        except Exception as e:
            self.log.warning(
                f"Failed to bulk update roles: {e}"
            )

        self.log.debug("EXIT: _bulk_update_roles()")
    
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

        The ND API ``GET /fabrics/{fabricName}/switches`` returns the
        switch list directly as response DATA.  ``nd.request()``
        already unwraps ``response["DATA"]``, so the return value is
        either a ``list`` of switch dicts or, in some ND versions, a
        ``dict`` with a ``"switches"`` key.  Handle both.

        Returns:
            List of raw switch dicts from the controller.

        Raises:
            Exception: Propagated from ``nd.request()`` on API errors
                       so that ``__init__`` fails visibly.
        """
        endpoint = EpManageFabricSwitchesGet()
        endpoint.fabric_name = self.fabric
        self.log.debug(f"Querying all switches with endpoint: {endpoint.path}")
        self.log.debug(f"Query verb: {endpoint.verb}")

        result = self.nd.request(path=endpoint.path, verb=endpoint.verb)

        # Normalise: result is either a list or a dict with a
        # "switches" key depending on ND version.
        if isinstance(result, list):
            switches = result
        elif isinstance(result, dict):
            switches = result.get("switches", [])
        else:
            switches = []

        self.log.debug(
            f"Queried {len(switches)} switches from fabric {self.fabric}"
        )
        return switches
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    
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
    
    def _finalize_operations(self, serial_numbers: List[str] = None) -> None:
        """
        Finalize operations - save and deploy config.
        
        Args:
            serial_numbers: Explicit list of switch serial numbers that were
                            modified. Used for targeted config-deploy.
        """
        if self.nd.module.check_mode:
            return

        if self.save_config_flag:
            self.log.info("Saving fabric configuration")
            self.fabric_utils.save_config()

        if self.deploy_config_flag and serial_numbers:
            self.log.info(f"Deploying configuration for {len(serial_numbers)} switch(es)")
            self.fabric_utils.deploy_config(serial_numbers)
    
    def exit_json(self) -> None:
        """
        Build final result from all registered tasks and exit.

        Merges the Results aggregation with supplemental data
        (logs, previous/current inventory snapshots) and delegates
        to ``ansible_module.exit_json`` / ``fail_json``.
        """
        self.results.build_final_result()
        final = self.results.final_result

        # Attach supplemental data that is not part of the
        # per-task Results flow.
        final["logs"] = self.nd_logs
        final["previous"] = (
            [sw.model_dump(by_alias=True) for sw in self.previous]
            if self.previous
            else []
        )
        final["current"] = (
            [sw.model_dump(by_alias=True) for sw in self.existing]
            if self.existing
            else []
        )

        if True in self.results.failed:
            self.nd.module.fail_json(**final)
        self.nd.module.exit_json(**final)