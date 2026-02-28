# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple, Union

from .nd_v2 import NDModule
from .enums import OperationType
from .results import Results
from .models.switch_inventory_models import (
    SwitchRole,
    SnmpV3AuthProtocol,
    PlatformType,
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
    SwitchConfigModel,
    SwitchCredentialsRequestModel,
    POAPConfigModel,
    RMAConfigModel,
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
    """Specialized module for switch lifecycle management.

    Provides switch-specific operations on top of NDModule:
        - Discovery and inventory management
        - Wait for switch migration / manageability
        - Credential persistence
        - Config save and deploy
        - POAP (bootstrap / pre-provision) workflows
        - RMA (Return Material Authorization) workflows

    Schema models (from ``switch_inventory_models``):
        - ``SwitchDataModel``            – existing switch inventory data
        - ``SwitchDiscoveryModel``       – switch discovery / add operations
        - ``BootstrapImportSwitchModel`` – POAP operations
        - ``RMASwitchModel``             – RMA operations
    """

    # =========================================================================
    # Initialization & Lifecycle
    # =========================================================================

    def __init__(
        self,
        nd: NDModule,
        results: Results,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the Switch Resource Module.

        Args:
            nd:      NDModule instance (wraps the Ansible module and REST client).
            results: Results aggregation instance for task output.
            logger:  Optional logger; defaults to ``nd.NDSwitchResourceModule``.
        """
        self.log = logger or logging.getLogger("nd.NDSwitchResourceModule")
        self.nd = nd
        self.module = nd.module
        self.results = results

        # Module parameters
        self.config = self.module.params.get("config", {})
        self.fabric = self.module.params.get("fabric")
        self.state = self.module.params.get("state")
        self.save_config_flag = self.module.params.get("save", True)
        self.deploy_config_flag = self.module.params.get("deploy", True)

        # Switch collections
        try:
            self.proposed: List[SwitchDataModel] = []
            self.existing: List[SwitchDataModel] = [
                SwitchDataModel.model_validate(sw)
                for sw in self._query_all_switches()
            ]
            self.previous: List[SwitchDataModel] = deepcopy(self.existing)
        except Exception as e:
            self.log.error(f"Failed to initialize collections: {e}")
            self.existing = []
            self.previous = []
            self.proposed = []

        # Operation tracking
        self.nd_logs: List[Dict[str, Any]] = []

        # Utility instances
        self.payload_utils = PayloadUtils(self.log)
        self.fabric_utils = FabricUtils(self.nd, self.fabric, self.log)
        self.wait_utils = SwitchWaitUtils(
            self, self.fabric, self.log, fabric_utils=self.fabric_utils
        )

        self.log.info(f"Initialized NDSwitchResourceModule for fabric: {self.fabric}")

    def exit_json(self) -> None:
        """Build final result from all registered tasks and exit.

        Merges the ``Results`` aggregation with supplemental data
        (logs, previous/current inventory snapshots) and delegates
        to ``ansible_module.exit_json`` or ``fail_json``.
        """
        self.results.build_final_result()
        final = self.results.final_result

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

    # =========================================================================
    # Public API – State Management
    # =========================================================================

    def manage_state(self) -> None:
        """Main entry point for state management.

        Reads ``self.state`` and delegates to the appropriate handler:
            - **query** / **deleted** – config is optional (operates on all
              switches when absent).
            - **merged** / **overridden** – config is required.  POAP and RMA
              operation types are dispatched before normal discovery.
        """
        self.log.info(f"Managing state: {self.state}")

        # query / deleted — config is optional
        if self.state in ("query", "deleted"):
            proposed_config = self._validate_configs(self.config) if self.config else None
            if self.state == "deleted":
                return self._handle_deleted_state(proposed_config)
            return self._handle_query_state(proposed_config)

        # merged / overridden — config is required
        if not self.config:
            self.nd.module.fail_json(
                msg=f"'config' is required for '{self.state}' state."
            )

        proposed_config = self._validate_configs(self.config)
        self.operation_type = proposed_config[0].operation_type

        # POAP and RMA bypass normal discovery
        if self.operation_type == "poap":
            return self._handle_poap_state(proposed_config)
        if self.operation_type == "rma":
            return self._handle_rma_state(proposed_config)

        # Normal: discover → build proposed models → compute diff → delegate
        discovered_data = self._discover_switches(proposed_config)
        self._build_proposed_from_discovery(proposed_config, discovered_data)
        diff = self._compute_changes(self.proposed, self.existing)

        state_handlers = {
            "merged": self._handle_merged_state,
            "overridden": self._handle_overridden_state,
        }
        handler = state_handlers.get(self.state)
        if handler is None:
            self.nd.module.fail_json(msg=f"Unsupported state: {self.state}")
        return handler(diff, proposed_config, discovered_data)

    def _build_proposed_from_discovery(
        self,
        proposed_config: List[SwitchConfigModel],
        discovered_data: Dict[str, Dict[str, Any]],
    ) -> None:
        """Resolve discovery results into ``self.proposed`` switch models.

        For each proposed config entry:
            1. If discovery returned data for the seed IP, merge the user-
               supplied role and convert to ``SwitchDataModel``.
            2. If not discovered, fall back to an existing inventory match.
            3. If neither exists, fail with an actionable error message.

        Args:
            proposed_config: Validated switch configs from the playbook.
            discovered_data: Mapping of ``seed_ip`` → raw discovery dict.
        """
        for cfg in proposed_config:
            seed_ip = cfg.seed_ip
            discovered = discovered_data.get(seed_ip)

            if discovered:
                if cfg.role is not None:
                    discovered["role"] = cfg.role
                self.proposed.append(
                    SwitchDataModel.from_response(discovered)
                )
                self.log.debug(f"Built proposed model from discovery for {seed_ip}")
                continue

            # Fallback: switch may already be in the fabric inventory
            existing_match = next(
                (sw for sw in self.existing if sw.fabric_management_ip == seed_ip),
                None,
            )
            if existing_match:
                self.proposed.append(existing_match)
                self.log.warning(
                    f"Switch {seed_ip} not discovered but found in existing "
                    f"inventory — using existing record for comparison"
                )
                continue

            msg = (
                f"Switch with seed IP {seed_ip} not discovered "
                f"and not found in existing inventory."
            )
            self.log.error(msg)
            self.nd.module.fail_json(msg=msg)

    # =========================================================================
    # State Handlers
    # =========================================================================

    def _handle_query_state(
        self,
        proposed_config: Optional[List[SwitchConfigModel]] = None,
    ) -> None:
        """Return existing switches matching the proposed config.

        Args:
            proposed_config: If ``None``, all fabric switches are returned.
                If provided, only switches matching ``seed_ip`` (and
                optionally ``role``) are returned.

        Registers a single QUERY task result with the matching switch
        inventory in ``response_current["DATA"]``.
        """
        self.log.debug("ENTER: _handle_query_state()")
        self.log.info("Handling query state")
        self.log.debug(f"Found {len(self.existing)} existing switches")

        if proposed_config is None:
            matched_switches = list(self.existing)
            self.log.info("No proposed config — returning all existing switches")
        else:
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
                    self.log.info(f"Switch {cfg.seed_ip} not found in fabric")
                    continue

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

        switch_data = [sw.model_dump(by_alias=True) for sw in matched_switches]

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

        self.log.debug(f"Returning {len(switch_data)} switches in results")
        self.log.debug("EXIT: _handle_query_state()")

    def _handle_merged_state(
        self,
        diff: Dict[str, List[SwitchDataModel]],
        proposed_config: List[SwitchConfigModel],
        discovered_data: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """Add new switches and process migration-mode switches.

        Workflow:
            1. Log idempotent switches (no-op).
            2. Warn about ``to_update`` (not supported in merged state).
            3. Bulk-add new switches (``to_add``) to fabric.
            4. Collect migration-mode switches.
            5. Common post-processing for all actionable switches:
               wait for manageability, save credentials, assign roles.
            6. Finalize (config-save + config-deploy).
        """
        self.log.debug("ENTER: _handle_merged_state()")
        self.log.info("Handling merged state")
        self.log.debug(f"Proposed configs: {len(self.proposed)}")
        self.log.debug(f"Existing switches: {len(self.existing)}")

        if not self.proposed:
            self.log.info("No configurations provided for merged state")
            self.log.debug("EXIT: _handle_merged_state() - no configs")
            return

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

        switches_to_add = diff.get("to_add", [])
        migration_switches = diff.get("migration_mode", [])

        if not switches_to_add and not migration_switches:
            self.log.info("No switches need adding or migration processing")
            return

        # Check mode — preview only
        if self.nd.module.check_mode:
            self.log.info(
                f"Check mode: would add {len(switches_to_add)} and "
                f"process {len(migration_switches)} migration switches"
            )
            self.results.action = "merge"
            self.results.state = self.state
            self.results.operation_type = OperationType.CREATE
            self.results.response_current = {"MESSAGE": "check mode — skipped", "RETURN_CODE": 200}
            self.results.result_current = {"success": True, "changed": True}
            self.results.diff_current = {
                "to_add": [sw.fabric_management_ip for sw in switches_to_add],
                "migration_mode": [sw.fabric_management_ip for sw in migration_switches],
            }
            self.results.register_task_result()
            return

        # Collect (serial_number, SwitchConfigModel) pairs for post-processing
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
            return

        # Common post-processing for all switches (new + migration)
        all_serial_numbers = [sn for sn, _ in switch_actions]

        self.log.info(
            f"Waiting for {len(all_serial_numbers)} switch(es) to become manageable: "
            f"{all_serial_numbers}"
        )
        success = self.wait_utils.wait_for_switch_manageable(all_serial_numbers)
        if not success:
            self.log.warning("Some switches did not become fully manageable")

        self._bulk_save_credentials(switch_actions)
        # self._bulk_update_roles(switch_actions)
        self._finalize_operations()

        self.log.debug("EXIT: _handle_merged_state() - completed")

    def _handle_overridden_state(
        self,
        diff: Dict[str, List[SwitchDataModel]],
        proposed_config: List[SwitchConfigModel],
        discovered_data: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """Ensure only proposed switches exist in the fabric.

        Workflow:
            1. Delete switches not in proposed config (``to_delete``).
            2. Delete-then-re-add switches that need updating (``to_update``).
            3. Delegate adds + migration processing to ``_handle_merged_state``.
        """
        self.log.debug("ENTER: _handle_overridden_state()")
        self.log.info("Handling overridden state")

        if not self.proposed:
            self.log.warning("No configurations provided for overridden state")
            return

        # Check mode — preview only
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
            would_change = (n_delete + n_update + n_add + n_migrate) > 0
            self.results.action = "override"
            self.results.state = self.state
            self.results.operation_type = OperationType.CREATE
            self.results.response_current = {"MESSAGE": "check mode — skipped", "RETURN_CODE": 200}
            self.results.result_current = {"success": True, "changed": would_change}
            self.results.diff_current = {
                "to_delete": n_delete,
                "to_update": n_update,
                "to_add": n_add,
                "migration_mode": n_migrate,
            }
            self.results.register_task_result()
            return

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

            diff["to_add"].append(sw)

        if switches_to_delete:
            self._bulk_delete_switches(switches_to_delete)

        diff["to_update"] = []

        # Phase 3: Delegate add + migration to merged state
        self._handle_merged_state(diff, proposed_config, discovered_data)
        self.log.debug("EXIT: _handle_overridden_state()")

    def _handle_deleted_state(
        self,
        proposed_config: Optional[List[SwitchConfigModel]] = None,
    ) -> None:
        """Remove specified switches from the fabric.

        Args:
            proposed_config: If ``None``, **all** switches are deleted.
                If provided, only switches matching ``seed_ip`` are deleted.
                Discovery is skipped — matching uses the existing inventory.
        """
        self.log.debug("ENTER: _handle_deleted_state()")
        self.log.info("Handling deleted state")

        if proposed_config is None:
            switches_to_delete = list(self.existing)
            self.log.info(
                f"No proposed config — targeting all {len(switches_to_delete)} "
                f"existing switch(es) for deletion"
            )
            for sw in switches_to_delete:
                self._log_operation("delete", sw.fabric_management_ip)
        else:
            switches_to_delete: List[SwitchDataModel] = []
            for switch_config in proposed_config:
                identifier = switch_config.seed_ip
                self.log.debug(f"Looking for switch to delete with seed IP: {identifier}")
                existing_switch = next(
                    (sw for sw in self.existing if sw.fabric_management_ip == identifier),
                    None,
                )
                if existing_switch:
                    self.log.info(
                        f"Marking for deletion: {identifier} ({existing_switch.switch_id})"
                    )
                    switches_to_delete.append(existing_switch)
                else:
                    self.log.info(f"Switch not found for deletion: {identifier}")

        self.log.info(f"Total switches marked for deletion: {len(switches_to_delete)}")
        if not switches_to_delete:
            self.log.info("No switches to delete")
            return

        # Check mode — preview only
        if self.nd.module.check_mode:
            self.log.info(f"Check mode: would delete {len(switches_to_delete)} switch(es)")
            self.results.action = "delete"
            self.results.state = self.state
            self.results.operation_type = OperationType.DELETE
            self.results.response_current = {"MESSAGE": "check mode — skipped", "RETURN_CODE": 200}
            self.results.result_current = {"success": True, "changed": True}
            self.results.diff_current = {
                "to_delete": [sw.fabric_management_ip for sw in switches_to_delete],
            }
            self.results.register_task_result()
            return

        self.log.info(
            f"Proceeding to delete {len(switches_to_delete)} switch(es) from fabric"
        )
        self._bulk_delete_switches(switches_to_delete)
        self.log.debug("EXIT: _handle_deleted_state()")

    # =========================================================================
    # Validation
    # =========================================================================

    def _validate_configs(
        self,
        config: Union[Dict[str, Any], List[Dict[str, Any]]],
    ) -> List[SwitchConfigModel]:
        """Validate raw Ansible config and return ``SwitchConfigModel`` instances.

        Per-config validation (state restrictions, POAP/RMA mutual exclusivity,
        credential enforcement, role defaults) is handled by
        ``SwitchConfigModel`` validators during ``model_validate()``.

        Cross-config validation (mixed operation types) is handled by
        ``SwitchConfigModel.validate_no_mixed_operations()``.

        Args:
            config: Raw configuration dict or list of dicts from module params.

        Returns:
            List of validated ``SwitchConfigModel`` instances.

        Raises:
            ValidationError: If config validation fails or mixed operations detected.
        """
        self.log.debug("ENTER: _validate_configs()")

        configs_list = config if isinstance(config, list) else [config]
        self.log.debug(f"Normalized to {len(configs_list)} configuration(s)")

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
            return validated_configs

        # Cross-config check — model can't do this per-instance
        try:
            SwitchConfigModel.validate_no_mixed_operations(validated_configs)
        except ValueError as e:
            error_msg = str(e)
            self.log.error(error_msg)
            if hasattr(self.nd, 'module'):
                self.nd.module.fail_json(msg=error_msg)
            else:
                raise

        operation_type = validated_configs[0].operation_type
        self.log.info(
            f"Successfully validated {len(validated_configs)} "
            f"configuration(s) with operation type: {operation_type}"
        )
        self.log.debug(
            f"EXIT: _validate_configs() -> "
            f"{len(validated_configs)} configs, operation_type={operation_type}"
        )
        return validated_configs

    def _compute_changes(
        self,
        proposed: List[SwitchDataModel],
        existing: List[SwitchDataModel],
    ) -> Dict[str, List[SwitchDataModel]]:
        """Compare proposed vs existing switch lists and categorise differences.

        Returns:
            Dict with keys:
                - ``to_add``         – switches in proposed but not existing
                - ``to_update``      – switches in both with field differences
                - ``to_delete``      – switches in existing but not proposed
                - ``migration_mode`` – switches currently in Migration mode
                - ``idempotent``     – switches with no changes needed
        """
        self.log.debug("ENTER: _compute_changes()")
        self.log.debug(
            f"Comparing {len(proposed)} proposed vs {len(existing)} existing switches"
        )

        # Build indexes for O(1) lookups
        existing_by_id = {sw.switch_id: sw for sw in existing}
        existing_by_ip = {sw.fabric_management_ip: sw for sw in existing}

        self.log.debug(
            f"Indexes built — existing_by_id: {list(existing_by_id.keys())}, "
            f"existing_by_ip: {list(existing_by_ip.keys())}"
        )

        # Only user-controllable fields populated by both discovery and inventory APIs.
        # Server-managed fields (uptime, alerts, vpc info, telemetry, etc.) are ignored.
        compare_fields = {
            "switch_id",
            "serial_number",
            "fabric_management_ip",
            "hostname",
            "model",
            "software_version",
            "switch_role",
        }

        changes: Dict[str, list] = {
            "to_add": [],
            "to_update": [],
            "to_delete": [],
            "migration_mode": [],
            "idempotent": [],
        }

        # Categorise proposed switches
        for prop_sw in proposed:
            ip = prop_sw.fabric_management_ip
            sid = prop_sw.switch_id

            existing_sw = existing_by_id.get(sid)
            match_key = "switch_id" if existing_sw else None

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

            if existing_sw.mode == "Migration":
                self.log.info(
                    f"Switch {ip} ({existing_sw.switch_id}) is in Migration mode"
                )
                changes["migration_mode"].append(prop_sw)
                continue

            prop_dict = prop_sw.model_dump(
                by_alias=True, exclude_none=True, include=compare_fields
            )
            existing_dict = existing_sw.model_dump(
                by_alias=True, exclude_none=True, include=compare_fields
            )

            if prop_dict == existing_dict:
                self.log.debug(f"Switch {ip} is idempotent — no changes needed")
                changes["idempotent"].append(prop_sw)
            else:
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

        # Switches in existing but not in proposed (for overridden state)
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

    # =========================================================================
    # Discovery & Fabric Add
    # =========================================================================

    def _discover_switches(
        self,
        switch_configs: List[SwitchConfigModel],
    ) -> Dict[str, Dict[str, Any]]:
        """Discover switches based on proposed configurations.

        Groups switches by credentials and issues one bulk discovery API
        call per credential group.

        Returns:
            Dict mapping ``seed_ip`` → raw discovered data dict.
        """
        self.log.debug("Step 1: Grouping switches by credentials")
        switch_credential_groups = self._group_switches_by_credentials(switch_configs)
        self.log.debug(f"Created {len(switch_credential_groups)} credential group(s)")

        self.log.debug("Step 2: Bulk discovering switches")
        all_discovered: Dict[str, Dict[str, Any]] = {}
        for group_key, switches in switch_credential_groups.items():
            username, password_hash, auth_proto, platform_type, preserve_config = group_key
            password = switches[0].password

            self.log.debug(
                f"Discovering group: {len(switches)} switches with username={username}"
            )
            discovered_batch = self._bulk_discover_switches(
                switches=switches,
                username=username,
                password=password,
                auth_proto=auth_proto,
                platform_type=platform_type,
            )
            all_discovered.update(discovered_batch)

        self.log.debug(f"Total discovered: {len(all_discovered)} switches")
        return all_discovered

    def _bulk_discover_switches(
        self,
        switches: List[SwitchConfigModel],
        username: str,
        password: str,
        auth_proto: SnmpV3AuthProtocol,
        platform_type: PlatformType,
    ) -> Dict[str, Dict[str, Any]]:
        """Discover multiple switches sharing the same credentials in one API call.

        Args:
            switches:      Switches to discover.
            username:      Discovery username.
            password:      Discovery password.
            auth_proto:    SNMP v3 authentication protocol.
            platform_type: Platform type (nx-os, ios-xe, etc.).

        Returns:
            Dict mapping ``seed_ip`` → discovered data dict.
        """
        self.log.debug("ENTER: _bulk_discover_switches()")
        self.log.debug(f"Discovering {len(switches)} switches in bulk")

        endpoint = EpManageFabricShallowDiscovery()
        endpoint.fabric_name = self.fabric

        seed_ips = [switch.seed_ip for switch in switches]
        self.log.debug(f"Seed IPs: {seed_ips}")

        max_hops = switches[0].max_hops if hasattr(switches[0], 'max_hops') else 0

        discovery_request = ShallowDiscoveryRequestModel(
            seedIpCollection=seed_ips,
            maxHop=max_hops,
            platformType=platform_type,
            snmpV3AuthProtocol=auth_proto,
            username=username,
            password=password,
        )

        payload = discovery_request.to_payload()
        self.log.info(f"Bulk discovering {len(seed_ips)} switches: {', '.join(seed_ips)}")
        self.log.debug(f"Discovery endpoint: {endpoint.path}")
        self.log.debug(f"Discovery payload (password masked): {self._mask_password(payload)}")

        try:
            self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)

            response = self.nd.rest_send.response_current
            result = self.nd.rest_send.result_current

            self.results.action = "discover"
            self.results.response_current = response
            self.results.result_current = result
            self.results.diff_current = payload
            self.results.register_task_result()

            # Extract discovered switches from response
            switches_data = []
            if response and isinstance(response, dict):
                if "DATA" in response and isinstance(response["DATA"], dict):
                    switches_data = response["DATA"].get("switches", [])
                elif "body" in response and isinstance(response["body"], dict):
                    switches_data = response["body"].get("switches", [])
                elif "switches" in response:
                    switches_data = response.get("switches", [])

            self.log.debug(
                f"Extracted {len(switches_data)} switches from discovery response"
            )

            discovered_results: Dict[str, Dict[str, Any]] = {}
            for discovered in switches_data:
                if not isinstance(discovered, dict):
                    continue

                ip = discovered.get("ip")
                status = discovered.get("status", "").lower()
                serial_number = discovered.get("serialNumber")

                if not serial_number:
                    self.log.error(f"Switch {ip} discovery missing serial number")
                    continue
                if not ip:
                    self.log.error(f"Switch with serial {serial_number} missing IP address")
                    continue

                if status in ("manageable", "ok"):
                    discovered_results[ip] = discovered
                    self.log.info(
                        f"Switch {ip} ({serial_number}) discovered successfully - status: {status}"
                    )
                elif status == "alreadymanaged":
                    self.log.info(f"Switch {ip} ({serial_number}) is already managed")
                    discovered_results[ip] = discovered
                else:
                    reason = discovered.get("statusReason", "Unknown")
                    self.log.error(
                        f"Switch {ip} discovery failed - status: {status}, reason: {reason}"
                    )

            for seed_ip in seed_ips:
                if seed_ip not in discovered_results:
                    self.log.warning(f"Switch {seed_ip} not found in discovery response")

            self.log.info(
                f"Bulk discovery completed: "
                f"{len(discovered_results)}/{len(seed_ips)} switches successful"
            )
            self.log.debug(f"Discovered switches: {list(discovered_results.keys())}")
            self.log.debug(
                f"EXIT: _bulk_discover_switches() -> {len(discovered_results)} discovered"
            )
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
        preserve_config: bool,
    ) -> Dict[str, Any]:
        """Add multiple discovered switches to a fabric in one API call.

        Args:
            switches:        List of ``(SwitchConfigModel, discovered_data)`` tuples.
            username:        Discovery username.
            password:        Discovery password.
            auth_proto:      SNMP v3 authentication protocol.
            platform_type:   Platform type.
            preserve_config: Whether to preserve existing switch config.

        Returns:
            API response dict.
        """
        self.log.debug("ENTER: _bulk_add_switches_to_fabric()")
        self.log.debug(f"Adding {len(switches)} switches to fabric")

        endpoint = EpManageFabricSwitchesAdd()
        endpoint.fabric_name = self.fabric

        switch_discoveries = []
        for switch_config, discovered in switches:
            required_fields = ["hostname", "ip", "serialNumber", "model"]
            missing_fields = [f for f in required_fields if not discovered.get(f)]

            if missing_fields:
                self.log.warning(
                    f"Skipping switch - missing required fields from discovery: "
                    f"{', '.join(missing_fields)}"
                )
                continue

            switch_role = switch_config.role if hasattr(switch_config, 'role') else None

            switch_discovery = SwitchDiscoveryModel(
                hostname=discovered.get("hostname"),
                ip=discovered.get("ip"),
                serialNumber=discovered.get("serialNumber"),
                model=discovered.get("model"),
                softwareVersion=discovered.get("softwareVersion"),
                switchRole=switch_role,
            )
            switch_discoveries.append(switch_discovery)
            self.log.debug(
                f"Prepared switch for add: "
                f"{discovered.get('serialNumber')} ({discovered.get('hostname')})"
            )

        if not switch_discoveries:
            self.log.error("No valid switches to add after validation")
            raise SwitchOperationError("No valid switches to add - all failed validation")

        add_request = AddSwitchesRequestModel(
            switches=switch_discoveries,
            platformType=platform_type,
            preserveConfig=preserve_config,
            snmpV3AuthProtocol=auth_proto,
            username=username,
            password=password,
        )

        payload = add_request.to_payload()
        serial_numbers = [d.get("serialNumber") for _, d in switches]
        self.log.info(
            f"Bulk adding {len(switches)} switches to fabric "
            f"{self.fabric}: {', '.join(serial_numbers)}"
        )
        self.log.debug(f"Add endpoint: {endpoint.path}")
        self.log.debug(f"Add payload (password masked): {self._mask_password(payload)}")

        self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)

        response = self.nd.rest_send.response_current
        result = self.nd.rest_send.result_current

        self.results.action = "create"
        self.results.response_current = response
        self.results.result_current = result
        self.results.diff_current = payload
        self.results.register_task_result()

        return response

    # =========================================================================
    # Bulk Switch Operations
    # =========================================================================

    def _bulk_delete_switches(
        self,
        switches: List[Union[SwitchDataModel, SwitchDiscoveryModel]],
    ) -> List[str]:
        """Remove multiple switches from a fabric in a single API call.

        Args:
            switches: Switch models to delete.

        Returns:
            Serial numbers successfully submitted for deletion.
        """
        self.log.debug("ENTER: _bulk_delete_switches()")

        if self.nd.module.check_mode:
            self.log.debug("Check mode: Skipping actual deletion")
            return []

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

            self.results.action = "delete"
            self.results.response_current = response
            self.results.result_current = result
            self.results.diff_current = {"deleted": serial_numbers}
            self.results.register_task_result()

            self.log.info(f"Bulk delete submitted for {len(serial_numbers)} switch(es)")
            self.log.debug("EXIT: _bulk_delete_switches()")
            return serial_numbers

        except Exception as e:
            self.log.error(f"Bulk delete failed: {e}")
            raise SwitchOperationError(
                f"Bulk delete failed for {serial_numbers}: {e}"
            ) from e

    def _bulk_save_credentials(
        self,
        switch_actions: List[Tuple[str, SwitchConfigModel]],
    ) -> None:
        """Save credentials for switches, grouped by (username, password).

        Makes one API call per unique credential pair, sending all matching
        ``switchIds`` in a single ``SwitchCredentialsRequestModel`` payload.

        Args:
            switch_actions: ``(serial_number, SwitchConfigModel)`` pairs.
        """
        self.log.debug("ENTER: _bulk_save_credentials()")

        cred_groups: Dict[Tuple[str, str], List[str]] = {}
        for sn, cfg in switch_actions:
            if not cfg.user_name or not cfg.password:
                self.log.debug(f"Skipping credentials for {sn}: missing user_name or password")
                continue
            key = (cfg.user_name, cfg.password)
            cred_groups.setdefault(key, []).append(sn)

        if not cred_groups:
            self.log.debug("EXIT: _bulk_save_credentials() - no credentials to save")
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
                f"Saving credentials for {len(serial_numbers)} switch(es): {serial_numbers}"
            )
            self.log.debug(f"Credentials endpoint: {endpoint.path}")
            self.log.debug(
                f"Credentials payload (masked): {self._mask_password(payload)}"
            )

            try:
                self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)

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
                self.log.info(f"Credentials saved for {len(serial_numbers)} switch(es)")
            except Exception as e:
                self.log.warning(f"Failed to save credentials for {serial_numbers}: {e}")

        self.log.debug("EXIT: _bulk_save_credentials()")

    def _bulk_update_roles(
        self,
        switch_actions: List[Tuple[str, SwitchConfigModel]],
    ) -> None:
        """Update switch roles in bulk via the ``changeRoles`` endpoint.

        Sends ``{"switchRoles": [{"switchId": "SN", "role": "leaf"}, ...]}``
        in a single API call.

        Args:
            switch_actions: ``(serial_number, SwitchConfigModel)`` pairs.
        """
        self.log.debug("ENTER: _bulk_update_roles()")

        switch_roles = []
        for sn, cfg in switch_actions:
            role = self._get_switch_field(cfg, ['role'])
            if not role:
                continue
            role_value = role.value if isinstance(role, SwitchRole) else str(role)
            switch_roles.append({"switchId": sn, "role": role_value})

        if not switch_roles:
            self.log.debug("EXIT: _bulk_update_roles() - no roles to update")
            return

        endpoint = EpManageFabricSwitchActionsChangeRoles()
        endpoint.fabric_name = self.fabric
        payload = {"switchRoles": switch_roles}

        self.log.info(f"Bulk updating roles for {len(switch_roles)} switch(es)")
        self.log.debug(f"ChangeRoles endpoint: {endpoint.path}")
        self.log.debug(f"ChangeRoles payload: {payload}")

        try:
            self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)

            response = self.nd.rest_send.response_current
            result = self.nd.rest_send.result_current

            self.results.action = "update_role"
            self.results.response_current = response
            self.results.result_current = result
            self.results.diff_current = payload
            self.results.register_task_result()
            self.log.info(f"Roles updated for {len(switch_roles)} switch(es)")
        except Exception as e:
            self.log.warning(f"Failed to bulk update roles: {e}")

        self.log.debug("EXIT: _bulk_update_roles()")

    # =========================================================================
    # POAP Operations (Bootstrap / Pre-Provision)
    # =========================================================================

    def _handle_poap_state(
        self,
        proposed_config: List[SwitchConfigModel],
    ) -> None:
        """Orchestrate the full POAP workflow.

        Flow:
            1. Classify POAP entries into **bootstrap** (has ``serial_number``)
               and **pre-provision** (has ``preprovision_serial``) buckets.
            2. Bootstrap: query bootstrap API → match → build models → POST
               ``importBootstrap``.
            3. Pre-provision: build models → POST ``preProvision``.
            4. Register results.

        Called from ``manage_state()`` before normal discovery so that POAP
        switches never hit ``_discover_switches()``.
        """
        self.log.debug("ENTER: _handle_poap_state()")
        self.log.info(f"Processing POAP for {len(proposed_config)} switch config(s)")

        # Check mode — preview only
        if self.nd.module.check_mode:
            self.log.info("Check mode: would run POAP bootstrap / pre-provision")
            self.results.action = "poap"
            self.results.response_current = {"MESSAGE": "check mode — skipped"}
            self.results.result_current = {"success": True, "changed": True}
            self.results.diff_current = {
                "poap_switches": [pc.seed_ip for pc in proposed_config]
            }
            self.results.register_task_result()
            return

        # Classify entries
        bootstrap_entries: List[Tuple[SwitchConfigModel, POAPConfigModel]] = []
        preprov_entries: List[Tuple[SwitchConfigModel, POAPConfigModel]] = []

        for switch_cfg in proposed_config:
            if not switch_cfg.poap:
                self.log.warning(
                    f"Switch config for {switch_cfg.seed_ip} has no POAP block — skipping"
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

        # Handle bootstrap entries
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

        # Handle pre-provision entries
        if preprov_entries:
            preprov_models: List[PreProvisionSwitchModel] = []
            for switch_cfg, poap_cfg in preprov_entries:
                pp_model = self._build_preprovision_model(switch_cfg, poap_cfg)
                preprov_models.append(pp_model)
                self.log.info(
                    f"Built pre-provision model for serial="
                    f"{pp_model.serial_number}, hostname={pp_model.hostname}, "
                    f"ip={pp_model.ip}"
                )

            if preprov_models:
                self._preprovision_switches(preprov_models)

        # Edge case: nothing actionable
        if not bootstrap_entries and not preprov_entries:
            self.log.warning("No POAP switch models built — nothing to process")
            self.results.action = "poap"
            self.results.response_current = {"MESSAGE": "no switches to process"}
            self.results.result_current = {"success": True, "changed": False}
            self.results.diff_current = {}
            self.results.register_task_result()

        self.log.debug("EXIT: _handle_poap_state()")

    def _query_bootstrap_switches(self) -> List[Dict[str, Any]]:
        """GET switches currently in the bootstrap (POAP / PnP) loop.

        Returns:
            List of raw switch dicts from the bootstrap API.
        """
        self.log.debug("ENTER: _query_bootstrap_switches()")

        endpoint = EpManageFabricBootstrapGet()
        endpoint.fabric_name = self.fabric
        self.log.debug(f"Bootstrap endpoint: {endpoint.path}")

        result = self.nd.request(path=endpoint.path, verb=endpoint.verb)

        if isinstance(result, dict):
            switches = result.get("switches", [])
        elif isinstance(result, list):
            switches = result
        else:
            switches = []

        self.log.info(f"Bootstrap API returned {len(switches)} switch(es) in POAP loop")
        self.log.debug("EXIT: _query_bootstrap_switches()")
        return switches

    def _build_bootstrap_import_model(
        self,
        switch_cfg: SwitchConfigModel,
        poap_cfg: POAPConfigModel,
        bootstrap_data: Optional[Dict[str, Any]],
    ) -> BootstrapImportSwitchModel:
        """Merge user POAP config with bootstrap API data into a complete model.

        User config values take priority.  Bootstrap API provides
        ``publicKey``, ``fingerPrint``, ``inInventory``, and ``dhcpBootstrapIp``
        which the user normally does not supply.

        Args:
            switch_cfg:     Parent config (seed_ip, role, password, auth_proto).
            poap_cfg:       POAPConfigModel from the user playbook.
            bootstrap_data: Matching entry from the bootstrap GET API
                            (may be ``None`` for pre-provision).
        """
        self.log.debug(
            f"ENTER: _build_bootstrap_import_model(serial={poap_cfg.serial_number})"
        )

        bs = bootstrap_data or {}

        # User config fields
        serial_number = poap_cfg.serial_number
        hostname = poap_cfg.hostname
        ip = switch_cfg.seed_ip
        model = poap_cfg.model
        version = poap_cfg.version
        image_policy = poap_cfg.image_policy
        gateway_ip_mask = poap_cfg.config_data.gateway if poap_cfg.config_data else None
        switch_role = switch_cfg.role
        password = switch_cfg.password
        auth_proto = SnmpV3AuthProtocol.MD5  # POAP/bootstrap always uses MD5

        discovery_username = getattr(poap_cfg, "discovery_username", None)
        discovery_password = getattr(poap_cfg, "discovery_password", None)

        # Bootstrap API response fields
        fingerprint = bs.get("fingerPrint", bs.get("fingerprint", ""))
        public_key = bs.get("publicKey", "")
        re_add = bs.get("reAdd", False)
        in_inventory = bs.get("inInventory", False)

        # Optional data block
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
            f"EXIT: _build_bootstrap_import_model() -> {bootstrap_model.serial_number}"
        )
        return bootstrap_model

    def _import_bootstrap_switches(
        self,
        models: List[BootstrapImportSwitchModel],
    ) -> None:
        """POST bootstrap switch models to the ``importBootstrap`` endpoint."""
        self.log.debug("ENTER: _import_bootstrap_switches()")

        endpoint = EpManageFabricSwitchActionsImportBootstrap()
        endpoint.fabric_name = self.fabric

        request_model = ImportBootstrapSwitchesRequestModel(switches=models)
        payload = request_model.to_payload()

        self.log.debug(f"importBootstrap endpoint: {endpoint.path}")
        self.log.debug(
            f"importBootstrap payload (masked): {self._mask_password(payload)}"
        )
        self.log.info(
            f"Importing {len(models)} bootstrap switch(es): "
            f"{[m.serial_number for m in models]}"
        )

        self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)

        response = self.nd.rest_send.response_current
        result = self.nd.rest_send.result_current

        self.results.action = "bootstrap"
        self.results.response_current = response
        self.results.result_current = result
        self.results.diff_current = payload
        self.results.register_task_result()

        self.log.info(f"importBootstrap API response success: {result.get('success')}")
        self.log.debug("EXIT: _import_bootstrap_switches()")

    def _build_preprovision_model(
        self,
        switch_cfg: SwitchConfigModel,
        poap_cfg: POAPConfigModel,
    ) -> PreProvisionSwitchModel:
        """Build a ``PreProvisionSwitchModel`` from user-supplied POAP config.

        Pre-provision does not require a bootstrap API query because the
        switch does not physically exist yet.

        Args:
            switch_cfg: Parent config (seed_ip, role, password, auth_proto).
            poap_cfg:   POAPConfigModel from the user playbook.
        """
        self.log.debug(
            f"ENTER: _build_preprovision_model(serial={poap_cfg.preprovision_serial})"
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
        auth_proto = SnmpV3AuthProtocol.MD5  # Pre-provision always uses MD5

        discovery_username = getattr(poap_cfg, "discovery_username", None)
        discovery_password = getattr(poap_cfg, "discovery_password", None)

        # Optional data block
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
            f"EXIT: _build_preprovision_model() -> {preprov_model.serial_number}"
        )
        return preprov_model

    def _preprovision_switches(
        self,
        models: List[PreProvisionSwitchModel],
    ) -> None:
        """POST pre-provision switch models to the ``preProvision`` endpoint."""
        self.log.debug("ENTER: _preprovision_switches()")

        endpoint = EpManageFabricSwitchActionsPreProvision()
        endpoint.fabric_name = self.fabric

        request_model = PreProvisionSwitchesRequestModel(switches=models)
        payload = request_model.to_payload()

        self.log.debug(f"preProvision endpoint: {endpoint.path}")
        self.log.debug(
            f"preProvision payload (masked): {self._mask_password(payload)}"
        )
        self.log.info(
            f"Pre-provisioning {len(models)} switch(es): "
            f"{[m.serial_number for m in models]}"
        )

        self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)

        response = self.nd.rest_send.response_current
        result = self.nd.rest_send.result_current

        self.results.action = "preprovision"
        self.results.response_current = response
        self.results.result_current = result
        self.results.diff_current = payload
        self.results.register_task_result()

        self.log.info(f"preProvision API response success: {result.get('success')}")
        self.log.debug("EXIT: _preprovision_switches()")

    # =========================================================================
    # RMA Operations (Return Material Authorization)
    # =========================================================================

    def _handle_rma_state(
        self,
        proposed_config: List[SwitchConfigModel],
    ) -> None:
        """Orchestrate the full RMA workflow.

        Flow:
            1. Collect RMA entries from each ``SwitchConfigModel``.
            2. Validate old switches exist and are unreachable/maintenance.
            3. Query bootstrap API for ``publicKey`` / ``fingerPrint``.
            4. Build ``RMASwitchModel`` and POST to ``provisionRMA``.
            5. Wait for new switches to become manageable.
            6. Save credentials and finalize (config-save + config-deploy).

        Called from ``manage_state()`` before normal discovery.
        """
        self.log.debug("ENTER: _handle_rma_state()")
        self.log.info(f"Processing RMA for {len(proposed_config)} switch config(s)")

        # Check mode — preview only
        if self.nd.module.check_mode:
            self.log.info("Check mode: would run RMA provision")
            self.results.action = "rma"
            self.results.response_current = {"MESSAGE": "check mode — skipped"}
            self.results.result_current = {"success": True, "changed": True}
            self.results.diff_current = {
                "rma_switches": [pc.seed_ip for pc in proposed_config]
            }
            self.results.register_task_result()
            return

        # Collect (SwitchConfigModel, RMAConfigModel) pairs
        rma_entries: List[Tuple[SwitchConfigModel, RMAConfigModel]] = []
        for switch_cfg in proposed_config:
            if not switch_cfg.rma:
                self.log.warning(
                    f"Switch config for {switch_cfg.seed_ip} has no RMA block — skipping"
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
            return

        self.log.info(f"Found {len(rma_entries)} RMA entry/entries to process")

        # Validate old switches exist and are in correct state
        old_switch_info = self._validate_rma_prerequisites(rma_entries)

        # Query bootstrap API for publicKey / fingerPrint of new switches
        bootstrap_switches = self._query_bootstrap_switches()
        bootstrap_index: Dict[str, Dict[str, Any]] = {
            sw.get("serialNumber", sw.get("serial_number", "")): sw
            for sw in bootstrap_switches
        }
        self.log.debug(
            f"Bootstrap index contains {len(bootstrap_index)} switch(es): "
            f"{list(bootstrap_index.keys())}"
        )

        # Build and submit each RMA request
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

        # Post-processing: wait, save credentials, finalize
        all_new_serials = [sn for sn, _ in switch_actions]

        self.log.info(
            f"Waiting for {len(all_new_serials)} RMA switch(es) to "
            f"become manageable: {all_new_serials}"
        )
        success = self.wait_utils.wait_for_switch_manageable(all_new_serials)
        if not success:
            self.log.warning("One or more RMA switches did not become manageable")

        self._bulk_save_credentials(switch_actions)
        self._finalize_operations()

        self.log.debug("EXIT: _handle_rma_state()")

    def _validate_rma_prerequisites(
        self,
        rma_entries: List[Tuple[SwitchConfigModel, RMAConfigModel]],
    ) -> Dict[str, Dict[str, Any]]:
        """Validate that each old switch meets RMA prerequisites.

        Checks for every ``(switch_cfg, rma_cfg)`` pair:
            1. ``old_serial`` exists in current fabric inventory.
            2. Discovery status is **unreachable**.
            3. System mode is **maintenance**.

        Returns:
            Dict keyed by ``old_serial`` with ``hostname`` and ``switch_data``.
        """
        self.log.debug("ENTER: _validate_rma_prerequisites()")

        existing_by_serial: Dict[str, SwitchDataModel] = {
            sw.serial_number: sw for sw in self.existing if sw.serial_number
        }

        result: Dict[str, Dict[str, Any]] = {}

        for switch_cfg, rma_cfg in rma_entries:
            old_serial = rma_cfg.old_serial

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

            if ad.discovery_status != DiscoveryStatus.UNREACHABLE.value:
                self.nd.module.fail_json(
                    msg=(
                        f"RMA: Switch '{old_serial}' has discovery status "
                        f"'{ad.discovery_status or 'unknown'}', "
                        f"expected 'unreachable'. The old switch must be "
                        f"unreachable before RMA can proceed."
                    )
                )

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
                f"discovery={ad.discovery_status}, mode={ad.system_mode})"
            )

        self.log.debug("EXIT: _validate_rma_prerequisites()")
        return result

    def _build_rma_model(
        self,
        switch_cfg: SwitchConfigModel,
        rma_cfg: RMAConfigModel,
        bootstrap_data: Dict[str, Any],
        old_switch_info: Dict[str, Any],
    ) -> RMASwitchModel:
        """Merge user RMA config with bootstrap API data into a complete model.

        User config values take priority.  Bootstrap API supplies ``publicKey``
        and ``fingerPrint``.  ``hostname`` is taken from the old switch's
        inventory record.

        Args:
            switch_cfg:      Parent config (seed_ip, role, password).
            rma_cfg:         RMAConfigModel from the user playbook.
            bootstrap_data:  Bootstrap GET API entry for the **new** switch.
            old_switch_info: Dict with ``hostname`` and ``switch_data`` from
                             ``_validate_rma_prerequisites``.
        """
        self.log.debug(
            f"ENTER: _build_rma_model(new={rma_cfg.serial_number}, "
            f"old={rma_cfg.old_serial})"
        )

        # User config fields
        new_switch_id = rma_cfg.serial_number
        hostname = old_switch_info.get("hostname", "")
        ip = switch_cfg.seed_ip
        model_name = rma_cfg.model
        version = rma_cfg.version
        image_policy = rma_cfg.image_policy
        gateway_ip_mask = rma_cfg.config_data.gateway
        switch_role = switch_cfg.role
        password = switch_cfg.password
        auth_proto = SnmpV3AuthProtocol.MD5  # RMA always uses MD5

        discovery_username = rma_cfg.discovery_username
        discovery_password = rma_cfg.discovery_password

        # Bootstrap API response fields
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

    def _provision_rma_switch(
        self,
        old_switch_id: str,
        rma_model: RMASwitchModel,
    ) -> None:
        """POST an ``RMASwitchModel`` to the per-switch ``provisionRMA`` endpoint.

        Args:
            old_switch_id: Serial number of the switch being replaced.
            rma_model:     Complete payload model for the new switch.
        """
        self.log.debug("ENTER: _provision_rma_switch()")

        endpoint = EpManageFabricSwitchProvisionRMA()
        endpoint.fabric_name = self.fabric
        endpoint.switch_id = old_switch_id

        payload = rma_model.to_payload()

        self.log.info(f"RMA: Replacing {old_switch_id} with {rma_model.new_switch_id}")
        self.log.debug(f"RMA endpoint: {endpoint.path}")
        self.log.debug(f"RMA payload (masked): {self._mask_password(payload)}")

        self.nd.request(path=endpoint.path, verb=endpoint.verb, data=payload)

        response = self.nd.rest_send.response_current
        result = self.nd.rest_send.result_current

        self.results.action = "rma"
        self.results.response_current = response
        self.results.result_current = result
        self.results.diff_current = {
            "old_switch_id": old_switch_id,
            "new_switch_id": rma_model.new_switch_id,
        }
        self.results.register_task_result()

        self.log.info(f"RMA provision API response success: {result.get('success')}")
        self.log.debug("EXIT: _provision_rma_switch()")

    # =========================================================================
    # Query Helpers
    # =========================================================================

    def _query_all_switches(self) -> List[Dict[str, Any]]:
        """Query all switches from the fabric.

        The ND API ``GET /fabrics/{fabricName}/switches`` returns the switch
        list directly as response DATA.  ``nd.request()`` already unwraps
        ``response["DATA"]``, so the result is either a ``list`` or a ``dict``
        with a ``"switches"`` key.  Both forms are handled.

        Returns:
            List of raw switch dicts from the controller.
        """
        endpoint = EpManageFabricSwitchesGet()
        endpoint.fabric_name = self.fabric
        self.log.debug(f"Querying all switches with endpoint: {endpoint.path}")
        self.log.debug(f"Query verb: {endpoint.verb}")

        result = self.nd.request(path=endpoint.path, verb=endpoint.verb)

        if isinstance(result, list):
            switches = result
        elif isinstance(result, dict):
            switches = result.get("switches", [])
        else:
            switches = []

        self.log.debug(f"Queried {len(switches)} switches from fabric {self.fabric}")
        return switches

    # =========================================================================
    # Utility Helpers
    # =========================================================================

    def _group_switches_by_credentials(
        self,
        switches: List[SwitchConfigModel],
    ) -> Dict[Tuple, List[SwitchConfigModel]]:
        """Group switches by shared credentials for bulk API operations.

        Groups by: ``(username, password_hash, auth_proto, platform_type,
        preserve_config)``.

        Args:
            switches: Validated ``SwitchConfigModel`` instances.

        Returns:
            Dict mapping credential tuple → list of switches.
        """
        groups: Dict[Tuple, List[SwitchConfigModel]] = {}

        for switch in switches:
            username = switch.user_name
            password = switch.password
            auth_proto = switch.auth_proto
            platform_type = switch.platform_type
            preserve_config = switch.preserve_config

            password_hash = hash(password)
            group_key = (username, password_hash, auth_proto, platform_type, preserve_config)

            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(switch)

        self.log.info(
            f"Grouped {len(switches)} switches into {len(groups)} credential group(s)"
        )

        for idx, (key, group_switches) in enumerate(groups.items(), 1):
            username, _, auth_proto, platform_type, preserve_config = key
            auth_value = auth_proto.value if hasattr(auth_proto, 'value') else str(auth_proto)
            platform_value = platform_type.value if hasattr(platform_type, 'value') else str(platform_type)
            self.log.debug(
                f"Group {idx}: {len(group_switches)} switches with "
                f"username={username}, auth={auth_value}, "
                f"platform={platform_value}, preserve_config={preserve_config}"
            )

        return groups

    def _get_switch_field(
        self,
        switch: Union[SwitchConfigModel, SwitchDiscoveryModel, Dict[str, Any]],
        field_names: List[str],
    ) -> Optional[Any]:
        """Extract a field value from a switch config, trying multiple names.

        Supports Pydantic models and plain dicts with both snake_case and
        camelCase key lookups.

        Args:
            switch:      Switch model or dict to extract from.
            field_names: Candidate field names to try, in priority order.

        Returns:
            First non-``None`` value found, or ``None``.
        """
        for name in field_names:
            if hasattr(switch, name):
                value = getattr(switch, name)
                if value is not None:
                    return value
            elif isinstance(switch, dict):
                if name in switch and switch[name] is not None:
                    return switch[name]
                # Try camelCase variant
                camel = ''.join(
                    word.capitalize() if i > 0 else word
                    for i, word in enumerate(name.split('_'))
                )
                if camel in switch and switch[camel] is not None:
                    return switch[camel]
        return None

    def _determine_operation_type(
        self,
        switch: Union[SwitchConfigModel, SwitchDiscoveryModel, Dict[str, Any]],
    ) -> str:
        """Determine the operation type from switch configuration.

        Returns:
            ``'normal'``, ``'poap'``, or ``'rma'``.
        """
        if isinstance(switch, SwitchConfigModel):
            return switch.operation_type

        if isinstance(switch, dict):
            if 'poap' in switch or 'bootstrap' in switch:
                return 'poap'
            if 'rma' in switch or 'old_serial' in switch or 'oldSerial' in switch:
                return 'rma'

        return 'normal'

    def _mask_password(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return a deep copy of *payload* with password fields masked."""
        masked = deepcopy(payload)
        password_fields = {'password', 'discoveryPassword', 'discovery_password'}

        def _mask_recursive(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in password_fields:
                        obj[key] = '***MASKED***'
                    elif isinstance(value, (dict, list)):
                        _mask_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    _mask_recursive(item)

        _mask_recursive(masked)
        return masked

    def _log_operation(self, operation: str, identifier: str) -> None:
        """Record an operation for result output."""
        self.nd_logs.append({
            "operation": operation,
            "identifier": identifier,
            "status": "success",
        })

    def _finalize_operations(self) -> None:
        """Run config-save and config-deploy for the fabric.

        Respects the ``save`` and ``deploy`` module parameters and
        check mode.  Neither endpoint requires a request body.
        """
        if self.nd.module.check_mode:
            return

        if self.save_config_flag:
            self.log.info("Saving fabric configuration")
            self.fabric_utils.save_config()

        if self.deploy_config_flag:
            self.log.info("Deploying fabric configuration")
            self.fabric_utils.deploy_config()
