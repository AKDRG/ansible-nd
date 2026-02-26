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
from .models.switch_inventory_models import (
    SwitchRole,
    SnmpV3AuthProtocol,
    PlatformType,
    RemoteCredentialStore,
    DiscoveryStatus,
    SystemMode,
    SwitchDiscoveryModel,
    SwitchDataModel,
    AddSwitchesRequestModel,
    ShallowDiscoveryRequestModel,
    BootstrapImportSwitchModel,
    ImportBootstrapSwitchesRequestModel,
    PreProvisionSwitchModel,
    PreProvisionSwitchesRequestModel,
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
from .ep.ep_api_v1_manage_fabric_bootstrap import EpManageFabricBootstrapGet
from .ep.ep_api_v1_manage_fabric_discovery import EpManageFabricShallowDiscovery
from .ep.ep_api_v1_manage_fabric_switch_actions import (
    EpManageFabricSwitchProvisionRMA,
    EpManageFabricSwitchActionsImportBootstrap,
    EpManageFabricSwitchActionsPreProvision,
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

        Per-config validation (state restrictions, POAP/RMA mutual exclusivity,
        credential enforcement, role defaults) is handled automatically by
        ``SwitchConfigModel`` validators during ``model_validate()``.

        Cross-config validation (mixed operation types) is handled by
        ``SwitchConfigModel.validate_no_mixed_operations()``.

        Args:
            config: Raw configuration from ansible module params. Can be:
                    - Single dict with switch config
                    - List of dicts with multiple switch configs

        Returns:
            Tuple of (validated configs list, operation_type string)

        Raises:
            ValidationError: If config validation fails or mixed operation types detected
        """
        self.log.debug(f"ENTER: _validate_configs()")

        # Normalize config to list
        configs_list = config if isinstance(config, list) else [config]
        self.log.debug(f"Normalized to {len(configs_list)} configuration(s)")

        # Validate each config — model handles state checks,
        # POAP/RMA exclusivity, credential enforcement, role defaults
        validated_configs: List[SwitchConfigModel] = []
        for idx, cfg in enumerate(configs_list):
            try:
                validated = SwitchConfigModel.model_validate(
                    cfg, context={"state": self.state}
                )
                validated_configs.append(validated)
            except Exception as e:
                error_msg = (
                    f"Configuration validation failed for "
                    f"config index {idx}: {str(e)}"
                )
                self.log.error(error_msg)
                if hasattr(self.nd, 'module'):
                    self.nd.module.fail_json(msg=error_msg)
                else:
                    raise ValueError(error_msg) from e

        if not validated_configs:
            self.log.warning("No valid configurations found in input")
            return validated_configs, "unknown"

        # Cross-config check — model can't do this per-instance
        try:
            SwitchConfigModel.validate_no_mixed_operations(
                validated_configs
            )
        except ValueError as e:
            error_msg = str(e)
            self.log.error(error_msg)
            if hasattr(self.nd, 'module'):
                self.nd.module.fail_json(msg=error_msg)
            else:
                raise

        # Operation type is uniform (validated above)
        operation_type = validated_configs[0].operation_type

        self.log.info(
            f"Successfully validated {len(validated_configs)} "
            f"configuration(s) with operation type: "
            f"{operation_type}"
        )
        self.log.debug(
            f"EXIT: _validate_configs() -> "
            f"{len(validated_configs)} configs, "
            f"operation_type={operation_type}"
        )
        return validated_configs
    
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
                proposed_config = self._validate_configs(self.config)

            if self.state == "deleted":
                return self._handle_deleted_state(proposed_config)
            else:
                return self._handle_query_state(proposed_config)

        # merged / overridden — config is required
        if not self.config:
            self.nd.module.fail_json(
                msg=f"'config' is required for '{self.state}' state."
            )

        proposed_config = self._validate_configs(self.config)
        self.operation_type = proposed_config[0].operation_type

        # POAP bypasses normal discovery — handle it separately and return
        if self.operation_type == "poap":
            return self._handle_poap_state(proposed_config)

        # RMA bypasses normal discovery — handle it separately and return
        if self.operation_type == "rma":
            return self._handle_rma_state(proposed_config)

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
        self.log.debug("ENTER: _compute_changes()")
        self.log.debug(
            f"Comparing {len(proposed)} proposed vs {len(existing)} existing switches"
        )

        # Build index by switch_id for O(1) lookups
        existing_by_id = {sw.switch_id: sw for sw in existing}
        proposed_by_id = {sw.switch_id: sw for sw in proposed}
        
        # Also index by IP (for switches not yet discovered)
        existing_by_ip = {sw.fabric_management_ip: sw for sw in existing}

        self.log.debug(
            f"Indexes built — existing_by_id: {list(existing_by_id.keys())}, "
            f"existing_by_ip: {list(existing_by_ip.keys())}"
        )
        
        # Fields to INCLUDE in comparison — only user-controllable fields
        # that are populated by both discovery and inventory APIs.
        # Everything else (fabric metadata, uptime, alerts, additionalData,
        # vpc info, telemetry, etc.) is server-managed and must be ignored.
        compare_fields = {
            "switch_id",
            "serial_number",
            "fabric_management_ip",
            "hostname",
            "model",
            "software_version",
            "switch_role",
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
            ip = prop_sw.fabric_management_ip
            sid = prop_sw.switch_id

            # Try to find match by switch_id first
            existing_sw = existing_by_id.get(sid)
            match_key = "switch_id" if existing_sw else None
            
            # If not found by switch_id, try by IP
            if not existing_sw:
                existing_sw = existing_by_ip.get(ip)
                if existing_sw:
                    match_key = "ip"

            if not existing_sw:
                self.log.info(
                    f"Switch {ip} (id={sid}) not found in existing — marking to_add"
                )
                changes["to_add"].append(prop_sw)
                continue

            self.log.debug(
                f"Switch {ip} matched existing by {match_key} "
                f"(existing_id={existing_sw.switch_id})"
            )

            # Check migration mode first
            if existing_sw.mode == "Migration":
                self.log.info(
                    f"Switch {ip} ({existing_sw.switch_id}) is in Migration mode"
                )
                changes["migration_mode"].append(prop_sw)
                continue
            
            # Compare models using only user-controllable fields
            prop_dict = prop_sw.model_dump(
                by_alias=True,
                exclude_none=True,
                include=compare_fields
            )
            
            existing_dict = existing_sw.model_dump(
                by_alias=True,
                exclude_none=True,
                include=compare_fields
            )
            
            if prop_dict == existing_dict:
                self.log.debug(f"Switch {ip} is idempotent — no changes needed")
                changes["idempotent"].append(prop_sw)
            else:
                # Log the specific differences
                diff_keys = {
                    k for k in set(prop_dict) | set(existing_dict)
                    if prop_dict.get(k) != existing_dict.get(k)
                }
                self.log.info(
                    f"Switch {ip} has differences — marking to_update. "
                    f"Changed fields: {diff_keys}"
                )
                self.log.debug(
                    f"Switch {ip} diff detail — "
                    f"proposed: { {k: prop_dict.get(k) for k in diff_keys} }, "
                    f"existing: { {k: existing_dict.get(k) for k in diff_keys} }"
                )
                changes["to_update"].append(prop_sw)
        
        # Find switches in existing but not in proposed (for overridden state)
        proposed_ids = {sw.switch_id for sw in proposed}
        for existing_sw in existing:
            if existing_sw.switch_id not in proposed_ids:
                self.log.info(
                    f"Existing switch {existing_sw.fabric_management_ip} "
                    f"({existing_sw.switch_id}) not in proposed — marking to_delete"
                )
                changes["to_delete"].append(existing_sw)

        self.log.info(
            f"Compute changes summary: "
            f"to_add={len(changes['to_add'])}, "
            f"to_update={len(changes['to_update'])}, "
            f"to_delete={len(changes['to_delete'])}, "
            f"migration_mode={len(changes['migration_mode'])}, "
            f"idempotent={len(changes['idempotent'])}"
        )
        self.log.debug("EXIT: _compute_changes()")
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

        # POAP and RMA are handled before discovery in manage_state()

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
        self._finalize_operations()

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
                self.log.debug(
                    f"Looking for switch to delete with seed IP: {switch_config.seed_ip}"
                )
                identifier = switch_config.seed_ip
                existing_switch = next(
                    (sw for sw in self.existing if sw.fabric_management_ip == identifier),
                    None,
                )
                if existing_switch:
                    self.log.info(f"Marking for deletion: {identifier} ({existing_switch.switch_id})")
                    switches_to_delete.append(existing_switch)
                    # self._log_operation("delete", identifier)
                else:
                    self.log.info(f"Switch not found for deletion: {identifier}")

        self.log.info(f"Total switches marked for deletion: {len(switches_to_delete)}")
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

        self.log.info(
            f"Proceeding to delete {len(switches_to_delete)} switch(es) from fabric"
        )
        # Bulk delete all collected switches in one API call
        deleted_serial_numbers = self._bulk_delete_switches(switches_to_delete)
        # self._finalize_operations(deleted_serial_numbers)
        # self.results.changed = True

        # self.results.register_final_result()
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
        # SwitchConfigModel exposes operation_type as a computed field
        if isinstance(switch, SwitchConfigModel):
            return switch.operation_type
        
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

    def _handle_poap_state(
        self, proposed_config: List[SwitchConfigModel]
    ) -> None:
        """
        Orchestrate the full POAP (bootstrap / pre-provision) workflow.

        Flow:
            1. Separate POAP entries into bootstrap (serial_number) and
               pre-provision (preprovision_serial) buckets.
            2. For bootstrap entries:
               a. Query the bootstrap API for switches in the POAP loop.
               b. Match each entry against the bootstrap data.
               c. Build BootstrapImportSwitchModel list.
               d. POST to importBootstrap.
            3. For pre-provision entries:
               a. Build PreProvisionSwitchModel list (no bootstrap API
                  query needed — the switch does not exist yet).
               b. POST to preProvision.
            4. Register results.

        This method is called from ``manage_state()`` *before* normal
        discovery so that POAP switches (which are not yet in the fabric
        inventory) never hit ``_discover_switches()``.
        """
        self.log.debug("ENTER: _handle_poap_state()")
        self.log.info(
            f"Processing POAP for {len(proposed_config)} switch config(s)"
        )

        # Check mode — preview only
        if self.nd.module.check_mode:
            self.log.info("Check mode: would run POAP bootstrap / pre-provision")
            self.results.action = "poap"
            self.results.response_current = {"MESSAGE": "check mode — skipped"}
            self.results.result_current = {"success": True, "changed": True}
            self.results.diff_current = {
                "poap_switches": [
                    pc.seed_ip for pc in proposed_config
                ]
            }
            self.results.register_task_result()
            self.results.register_final_result()
            return

        # ------------------------------------------------------------- #
        # Classify POAP entries into bootstrap vs pre-provision buckets
        # ------------------------------------------------------------- #
        bootstrap_entries: List[tuple] = []   # (SwitchConfigModel, POAPConfigModel)
        preprov_entries: List[tuple] = []     # (SwitchConfigModel, POAPConfigModel)

        for switch_cfg in proposed_config:
            if not switch_cfg.poap:
                self.log.warning(
                    f"Switch config for {switch_cfg.seed_ip} has no POAP "
                    f"block — skipping"
                )
                continue

            for poap_cfg in switch_cfg.poap:
                if poap_cfg.preprovision_serial:
                    preprov_entries.append((switch_cfg, poap_cfg))
                elif poap_cfg.serial_number:
                    bootstrap_entries.append((switch_cfg, poap_cfg))
                else:
                    self.log.warning(
                        f"POAP entry for {switch_cfg.seed_ip} has neither "
                        f"serial_number nor preprovision_serial — skipping"
                    )

        self.log.info(
            f"POAP classification: {len(bootstrap_entries)} bootstrap, "
            f"{len(preprov_entries)} pre-provision"
        )

        # ------------------------------------------------------------- #
        # Handle bootstrap entries (existing flow)
        # ------------------------------------------------------------- #
        if bootstrap_entries:
            bootstrap_switches = self._query_bootstrap_switches()
            bootstrap_index: Dict[str, Dict[str, Any]] = {
                sw.get("serialNumber", sw.get("serial_number", "")): sw
                for sw in bootstrap_switches
            }
            self.log.debug(
                f"Bootstrap index contains {len(bootstrap_index)} switch(es): "
                f"{list(bootstrap_index.keys())}"
            )

            import_models: List[BootstrapImportSwitchModel] = []
            for switch_cfg, poap_cfg in bootstrap_entries:
                serial = poap_cfg.serial_number
                bootstrap_data = bootstrap_index.get(serial)

                if not bootstrap_data:
                    msg = (
                        f"Serial {serial} not found in bootstrap API "
                        f"response. The switch is not in the POAP loop. "
                        f"Ensure the switch is powered on and POAP/DHCP "
                        f"is enabled in the fabric."
                    )
                    self.log.error(msg)
                    self.nd.module.fail_json(msg=msg)

                model = self._build_bootstrap_import_model(
                    switch_cfg, poap_cfg, bootstrap_data
                )
                import_models.append(model)
                self.log.info(
                    f"Built bootstrap model for serial={serial}, "
                    f"hostname={model.hostname}, ip={model.ip}"
                )

            if import_models:
                self._import_bootstrap_switches(import_models)

        # ------------------------------------------------------------- #
        # Handle pre-provision entries
        # ------------------------------------------------------------- #
        if preprov_entries:
            preprov_models: List[PreProvisionSwitchModel] = []
            for switch_cfg, poap_cfg in preprov_entries:
                pp_model = self._build_preprovision_model(
                    switch_cfg, poap_cfg
                )
                preprov_models.append(pp_model)
                self.log.info(
                    f"Built pre-provision model for serial="
                    f"{pp_model.serial_number}, hostname={pp_model.hostname}, "
                    f"ip={pp_model.ip}"
                )

            if preprov_models:
                self._preprovision_switches(preprov_models)

        # ------------------------------------------------------------- #
        # Edge case: nothing actionable
        # ------------------------------------------------------------- #
        if not bootstrap_entries and not preprov_entries:
            self.log.warning("No POAP switch models built — nothing to process")
            self.results.action = "poap"
            self.results.response_current = {"MESSAGE": "no switches to process"}
            self.results.result_current = {"success": True, "changed": False}
            self.results.diff_current = {}
            self.results.register_task_result()
            self.results.register_final_result()

        self.log.debug("EXIT: _handle_poap_state()")

    # --------------------------------------------------------------------- #

    def _query_bootstrap_switches(self) -> List[Dict[str, Any]]:
        """
        GET ``/fabrics/{fabricName}/bootstrap`` and return the list of
        switches currently in the bootstrap (POAP / PnP) loop.

        Returns:
            List of raw switch dicts from the bootstrap API.
        """
        self.log.debug("ENTER: _query_bootstrap_switches()")

        endpoint = EpManageFabricBootstrapGet()
        endpoint.fabric_name = self.fabric

        self.log.debug(f"Bootstrap endpoint: {endpoint.path}")

        result = self.nd.request(path=endpoint.path, verb=endpoint.verb)

        # The response may be a dict with a "switches" key or a list.
        if isinstance(result, dict):
            switches = result.get("switches", [])
        elif isinstance(result, list):
            switches = result
        else:
            switches = []

        self.log.info(
            f"Bootstrap API returned {len(switches)} switch(es) in POAP loop"
        )
        self.log.debug("EXIT: _query_bootstrap_switches()")
        return switches

    # --------------------------------------------------------------------- #

    def _build_bootstrap_import_model(
        self,
        switch_cfg: SwitchConfigModel,
        poap_cfg: POAPConfigModel,
        bootstrap_data: Optional[Dict[str, Any]],
    ) -> BootstrapImportSwitchModel:
        """
        Merge user-supplied POAP config with bootstrap API data to create
        a complete ``BootstrapImportSwitchModel``.

        Priority:
            * User config values always win.
            * Bootstrap API provides ``publicKey``, ``fingerPrint``,
              ``inInventory``, and ``dhcpBootstrapIp`` which the user
              normally does not supply.

        Args:
            switch_cfg:     The parent SwitchConfigModel (carries seed_ip,
                            role, password, auth_proto).
            poap_cfg:       The POAPConfigModel from the user playbook.
            bootstrap_data: The matching entry from the bootstrap GET API
                            (may be ``None`` for pre-provision).
        """
        self.log.debug(
            f"ENTER: _build_bootstrap_import_model(serial={poap_cfg.serial_number})"
        )

        bs = bootstrap_data or {}

        # --- fields from user config ---
        serial_number = poap_cfg.serial_number
        hostname = poap_cfg.hostname
        ip = switch_cfg.seed_ip
        model = poap_cfg.model
        version = poap_cfg.version
        image_policy = poap_cfg.image_policy
        gateway_ip_mask = poap_cfg.config_data.gateway if poap_cfg.config_data else None
        switch_role = switch_cfg.role
        password = switch_cfg.password
        # POAP/bootstrap always uses MD5 regardless of user-supplied auth_proto
        auth_proto = SnmpV3AuthProtocol.MD5

        discovery_username = getattr(poap_cfg, "discovery_username", None)
        discovery_password = getattr(poap_cfg, "discovery_password", None)

        # --- fields from bootstrap API response ---
        # The GET bootstrap API returns "fingerPrint" (capital P),
        # but the POST importBootstrap API expects "fingerprint" (lowercase).
        fingerprint = bs.get("fingerPrint", bs.get("fingerprint", ""))
        public_key = bs.get("publicKey", "")
        re_add = bs.get("reAdd", False)
        in_inventory = bs.get("inInventory", False)

        # --- optional data block (models / gateway) ---
        data_block: Optional[Dict[str, Any]] = None
        if poap_cfg.config_data:
            data_block = {}
            if gateway_ip_mask:
                data_block["gatewayIpMask"] = gateway_ip_mask
            if poap_cfg.config_data.models:
                data_block["models"] = poap_cfg.config_data.models

        bootstrap_model = BootstrapImportSwitchModel(
            serialNumber=serial_number,
            model=model,
            version=version,
            hostname=hostname,
            ipAddress=ip,
            password=password,
            discoveryAuthProtocol=auth_proto,
            discoveryUsername=discovery_username,
            discoveryPassword=discovery_password,
            data=data_block,
            fingerprint=fingerprint,
            publicKey=public_key,
            reAdd=re_add,
            inInventory=in_inventory,
            imagePolicy=image_policy or "",
            switchRole=switch_role,
            ip=ip,
            softwareVersion=version,
            gatewayIpMask=gateway_ip_mask,
        )

        self.log.debug(
            f"EXIT: _build_bootstrap_import_model() -> "
            f"{bootstrap_model.serial_number}"
        )
        return bootstrap_model

    # --------------------------------------------------------------------- #

    def _import_bootstrap_switches(
        self, models: List[BootstrapImportSwitchModel]
    ) -> None:
        """
        POST the list of ``BootstrapImportSwitchModel`` to the
        ``importBootstrap`` endpoint.

        Registers results per-switch for proper Ansible output.
        """
        self.log.debug("ENTER: _import_bootstrap_switches()")

        endpoint = EpManageFabricSwitchActionsImportBootstrap()
        endpoint.fabric_name = self.fabric

        request_model = ImportBootstrapSwitchesRequestModel(switches=models)
        payload = request_model.to_payload()

        self.log.debug(f"importBootstrap endpoint: {endpoint.path}")
        self.log.debug(
            f"importBootstrap payload (masked): "
            f"{self._mask_password(payload)}"
        )
        self.log.info(
            f"Importing {len(models)} bootstrap switch(es): "
            f"{[m.serial_number for m in models]}"
        )

        # Make the request
        self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)

        # Capture response
        response = self.nd.rest_send.response_current
        result = self.nd.rest_send.result_current

        # Register task result
        self.results.action = "bootstrap"
        self.results.response_current = response
        self.results.result_current = result
        self.results.diff_current = payload
        self.results.register_task_result()

        self.log.info(
            f"importBootstrap API response success: {result.get('success')}"
        )
        self.log.debug("EXIT: _import_bootstrap_switches()")

    # --------------------------------------------------------------------- #
    # Pre-Provision helpers
    # --------------------------------------------------------------------- #

    def _build_preprovision_model(
        self,
        switch_cfg: SwitchConfigModel,
        poap_cfg: POAPConfigModel,
    ) -> PreProvisionSwitchModel:
        """
        Build a ``PreProvisionSwitchModel`` from the user-supplied POAP
        config.  Pre-provision does **not** require a bootstrap API query
        because the switch does not physically exist yet.

        Args:
            switch_cfg: The parent SwitchConfigModel (carries seed_ip,
                        role, password, auth_proto).
            poap_cfg:   The POAPConfigModel from the user playbook.
        """
        self.log.debug(
            f"ENTER: _build_preprovision_model("
            f"serial={poap_cfg.preprovision_serial})"
        )

        serial_number = poap_cfg.preprovision_serial
        hostname = poap_cfg.hostname
        ip = switch_cfg.seed_ip
        model_name = poap_cfg.model
        version = poap_cfg.version
        image_policy = poap_cfg.image_policy
        gateway_ip_mask = poap_cfg.config_data.gateway if poap_cfg.config_data else None
        switch_role = switch_cfg.role
        password = switch_cfg.password
        # POAP/preprovision always uses MD5 regardless of user-supplied auth_proto
        auth_proto = SnmpV3AuthProtocol.MD5

        discovery_username = getattr(poap_cfg, "discovery_username", None)
        discovery_password = getattr(poap_cfg, "discovery_password", None)

        # --- optional data block (models / gateway) ---
        data_block: Optional[Dict[str, Any]] = None
        if poap_cfg.config_data:
            data_block = {}
            if gateway_ip_mask:
                data_block["gatewayIpMask"] = gateway_ip_mask
            if poap_cfg.config_data.models:
                data_block["models"] = poap_cfg.config_data.models

        preprov_model = PreProvisionSwitchModel(
            serialNumber=serial_number,
            hostname=hostname,
            ip=ip,
            model=model_name,
            softwareVersion=version,
            gatewayIpMask=gateway_ip_mask,
            password=password,
            discoveryAuthProtocol=auth_proto,
            discoveryUsername=discovery_username,
            discoveryPassword=discovery_password,
            data=data_block,
            imagePolicy=image_policy or None,
            switchRole=switch_role,
        )

        self.log.debug(
            f"EXIT: _build_preprovision_model() -> "
            f"{preprov_model.serial_number}"
        )
        return preprov_model

    # --------------------------------------------------------------------- #

    def _preprovision_switches(
        self, models: List[PreProvisionSwitchModel]
    ) -> None:
        """
        POST the list of ``PreProvisionSwitchModel`` to the
        ``preProvision`` endpoint.

        Registers results per-call for proper Ansible output.
        """
        self.log.debug("ENTER: _preprovision_switches()")

        endpoint = EpManageFabricSwitchActionsPreProvision()
        endpoint.fabric_name = self.fabric

        request_model = PreProvisionSwitchesRequestModel(switches=models)
        payload = request_model.to_payload()

        self.log.debug(f"preProvision endpoint: {endpoint.path}")
        self.log.debug(
            f"preProvision payload (masked): "
            f"{self._mask_password(payload)}"
        )
        self.log.info(
            f"Pre-provisioning {len(models)} switch(es): "
            f"{[m.serial_number for m in models]}"
        )

        # Make the request
        self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)

        # Capture response
        response = self.nd.rest_send.response_current
        result = self.nd.rest_send.result_current

        # Register task result
        self.results.action = "preprovision"
        self.results.response_current = response
        self.results.result_current = result
        self.results.diff_current = payload
        self.results.register_task_result()

        self.log.info(
            f"preProvision API response success: {result.get('success')}"
        )
        self.log.debug("EXIT: _preprovision_switches()")

    # =========================================================================
    # RMA Operations
    # =========================================================================
    
    def _handle_rma_state(
        self, proposed_config: List[SwitchConfigModel]
    ) -> None:
        """
        Orchestrate the full RMA (Return Material Authorization) workflow.

        Flow:
            1. Collect all RMA entries from each SwitchConfigModel.
            2. Query the bootstrap API for switches in the POAP loop
               to obtain publicKey and fingerPrint for the new switch.
            3. For each RMA entry, build an ``RMASwitchModel`` and POST
               it to ``/switches/{oldSwitchId}/actions/provisionRMA``.
            4. Wait for each new switch to become manageable.
            5. Save credentials for each new switch.
            6. Config save and deploy.

        This method is called from ``manage_state()`` *before* normal
        discovery to prevent RMA switches from going through the
        regular add flow.
        """
        self.log.debug("ENTER: _handle_rma_state()")
        self.log.info(
            f"Processing RMA for {len(proposed_config)} switch config(s)"
        )

        # Check mode — preview only
        if self.nd.module.check_mode:
            self.log.info("Check mode: would run RMA provision")
            self.results.action = "rma"
            self.results.response_current = {"MESSAGE": "check mode — skipped"}
            self.results.result_current = {"success": True, "changed": True}
            self.results.diff_current = {
                "rma_switches": [
                    pc.seed_ip for pc in proposed_config
                ]
            }
            self.results.register_task_result()
            self.results.changed = True
            self.results.register_final_result()
            return

        # ------------------------------------------------------------- #
        # Collect all (SwitchConfigModel, RMAConfigModel) pairs
        # ------------------------------------------------------------- #
        rma_entries: List[Tuple[SwitchConfigModel, RMAConfigModel]] = []

        for switch_cfg in proposed_config:
            if not switch_cfg.rma:
                self.log.warning(
                    f"Switch config for {switch_cfg.seed_ip} has no RMA "
                    f"block — skipping"
                )
                continue

            for rma_cfg in switch_cfg.rma:
                rma_entries.append((switch_cfg, rma_cfg))

        if not rma_entries:
            self.log.warning("No RMA entries found — nothing to process")
            self.results.action = "rma"
            self.results.response_current = {"MESSAGE": "no switches to process"}
            self.results.result_current = {"success": True, "changed": False}
            self.results.diff_current = {}
            self.results.register_task_result()
            self.results.register_final_result()
            return

        self.log.info(f"Found {len(rma_entries)} RMA entry/entries to process")

        # ------------------------------------------------------------- #
        # Validate old switches exist and are in correct state
        # ------------------------------------------------------------- #
        old_switch_info = self._validate_rma_prerequisites(rma_entries)

        # ------------------------------------------------------------- #
        # Query bootstrap API for publicKey / fingerPrint of new switches
        # ------------------------------------------------------------- #
        bootstrap_switches = self._query_bootstrap_switches()
        bootstrap_index: Dict[str, Dict[str, Any]] = {
            sw.get("serialNumber", sw.get("serial_number", "")): sw
            for sw in bootstrap_switches
        }
        self.log.debug(
            f"Bootstrap index contains {len(bootstrap_index)} switch(es): "
            f"{list(bootstrap_index.keys())}"
        )

        # ------------------------------------------------------------- #
        # Build and submit each RMA request
        # ------------------------------------------------------------- #
        switch_actions: List[Tuple[str, SwitchConfigModel]] = []

        for switch_cfg, rma_cfg in rma_entries:
            new_serial = rma_cfg.serial_number
            bootstrap_data = bootstrap_index.get(new_serial)

            if not bootstrap_data:
                msg = (
                    f"New switch serial {new_serial} not found in "
                    f"bootstrap API response. The switch is not in the "
                    f"POAP loop. Ensure the replacement switch is powered "
                    f"on and POAP/DHCP is enabled in the fabric."
                )
                self.log.error(msg)
                self.nd.module.fail_json(msg=msg)

            rma_model = self._build_rma_model(
                switch_cfg, rma_cfg, bootstrap_data,
                old_switch_info[rma_cfg.old_serial],
            )
            self.log.info(
                f"Built RMA model: replacing {rma_cfg.old_serial} with "
                f"{rma_model.new_switch_id}"
            )

            self._provision_rma_switch(rma_cfg.old_serial, rma_model)
            switch_actions.append((rma_model.new_switch_id, switch_cfg))

        # ------------------------------------------------------------- #
        # Post-processing: wait, save credentials, finalize
        # ------------------------------------------------------------- #
        all_new_serials = [sn for sn, _ in switch_actions]

        # Wait for all new switches to become manageable
        self.log.info(
            f"Waiting for {len(all_new_serials)} RMA switch(es) to "
            f"become manageable: {all_new_serials}"
        )
        success = self.wait_utils.wait_for_switch_manageable(all_new_serials)
        if not success:
            self.log.warning(
                "One or more RMA switches did not become manageable"
            )

        # Save credentials for new switches
        self._bulk_save_credentials(switch_actions)

        # Config save and deploy
        self._finalize_operations()

        self.results.changed = True
        self.results.register_final_result()
        self.log.debug("EXIT: _handle_rma_state()")

    # --------------------------------------------------------------------- #

    def _validate_rma_prerequisites(
        self,
        rma_entries: List[Tuple[SwitchConfigModel, RMAConfigModel]],
    ) -> Dict[str, Dict[str, Any]]:
        """Validate that each old switch meets RMA prerequisites.

        For every ``(switch_cfg, rma_cfg)`` pair, verify:

        1. ``old_serial`` exists in the current fabric inventory.
        2. The switch's discovery status is **unreachable**.
        3. The switch's system mode is **maintenance**.

        Returns:
            Dict keyed by ``old_serial`` with:
                ``hostname``     – the existing switch's hostname
                ``switch_data``  – the full ``SwitchDataModel``
        """
        self.log.debug("ENTER: _validate_rma_prerequisites()")

        # Build lookup by serial from existing inventory
        existing_by_serial: Dict[str, SwitchDataModel] = {
            sw.serial_number: sw
            for sw in self.existing
            if sw.serial_number
        }

        result: Dict[str, Dict[str, Any]] = {}

        for switch_cfg, rma_cfg in rma_entries:
            old_serial = rma_cfg.old_serial

            # --- 1. Must exist in fabric inventory ---
            old_switch = existing_by_serial.get(old_serial)
            if old_switch is None:
                self.nd.module.fail_json(
                    msg=(
                        f"RMA: old_serial '{old_serial}' not found in "
                        f"fabric '{self.fabric}'. The switch being "
                        f"replaced must exist in the inventory."
                    )
                )

            ad = old_switch.additional_data

            if ad is None:
                self.nd.module.fail_json(
                    msg=(
                        f"RMA: Switch '{old_serial}' has no additional data "
                        f"in the inventory response. Cannot verify discovery "
                        f"status and system mode."
                    )
                )

            # --- 2. Discovery status must be unreachable ---
            # NOTE: use_enum_values=True in NDBaseModel stores plain
            # strings, so compare against the enum's .value.
            if ad.discovery_status != DiscoveryStatus.UNREACHABLE.value:
                self.nd.module.fail_json(
                    msg=(
                        f"RMA: Switch '{old_serial}' has discovery status "
                        f"'{ad.discovery_status or 'unknown'}', "
                        f"expected 'unreachable'. The old switch must be "
                        f"unreachable before RMA can proceed."
                    )
                )

            # --- 3. System mode must be maintenance ---
            if ad.system_mode != SystemMode.MAINTENANCE.value:
                self.nd.module.fail_json(
                    msg=(
                        f"RMA: Switch '{old_serial}' is in "
                        f"'{ad.system_mode or 'unknown'}' "
                        f"mode, expected 'maintenance'. Put the switch in "
                        f"maintenance mode before initiating RMA."
                    )
                )

            result[old_serial] = {
                "hostname": old_switch.hostname or "",
                "switch_data": old_switch,
            }
            self.log.info(
                f"RMA prerequisite check passed for old_serial "
                f"'{old_serial}' (hostname={old_switch.hostname}, "
                f"discovery={ad.discovery_status}, "
                f"mode={ad.system_mode})"
            )

        self.log.debug("EXIT: _validate_rma_prerequisites()")
        return result

    # --------------------------------------------------------------------- #

    def _build_rma_model(
        self,
        switch_cfg: SwitchConfigModel,
        rma_cfg: RMAConfigModel,
        bootstrap_data: Dict[str, Any],
        old_switch_info: Dict[str, Any],
    ) -> RMASwitchModel:
        """
        Merge user-supplied RMA config with bootstrap API data to create
        a complete ``RMASwitchModel``.

        Priority:
            * User config values always win.
            * Bootstrap API data supplies ``publicKey`` and ``fingerPrint``
              which the user normally does not know.
            * ``hostname`` is taken from the old switch's inventory record.

        Args:
            switch_cfg:      Parent SwitchConfigModel (carries seed_ip, role,
                             password).
            rma_cfg:         The RMAConfigModel from the user playbook.
            bootstrap_data:  Matching entry from the bootstrap GET API for the
                             **new** switch (serial = rma_cfg.serial_number).
            old_switch_info: Dict with ``hostname`` and ``switch_data`` from
                             ``_validate_rma_prerequisites``.
        """
        self.log.debug(
            f"ENTER: _build_rma_model(new={rma_cfg.serial_number}, "
            f"old={rma_cfg.old_serial})"
        )

        # --- fields from user config ---
        new_switch_id = rma_cfg.serial_number
        # Hostname comes from the old switch's inventory record
        hostname = old_switch_info.get("hostname", "")
        ip = switch_cfg.seed_ip
        model_name = rma_cfg.model
        version = rma_cfg.version
        image_policy = rma_cfg.image_policy
        gateway_ip_mask = rma_cfg.config_data.gateway
        switch_role = switch_cfg.role
        password = switch_cfg.password
        # RMA always uses MD5 — hardcoded, not user-configurable
        auth_proto = SnmpV3AuthProtocol.MD5

        discovery_username = rma_cfg.discovery_username
        discovery_password = rma_cfg.discovery_password

        # --- fields from bootstrap API response ---
        public_key = bootstrap_data.get("publicKey", "")
        finger_print = bootstrap_data.get(
            "fingerPrint", bootstrap_data.get("fingerprint", "")
        )

        rma_model = RMASwitchModel(
            gatewayIpMask=gateway_ip_mask,
            model=model_name,
            softwareVersion=version,
            imagePolicy=image_policy,
            switchRole=switch_role,
            password=password,
            discoveryAuthProtocol=auth_proto,
            discoveryUsername=discovery_username,
            discoveryPassword=discovery_password,
            hostname=hostname,
            ip=ip,
            newSwitchId=new_switch_id,
            publicKey=public_key,
            fingerPrint=finger_print,
        )

        self.log.debug(
            f"EXIT: _build_rma_model() -> newSwitchId={rma_model.new_switch_id}"
        )
        return rma_model

    # --------------------------------------------------------------------- #

    def _provision_rma_switch(
        self,
        old_switch_id: str,
        rma_model: RMASwitchModel,
    ) -> None:
        """
        POST a single ``RMASwitchModel`` to the provisionRMA endpoint.

        The endpoint is per-switch:
        ``/fabrics/{fabricName}/switches/{oldSwitchId}/actions/provisionRMA``

        Args:
            old_switch_id: Serial number of the switch being replaced.
            rma_model:     Complete payload model for the new switch.
        """
        self.log.debug("ENTER: _provision_rma_switch()")

        endpoint = EpManageFabricSwitchProvisionRMA()
        endpoint.fabric_name = self.fabric
        endpoint.switch_id = old_switch_id

        payload = rma_model.to_payload()

        self.log.info(
            f"RMA: Replacing {old_switch_id} with {rma_model.new_switch_id}"
        )
        self.log.debug(f"RMA endpoint: {endpoint.path}")
        self.log.debug(
            f"RMA payload (masked): {self._mask_password(payload)}"
        )

        # Make the request
        self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)

        # Capture response
        response = self.nd.rest_send.response_current
        result = self.nd.rest_send.result_current

        # Register task result
        self.results.action = "rma"
        self.results.response_current = response
        self.results.result_current = result
        self.results.diff_current = {
            "old_switch_id": old_switch_id,
            "new_switch_id": rma_model.new_switch_id,
        }
        self.results.register_task_result()

        self.log.info(
            f"RMA provision API response success: {result.get('success')}"
        )
        self.log.debug("EXIT: _provision_rma_switch()")
    
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
    
    def _finalize_operations(self) -> None:
        """
        Finalize operations - save and deploy config.

        Calls configSave and configDeploy for the fabric based on the
        ``save`` and ``deploy`` module parameters.  Neither endpoint
        requires a request body.
        """
        if self.nd.module.check_mode:
            return

        if self.save_config_flag:
            self.log.info("Saving fabric configuration")
            self.fabric_utils.save_config()

        if self.deploy_config_flag:
            self.log.info("Deploying fabric configuration")
            self.fabric_utils.deploy_config()
    
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