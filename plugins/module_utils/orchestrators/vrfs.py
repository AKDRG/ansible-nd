# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

"""
NDVrfOrchestrator — Orchestrator for ND VRF operations.

Unlike the links orchestrator (which uses a single API surface and picks the
strategy at module-entry time), the VRF orchestrator must:

  1. Dynamically select its strategy via VrfFabricResolver at run time.
  2. Handle the parent → child recursive invocation pattern:
       a. Run the parent fabric task through the state machine.
       b. For each child fabric, split the config, rebuild module_args,
          and re-invoke the module (via VrfWorkflowCoordinator).

The orchestrator is intentionally thin: it delegates endpoint selection to the
strategy and parent/child splitting to VrfWorkflowCoordinator.

Architecture overview
─────────────────────
  nd_vrf.py (AnsibleModule entry)
      │
      ▼
  VrfFabricResolver.resolve()  ──► BaseVrfStrategy subclass
      │
      ▼
  VrfWorkflowCoordinator.run()
      │
      ├── standalone / child ──► NDVrfOrchestrator ──► NDStateMachine
      │
      └── parent ─────────────► NDVrfOrchestrator (parent task)
                                  └── per child ──► nd_vrf (recursive)
"""

from typing import Any, ClassVar, Dict, List, Optional, Type

from ansible_collections.cisco.nd.plugins.module_utils.models.base import NDBaseModel
from ansible_collections.cisco.nd.plugins.module_utils.models.manage_vrfs.vrf_data_models import (
    VrfDataModel,
)
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.base import NDBaseOrchestrator
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.types import ResponseType
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.strategies.base_vrf import (
    BaseVrfStrategy,
)

NDVrfModel = VrfDataModel


class NDVrfOrchestrator(NDBaseOrchestrator["NDVrfModel"]):
    """
    Orchestrator for ND VRF CRUD operations.

    Delegates endpoint selection to a BaseVrfStrategy instance, enabling the
    same orchestrator to work across standalone, multisite-parent,
    multicluster-parent, and child fabric scopes.
    """

    # ── Class-level configuration ─────────────────────────────────

    model_class: ClassVar[Type[NDBaseModel]] = NDVrfModel

    # VRFs are individual resources; bulk-create IS supported by the API
    # (POST /vrfs accepts a list of objects).
    supports_bulk_create: ClassVar[bool] = True
    # vrfActions/remove accepts a list of VRF names.
    supports_bulk_delete: ClassVar[bool] = True
    supports_bulk_update: ClassVar[bool] = False

    # Endpoints are None here — always resolved via the strategy at call time.
    create_endpoint: Optional[Type] = None
    update_endpoint: Optional[Type] = None
    delete_endpoint: Optional[Type] = None
    query_one_endpoint: Optional[Type] = None
    query_all_endpoint: Optional[Type] = None

    # Strategy is injected at construction time by nd_vrf.py / VrfFabricResolver.
    strategy: Optional[BaseVrfStrategy] = None

    def model_post_init(self, __context) -> None:
        if self.strategy is None:
            raise ValueError("NDVrfOrchestrator requires a strategy instance.")

    # ── Endpoint factory ──────────────────────────────────────────

    def _make_endpoint(self, endpoint_cls, **extra_fields):
        """
        Instantiate an endpoint, set ``fabric_name`` from the strategy, call
        the strategy's ``configure_endpoint`` hook (e.g. to inject cluster_name
        for Multicluster fabrics), then apply any per-call identifiers.
        """
        ep = endpoint_cls()
        ep.fabric_name = self.strategy.fabric_name
        self.strategy.configure_endpoint(ep)
        for attr, val in extra_fields.items():
            setattr(ep, attr, val)
        return ep

    # ── Query ─────────────────────────────────────────────────────

    def query_all(self, model_instance=None, **kwargs) -> ResponseType:
        """GET all VRFs for the fabric."""
        try:
            endpoint = self._make_endpoint(self.strategy.vrfs_get_cls())
            result = self.sender.query_obj(endpoint.path)
            if isinstance(result, dict):
                return result.get("items", [])
            return result or []
        except Exception as e:
            raise Exception(f"Query all VRFs failed: {e}") from e

    # ── Create ────────────────────────────────────────────────────

    def create(self, model_instance: NDVrfModel, **kwargs) -> ResponseType:
        """POST a single VRF."""
        return self.create_bulk([model_instance])

    def create_bulk(self, model_instances: List[NDVrfModel], **kwargs) -> ResponseType:
        """POST a list of VRFs in a single request."""
        if not model_instances:
            return {}
        try:
            endpoint = self._make_endpoint(self.strategy.vrfs_post_cls())
            return self.sender.request(
                path=endpoint.path,
                method=endpoint.verb,
                data=[m.to_payload() for m in model_instances],
            )
        except Exception as e:
            raise Exception(
                f"Bulk create VRFs failed: {e}"
            ) from e

    # ── Update ────────────────────────────────────────────────────

    def update(self, model_instance: NDVrfModel, **kwargs) -> ResponseType:
        """PUT (replace) a single VRF identified by vrfName."""
        try:
            # Composite identifier is (vrf_name, fabric_name); vrf_name is index 0.
            vrf_name = model_instance.get_identifier_value()[0]
            endpoint = self._make_endpoint(
                self.strategy.vrf_put_cls(),
                vrf_name=vrf_name,
            )
            return self.sender.request(
                path=endpoint.path,
                method=endpoint.verb,
                data=model_instance.to_payload(),
            )
        except Exception as e:
            raise Exception(
                f"Update VRF failed for {model_instance.get_identifier_value()}: {e}"
            ) from e

    # ── Delete ────────────────────────────────────────────────────

    def delete(self, model_instance: NDVrfModel, **kwargs) -> ResponseType:
        """Delete a single VRF (delegates to bulk endpoint)."""
        return self.delete_bulk([model_instance])

    def delete_bulk(self, model_instances: List[NDVrfModel], **kwargs) -> ResponseType:
        """POST to vrfActions/remove to delete multiple VRFs in a single call."""
        if not model_instances:
            return {}
        try:
            # Composite identifier is (vrf_name, fabric_name); vrf_name is index 0.
            vrf_names = [m.get_identifier_value()[0] for m in model_instances]
            endpoint = self._make_endpoint(self.strategy.vrf_actions_remove_post_cls())
            return self.sender.request(
                path=endpoint.path,
                method=endpoint.verb,
                data={"vrfs": vrf_names},
            )
        except Exception as e:
            raise Exception(f"Bulk delete VRFs failed: {e}") from e
