# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

"""
VrfFabricResolver — Dynamically selects the correct VRF strategy based on
the fabric type returned by the ND Manage API.

This consolidates the action plugin's fabric-type detection and workflow
routing into a single, testable, reusable component under the orchestrator
layer.

Detection algorithm (mirrors dcnm_vrf action plugin logic):
 1. Query federated fabric associations (MFD / "mcfg" scope).
 2. If federation manager absent, fall back to MSD associations.
 3. Classify the target fabric:
      multicluster_parent, multicluster_child,
      multisite_parent,    multisite_child,
      standalone
 4. Return the matching concrete strategy instance.
"""

from typing import Any, Dict, Optional, Tuple

from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.strategies.base_vrf import (
    BaseVrfStrategy,
)
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.strategies.standalone_vrf import (
    StandaloneVrfStrategy,
)
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.strategies.multisite_parent_vrf import (
    MultisiteParentVrfStrategy,
)
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.strategies.multicluster_parent_vrf import (
    MulticlusterParentVrfStrategy,
)
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.strategies.child_vrf import (
    ChildVrfStrategy,
)


# ---------------------------------------------------------------------------
# Internal fabric-type detection helper
# ---------------------------------------------------------------------------

def _detect_fabric_type(
    fabric_name: str,
    fabric_associations: Dict[str, Any],
    data_type: str,
) -> Tuple[Optional[str], Optional[Dict]]:
    """
    Classify a fabric based on its properties in the fabric associations dict.

    Args:
        fabric_name: The fabric to classify.
        fabric_associations: Mapping of fabricName → fabric properties dict.
        data_type: "mcfg" for federated (MFD) data, "msd" for MSD data.

    Returns:
        (fabric_type_str, fabric_data_dict) or (None, None) if not found.
    """
    if fabric_name not in fabric_associations:
        return None, None

    fabric_data = fabric_associations[fabric_name]
    fabric_type = fabric_data.get("fabricType")
    fabric_state = fabric_data.get("fabricState")
    detected_type: Optional[str] = None

    if data_type == "mcfg":
        if fabric_type == "MFD":
            detected_type = "multicluster_parent"
        elif fabric_state == "member":
            detected_type = "multicluster_child"

    elif data_type == "msd":
        if fabric_type == "MSD":
            detected_type = "multisite_parent"
        elif fabric_state == "member":
            detected_type = "multisite_child"
        else:
            # Standalone: not MSD parent, not a member
            detected_type = "standalone"

    return detected_type, fabric_data


# ---------------------------------------------------------------------------
# Public resolver
# ---------------------------------------------------------------------------

