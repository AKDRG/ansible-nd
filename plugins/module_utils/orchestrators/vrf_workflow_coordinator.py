# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

"""
VrfWorkflowCoordinator — Parent / child VRF workflow orchestration.

Replaces the following workflow handlers from the dcnm_vrf action plugin:
  - handle_parent_workflow
  - handle_child_workflow
  - handle_standalone_workflow
  - create_child_task / execute_child_task
  - create_structured_results

The coordinator is constructed inside nd_vrf.py after the strategy is
resolved. For standalone and child fabrics it runs the state machine
directly. For parent fabrics it:
  1. Pre-validates the config (vlan_id placement, vrf_lite structure).
  2. Strips child_fabric_config from each VRF → clean parent config.
  3. Runs the parent task via NDStateMachine (once wired).
  4. Builds child module_args per child fabric and re-invokes nd_vrf.
  5. Aggregates and structures the combined results.
"""

import copy
from typing import Any, Dict, List, Optional

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.cisco.nd.plugins.module_utils.nd import NDModule
from ansible_collections.cisco.nd.plugins.module_utils.nd_state_machine import NDStateMachine
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.vrfs import NDVrfOrchestrator
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.strategies.base_vrf import (
    BaseVrfStrategy,
)
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.vrf_fabric_resolver import (
    VrfFabricResolver,
)
from ansible_collections.cisco.nd.plugins.module_utils.common.pydantic_compat import (
    ValidationError,
)


class VrfWorkflowCoordinator:
    """
    Coordinates VRF operations across parent and child fabrics.

    Args:
        module:   The AnsibleModule instance (params, fail_json, check_mode).
        strategy: The resolved BaseVrfStrategy for the target fabric.
    """

    def __init__(
        self,
        module: AnsibleModule,
        strategy: BaseVrfStrategy,
    ):
        self.module = module
        self.strategy = strategy

    # ── Entry point ───────────────────────────────────────────────

    def run(self) -> Dict[str, Any]:
        """
        Execute the workflow appropriate for the resolved fabric type.

        Returns a result dict suitable for module.exit_json(**result).
        """
        module_args: Dict = dict(self.module.params)
        fabric_type: str = self.strategy.fabric_type

        if self.strategy.is_child:
            return self._handle_child_workflow(module_args, fabric_type)
        elif self.strategy.is_parent:
            return self._handle_parent_workflow(module_args, fabric_type)
        else:
            return self._handle_standalone_workflow(module_args, fabric_type)

    # ── Config parsing ────────────────────────────────────────────

    def _parse_config(
        self,
        config: List[Dict],
        model_cls: type,
        state: str,
    ) -> List[Dict]:
        """
        Validate each entry in ``config`` against ``model_cls`` and return
        the normalised list (Python field names, None values excluded).

        ``state`` is passed for context in error messages only; all states
        are validated the same way since the models enforce required fields.

        Validation errors are reported immediately via ``module.fail_json``.
        """
        parsed = []
        for idx, entry in enumerate(config):
            try:
                model = model_cls.from_config(entry)
                parsed.append(model.to_config())
            except ValidationError as exc:
                self.module.fail_json(
                    msg=(
                        f"config[{idx}] validation failed "
                        f"({model_cls.__name__}, state={state!r}): {exc}"
                    )
                )
        return parsed

    # ── Workflow handlers ─────────────────────────────────────────

    def _handle_standalone_workflow(
        self, module_args: Dict, fabric_type: str
    ) -> Dict[str, Any]:
        """
        Direct pass-through to the state machine.

        No child fabric considerations. Applies to standalone fabrics and
        to child fabrics that are targeted directly with state=query.
        """
        state = module_args.get("state", "merged")
        module_args["config"] = self._parse_config(
            module_args.get("config") or [], self.strategy.config_model_cls, state
        )
        result = self._run_state_machine(module_args)
        result.setdefault("fabric_type", fabric_type)
        result.setdefault("workflow", "Standalone Fabric VRF Processing")
        return result

    def _handle_child_workflow(
        self, module_args: Dict, fabric_type: str
    ) -> Dict[str, Any]:
        """
        Enforce the Multisite / Multicluster operational model for child fabrics.

        Only state='query' is permitted when the module targets a child fabric
        directly. All write operations must be driven by the parent fabric.
        """
        state = module_args.get("state")
        fabric_name = module_args.get("fabric")

        if state == "query":
            module_args["config"] = self._parse_config(
                module_args.get("config") or [], self.strategy.config_model_cls, state
            )
            result = self._run_state_machine(module_args)
            result.setdefault("fabric_type", fabric_type)
            result.setdefault(
                "workflow",
                f"{fabric_type.replace('_', ' ').title()} VRF Query",
            )
            return result

        self.module.fail_json(
            msg=(
                f"Attempted '{state}' operation directly on child fabric "
                f"'{fabric_name}'. "
                "Only state='query' is allowed on child fabrics. "
                "Run the operation against the parent fabric instead."
            )
        )

    def _handle_parent_workflow(
        self, module_args: Dict, fabric_type: str
    ) -> Dict[str, Any]:
        """
        Full parent orchestration: parent fabric first, then all child fabrics.

        Workflow steps:
          1. Pre-validate configs (vlan_id placement, vrf_lite structure).
          2. Split each VRF's child_fabric_config entries into per-fabric tasks.
          3. Build a clean parent config (child_fabric_config stripped).
          4. Run the parent state machine.
          5. If parent succeeded, execute each child task sequentially.
          6. Aggregate all results into a structured response.
        """
        log_type = "multicluster" if "multicluster" in fabric_type else "multisite"
        parent_fabric = module_args.get("fabric")
        state = module_args.get("state", "merged")
        config: List[Dict] = self._parse_config(
            module_args.get("config") or [], self.strategy.config_model_cls, state
        )

        # Collect member fabric names for relationship validation
        child_member_names = self.strategy.child_fabric_members()
        child_fabric_data_map: Dict[str, Dict] = {
            m.get("fabricName"): m
            for m in self.strategy.fabric_data.get("members", [])
            if m.get("fabricName")
        }

        # Step 2 & 3 — split config into parent config + child task groups
        parent_config: List[Dict] = []
        child_tasks_dict: Dict[str, Dict] = {}

        for vrf in config:
            child_configs = vrf.get("child_fabric_config") or []

            for child_cfg in child_configs:
                child_fabric_name = child_cfg.get("fabric")
                if child_fabric_name not in child_member_names:
                    self.module.fail_json(
                        msg=(
                            f"Fabric '{child_fabric_name}' is not a member of "
                            f"parent fabric '{parent_fabric}'. "
                            f"Known members: {child_member_names}"
                        )
                    )
                child_tasks_dict = self._accumulate_child_task(
                    vrf,
                    child_cfg,
                    child_tasks_dict,
                    child_fabric_data_map.get(child_fabric_name, {}),
                    state,
                )

            # Parent config: same VRF but without child_fabric_config
            parent_vrf = copy.deepcopy(vrf)
            parent_vrf.pop("child_fabric_config", None)
            parent_config.append(parent_vrf)

        # Step 4 — run parent state machine
        parent_module_args = copy.deepcopy(module_args)
        parent_module_args["config"] = parent_config
        parent_result = self._run_state_machine(parent_module_args)

        # Step 5 — execute child tasks (only if parent succeeded)
        child_results: List[Dict] = []
        if not parent_result.get("failed", False) and child_tasks_dict:
            for child_task in child_tasks_dict.values():
                child_result = self._run_child_task(child_task)
                child_result["child_fabric"] = child_task["fabric"]
                child_results.append(child_result)
                if child_result.get("failed", False):
                    # Abort on first child failure
                    break

        # Step 6 — aggregate and structure results
        return self._build_structured_result(
            parent_result, child_results, parent_fabric, fabric_type, log_type
        )

    # ── Config splitting helpers ──────────────────────────────────

    def _accumulate_child_task(
        self,
        parent_vrf: Dict,
        child_cfg: Dict,
        child_tasks_dict: Dict,
        child_fabric_data: Dict,
        state: str,
    ) -> Dict:
        """
        Merge one child_fabric_config entry into the running child_tasks_dict,
        grouping configs by child fabric name.

        Multiple VRFs that target the same child fabric are batched into a
        single task entry so only one module call is needed per child fabric.
        """
        child_cfg = copy.deepcopy(child_cfg)
        child_fabric_name: str = child_cfg.pop("fabric")

        # Inherit the VRF name from the parent VRF definition
        child_cfg["vrf_name"] = parent_vrf.get("vrf_name")

        if child_fabric_name in child_tasks_dict:
            # Append to existing child task (batch multiple VRFs together)
            child_tasks_dict[child_fabric_name]["module_args"]["config"].append(child_cfg)
            child_tasks_dict[child_fabric_name]["vrf_list"].append(child_cfg["vrf_name"])
        else:
            # First VRF for this child: create a new task entry
            child_module_args = self.strategy.build_child_task_args(
                child_fabric_name=child_fabric_name,
                vrf_configs=[child_cfg],
                state=state,
            )
            child_tasks_dict[child_fabric_name] = {
                "fabric": child_fabric_name,
                "module_args": child_module_args,
                "vrf_list": [child_cfg["vrf_name"]],
                "strategy": VrfFabricResolver.strategy_from_fabric_details(
                    child_fabric_name, child_fabric_data
                ),
            }

        return child_tasks_dict

    # ── State machine runner ──────────────────────────────────────

    def _run_state_machine(
        self, module_args: Dict, strategy: Optional[BaseVrfStrategy] = None
    ) -> Dict[str, Any]:
        """
        Run NDStateMachine for the given module_args and return the result dict.

        ``strategy`` defaults to ``self.strategy`` (the resolved fabric strategy).
        Pass an explicit strategy when running child fabric tasks so the
        orchestrator uses the child's endpoint configuration instead of the
        parent's.
        """
        active_strategy = strategy or self.strategy
        fabric_name = active_strategy.fabric_name
        state = module_args.get("state", "merged")

        # VrfDataModel uses a composite identifier (vrf_name, fabric_name).
        # Playbook entries carry only vrf_name — inject the fabric_name here.
        enriched_config = []
        for entry in (module_args.get("config") or []):
            enriched = dict(entry)
            enriched.setdefault("fabric_name", fabric_name)
            enriched_config.append(enriched)

        original_config = self.module.params.get("config")
        original_state = self.module.params.get("state")
        try:
            self.module.params["config"] = enriched_config
            self.module.params["state"] = state

            orchestrator = NDVrfOrchestrator(
                sender=NDModule(self.module),
                strategy=active_strategy,
            )
            sm = NDStateMachine(module=self.module, model_orchestrator=orchestrator)

            if state != "query":
                sm.manage_state()

            return sm.output.format()
        finally:
            self.module.params["config"] = original_config
            self.module.params["state"] = original_state

    # ── Child task runner ─────────────────────────────────────────

    def _run_child_task(self, child_task: Dict) -> Dict[str, Any]:
        """
        Execute a child fabric VRF task via its own orchestrator instance.

        Builds the child strategy from the ``fabric_details`` injected by the
        parent strategy's ``build_child_task_args()``, then runs
        ``_run_state_machine`` with that strategy.  No module re-invocation
        or subprocess is needed — the same state machine path used for
        standalone and parent fabrics is reused here.
        """
        module_args = child_task["module_args"]
        child_strategy = child_task["strategy"]
        return self._run_state_machine(module_args, strategy=child_strategy)

    # ── Result aggregation ────────────────────────────────────────

    def _build_structured_result(
        self,
        parent_result: Dict,
        child_results: List[Dict],
        parent_fabric: str,
        fabric_type: str,
        log_type: str,
    ) -> Dict[str, Any]:
        """
        Combine parent and child results into a single structured response dict.

        Parent-only (no children processed):
            Augments parent_result with fabric_type and workflow metadata.

        Parent-with-children:
            Returns a comprehensive dict with separate parent_fabric and
            child_fabrics sections, plus aggregated changed / failed status.
        """
        if not child_results:
            parent_result.setdefault("fabric_type", fabric_type)
            parent_result.setdefault(
                "workflow",
                f"{log_type.capitalize()} Parent without Child Fabric Processing",
            )
            return parent_result

        structured: Dict[str, Any] = {
            "changed": parent_result.get("changed", False),
            "failed": parent_result.get("failed", False),
            "fabric_type": fabric_type,
            "workflow": f"{log_type.capitalize()} Parent with Child Fabric Processing",
            "parent_fabric": {
                "fabric": parent_fabric,
                "changed": parent_result.get("changed", False),
                "diff": parent_result.get("diff", []),
                "response": parent_result.get("response", []),
                "invocation": parent_result.get("invocation"),
            },
            "child_fabrics": [],
        }

        for child_result in child_results:
            child_entry = {
                "fabric": child_result.get("child_fabric"),
                "changed": child_result.get("changed", False),
                "failed": child_result.get("failed", False),
                "diff": child_result.get("diff", []),
                "response": child_result.get("response", []),
                "invocation": child_result.get("invocation"),
            }
            structured["child_fabrics"].append(child_entry)

            if child_result.get("changed", False):
                structured["changed"] = True

            if child_result.get("failed", False):
                structured["failed"] = True
                structured["msg"] = (
                    f"Child fabric task failed for "
                    f"'{child_result.get('child_fabric')}': "
                    f"{child_result.get('msg', 'Unknown error')}"
                )

        return structured