class VrfFabricResolver:
    """
    Resolves the correct VRF strategy for a given fabric name by querying
    fabric association data from the ND controller.

    Usage
    -----
    resolver = VrfFabricResolver(nd_module=nd_module, fabric_name="fab1")
    strategy = resolver.resolve()
    # strategy is now e.g. MultisiteParentVrfStrategy(fabric_name="fab1", ...)
    """

    # Sentinel returned by the ND API when no federation manager is present.
    _NO_FEDERATION_MANAGER = "A federation manager does not exist"

    def __init__(self, nd_module: Any, fabric_name: str):
        """
        Args:
            nd_module: An NDModule instance (provides send/receive to the ND API).
            fabric_name: The fabric whose type should be resolved.
        """
        self._nd = nd_module
        self.fabric_name = fabric_name

    # ── Public API ─────────────────────────────────────────────────

    def resolve(self) -> BaseVrfStrategy:
        """
        Query ND for fabric associations and return the matching strategy.

        Raises:
            ValueError: If the fabric is not found in any association data.
        """
        fabric_type, fabric_data = self._resolve_fabric_type()
        return self._build_strategy(fabric_type, fabric_data)

    # ── Internal helpers ───────────────────────────────────────────

    def _fetch_federated_fabric_associations(self) -> Any:
        """
        GET federated fabric associations (multicluster / MFD scope).

        Returns either a mapping of fabricName → fabric data, or the
        no-federation-manager sentinel string when the ND site is not
        part of a federation.

        TODO: Wire to the ND federated-fabric API endpoint once it is
        catalogued in endpoints/v1/manage/.
        Tracked in: <issue / PR reference>
        """
        # PLACEHOLDER
        raise NotImplementedError(
            "VrfFabricResolver._fetch_federated_fabric_associations: "
            "Not yet implemented. Wire to the ND federated-fabric API endpoint."
        )

    def _fetch_fabric_associations(self) -> Dict[str, Any]:
        """
        GET standard fabric associations (MSD scope).

        Returns a mapping of fabricName → fabric properties dict.

        TODO: Wire to the fabric-associations endpoint once catalogued.
        Tracked in: <issue / PR reference>
        """
        # PLACEHOLDER
        raise NotImplementedError(
            "VrfFabricResolver._fetch_fabric_associations: "
            "Not yet implemented. Wire to the ND fabric-associations API endpoint."
        )

    def _resolve_fabric_type(self) -> Tuple[str, Dict]:
        """
        Run the two-phase detection logic (mcfg → msd fallback).

        Phase 1: Try federated (MFD / "mcfg") associations.
        Phase 2: Fall back to MSD associations if Phase 1 fails or the
                 fabric is not classified by mcfg data.

        Returns:
            (fabric_type_string, raw_fabric_data_dict)

        Raises:
            ValueError if the fabric cannot be found in any data source.
        """
        # Phase 1 — federated (MFD / "mcfg")
        try:
            fed_data = self._fetch_federated_fabric_associations()
            if fed_data != self._NO_FEDERATION_MANAGER:
                fabric_type, fabric_data = _detect_fabric_type(
                    self.fabric_name, fed_data, "mcfg"
                )
                if fabric_type:
                    return fabric_type, fabric_data
                # Fabric present but unclassified by mcfg — fall through
        except NotImplementedError:
            # Phase 1 endpoint not yet wired; skip straight to Phase 2
            pass

        # Phase 2 — MSD associations
        msd_data = self._fetch_fabric_associations()
        fabric_type, fabric_data = _detect_fabric_type(
            self.fabric_name, msd_data, "msd"
        )
        if not fabric_type:
            raise ValueError(
                f"Fabric '{self.fabric_name}' not found in any NDFC fabric "
                "associations. Verify the fabric name and ND connectivity."
            )
        return fabric_type, fabric_data

    def _build_strategy(self, fabric_type: str, fabric_data: Dict) -> BaseVrfStrategy:
        """Instantiate and return the strategy that matches fabric_type."""
        common = dict(
            fabric_name=self.fabric_name,
            fabric_data=fabric_data,
        )

        if fabric_type == "multicluster_parent":
            return MulticlusterParentVrfStrategy(**common)
        elif fabric_type == "multisite_parent":
            return MultisiteParentVrfStrategy(**common)
        elif fabric_type == "multicluster_child":
            return ChildVrfStrategy(
                cluster_name=fabric_data.get("clusterName"), **common
            )
        elif fabric_type == "multisite_child":
            return ChildVrfStrategy(**common)
        else:
            # "standalone" and any unrecognised value
            return StandaloneVrfStrategy(**common)

    # ── Fast-path strategy builder (no API call) ───────────────────

    @staticmethod
    def strategy_from_fabric_details(
        fabric_name: str, fabric_details: Dict
    ) -> BaseVrfStrategy:
        """
        Build a strategy directly from an injected ``fabric_details`` dict.

        Used by VrfWorkflowCoordinator when executing child fabric tasks:
        the parent already resolved the child's type during config splitting,
        so no ND API round-trip is needed.

        ``fabric_details`` is an INTERNAL field — it is never exposed to
        playbook authors.
        """
        ft = fabric_details.get("fabric_type", "standalone")
        cluster_name = fabric_details.get("cluster_name")
        kwargs: Dict = dict(fabric_name=fabric_name)

        if ft == "multicluster_child":
            return ChildVrfStrategy(cluster_name=cluster_name, **kwargs)
        elif ft == "multisite_child":
            return ChildVrfStrategy(**kwargs)
        elif ft == "multicluster_parent":
            return MulticlusterParentVrfStrategy(**kwargs)
        elif ft == "multisite_parent":
            return MultisiteParentVrfStrategy(**kwargs)
        else:
            return StandaloneVrfStrategy(**kwargs)
