# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Akshayant Chengam Saravanan (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Switch Utility Classes for ND Switch Resource Module.

Provides:
    - ``SwitchOperationError`` – Exception for switch operation failures.
    - ``PayloadUtils``         – Simple API payload builders.
    - ``FabricUtils``          – Fabric-level config save / deploy / info.
    - ``SwitchWaitUtils``      – Multi-phase wait for switch manageability.

Most complex payloads (discovery, add, POAP, RMA) are built by schema models
in ``switch_inventory_models.py`` via their ``to_payload()`` methods.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
import time
from typing import Any, Dict, List, Optional

from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.ep_manage_fabric_config import (
    EpManageFabricConfigDeploy,
    EpManageFabricConfigSave,
    EpManageFabricGet,
    EpManageFabricInventoryDiscover,
)
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.ep_manage_fabric_switches import (
    EpManageFabricSwitchesGet,
)
from ansible_collections.cisco.nd.plugins.module_utils.ep.v1.ep_manage_fabric_switch_actions import (
    EpManageFabricSwitchActionsRediscover,
)


# =========================================================================
# Exceptions
# =========================================================================


class SwitchOperationError(Exception):
    """Raised when a switch operation fails."""


# =========================================================================
# PayloadUtils
# =========================================================================


class PayloadUtils:
    """Build simple, dict-based API payloads.

    Complex payloads (discovery, add, POAP, RMA) are handled by
    schema models in ``switch_inventory_models.py``.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.log = logger or logging.getLogger("nd.PayloadUtils")

    def build_credentials_payload(
        self,
        serial_numbers: List[str],
        username: str,
        password: str,
    ) -> Dict[str, Any]:
        """Build payload for saving switch credentials.

        Args:
            serial_numbers: Switch serial numbers.
            username:       Switch username.
            password:       Switch password.

        Returns:
            Credentials API payload dict.
        """
        return {
            "switchIds": serial_numbers,
            "username": username,
            "password": password,
        }

    def build_switch_ids_payload(
        self,
        serial_numbers: List[str],
    ) -> Dict[str, Any]:
        """Build payload with switch IDs for remove / batch operations.

        Args:
            serial_numbers: Switch serial numbers.

        Returns:
            ``{"switchIds": [...]}`` payload dict.
        """
        return {"switchIds": serial_numbers}


# =========================================================================
# FabricUtils
# =========================================================================


class FabricUtils:
    """Fabric-level operations: config save, deploy, and info retrieval."""

    def __init__(
        self,
        nd_module,
        fabric: str,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize FabricUtils.

        Args:
            nd_module: NDModule or NDNetworkResourceModule instance.
            fabric:    Fabric name.
            logger:    Optional logger; defaults to ``nd.FabricUtils``.
        """
        self.nd = nd_module
        self.fabric = fabric
        self.log = logger or logging.getLogger("nd.FabricUtils")

        # Pre-configure endpoints
        self.ep_config_save = EpManageFabricConfigSave()
        self.ep_config_save.fabric_name = fabric

        self.ep_config_deploy = EpManageFabricConfigDeploy()
        self.ep_config_deploy.fabric_name = fabric

        self.ep_fabric_get = EpManageFabricGet()
        self.ep_fabric_get.fabric_name = fabric

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def save_config(self) -> Dict[str, Any]:
        """Save (recalculate) fabric configuration.

        Returns:
            API response dict.

        Raises:
            SwitchOperationError: If the save request fails.
        """
        return self._request_endpoint(
            self.ep_config_save, action="Config save"
        )

    def deploy_config(self) -> Dict[str, Any]:
        """Deploy pending configuration to all switches in the fabric.

        The ``configDeploy`` endpoint requires no request body; it deploys
        all pending changes for the fabric.

        Returns:
            API response dict.

        Raises:
            SwitchOperationError: If the deploy request fails.
        """
        return self._request_endpoint(
            self.ep_config_deploy, action="Config deploy"
        )

    def get_fabric_info(self) -> Dict[str, Any]:
        """Retrieve fabric information.

        Returns:
            Fabric information dict.

        Raises:
            SwitchOperationError: If the request fails.
        """
        return self._request_endpoint(
            self.ep_fabric_get, action="Get fabric info"
        )

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _request_endpoint(self, endpoint, action: str = "Request") -> Dict[str, Any]:
        """Execute a request against a pre-configured endpoint.

        Centralises the try / log / raise pattern shared by every public
        method so each method remains a one-liner.

        Args:
            endpoint: Endpoint object with ``.path`` and ``.verb``.
            action:   Human-readable label for log messages.

        Returns:
            API response dict.

        Raises:
            SwitchOperationError: On any request failure.
        """
        self.log.info(f"{action} for fabric: {self.fabric}")
        try:
            response = self.nd.request(endpoint.path, verb=endpoint.verb)
            self.log.info(f"{action} completed for fabric: {self.fabric}")
            return response
        except Exception as e:
            self.log.error(f"{action} failed for fabric {self.fabric}: {e}")
            raise SwitchOperationError(
                f"{action} failed for fabric {self.fabric}: {e}"
            ) from e


# =========================================================================
# SwitchWaitUtils
# =========================================================================


class SwitchWaitUtils:
    """Multi-phase wait utilities for switch lifecycle operations.

    Status constants align with schema enums in
    ``switch_inventory_models.py``:
        - ``DiscoveryStatus``         – ok, unreachable, timeout, …
        - ``ShallowDiscoveryStatus``  – manageable, notReacheable, …
    """

    # Default wait parameters
    DEFAULT_MAX_ATTEMPTS: int = 300
    DEFAULT_WAIT_INTERVAL: int = 5  # seconds

    # Status values indicating the switch is ready
    MANAGEABLE_STATUSES = frozenset({"ok", "manageable"})

    # Status values indicating an operation is still in progress
    IN_PROGRESS_STATUSES = frozenset({
        "inProgress", "migration", "discovering", "rediscovering",
    })

    # Status values indicating failure
    FAILED_STATUSES = frozenset({
        "failed",
        "unreachable",
        "authenticationFailed",
        "timeout",
        "discoveryTimeout",
        "notReacheable",       # Note: typo matches the API spec
        "notAuthorized",
        "unknownUserPassword",
        "connectionError",
        "sshSessionError",
    })

    # Sleep multipliers for each phase
    _MIGRATION_SLEEP_FACTOR: float = 2.0
    _REDISCOVERY_SLEEP_FACTOR: float = 3.5

    def __init__(
        self,
        nd_module,
        fabric: str,
        logger: Optional[logging.Logger] = None,
        max_attempts: Optional[int] = None,
        wait_interval: Optional[int] = None,
        fabric_utils: Optional["FabricUtils"] = None,
    ):
        """Initialize SwitchWaitUtils.

        Args:
            nd_module:     Parent module instance (must expose ``.nd``).
            fabric:        Fabric name.
            logger:        Optional logger; defaults to ``nd.SwitchWaitUtils``.
            max_attempts:  Max polling iterations (default ``300``).
            wait_interval: Seconds between polls (default ``5``).
            fabric_utils:  Injected ``FabricUtils`` for greenfield check
                           (Dependency Inversion). Created internally if
                           not provided.
        """
        self.nd = nd_module.nd
        self.fabric = fabric
        self.log = logger or logging.getLogger("nd.SwitchWaitUtils")
        self.max_attempts = max_attempts or self.DEFAULT_MAX_ATTEMPTS
        self.wait_interval = wait_interval or self.DEFAULT_WAIT_INTERVAL
        self.fabric_utils = fabric_utils or FabricUtils(nd_module, fabric, self.log)

        # Pre-configure endpoints
        self.ep_switches_get = EpManageFabricSwitchesGet()
        self.ep_switches_get.fabric_name = fabric

        self.ep_inventory_discover = EpManageFabricInventoryDiscover()
        self.ep_inventory_discover.fabric_name = fabric

        self.ep_rediscover = EpManageFabricSwitchActionsRediscover()
        self.ep_rediscover.fabric_name = fabric

        # Cached greenfield flag
        self._greenfield_debug_enabled: Optional[bool] = None

    # =====================================================================
    # Public API – Wait Methods
    # =====================================================================

    def wait_for_switch_manageable(
        self,
        serial_numbers: List[str],
        all_preserve_config: bool = False,
        skip_greenfield_check: bool = False,
    ) -> bool:
        """Wait for switches to exit migration mode and become manageable.

        Implements a multi-phase strategy:
            1. Wait for all switches to **exit** ``migration`` system mode.
            2. Wait for all switches to **enter** ``normal`` system mode.
            3. If **all** switches use ``preserve_config=True`` (brownfield),
               return immediately — brownfield switches do not reload.
            4. If the greenfield debug flag is enabled **and**
               ``skip_greenfield_check`` is ``False``, return immediately.
            5. Wait for discovery status ``unreachable`` (indicates reload).
            6. Trigger rediscovery, then wait for discovery status ``ok``.

        Args:
            serial_numbers:      Switch serial numbers to monitor.
            all_preserve_config: When ``True``, every switch in the batch is
                brownfield (``preserve_config=True``).  Brownfield switches
                keep their running config and **never reload**, so phases
                5-6 (reload detection) are skipped to avoid a ~25-minute
                timeout waiting for an ``unreachable`` state that never
                arrives.  This mirrors the ``all_brownfield_switches``
                optimisation in the legacy ``dcnm_inventory`` module.
            skip_greenfield_check: When ``True``, the greenfield debug flag
                shortcut (phase 4) is bypassed.  Used by POAP bootstrap
                imports where the device **always** reboots regardless of
                the fabric greenfield debug setting.

        Returns:
            ``True`` if all switches are manageable, ``False`` on timeout.
        """
        self.log.info(
            f"Waiting for switches to become manageable: {serial_numbers}"
        )

        # Phase 1 + 2: migration → normal
        if not self._wait_for_system_mode(serial_numbers):
            return False

        # Phase 3: brownfield shortcut — no reload expected
        if all_preserve_config:
            self.log.info(
                "All switches are brownfield (preserve_config=True) — "
                "skipping reload detection (phases 5-6)"
            )
            return True

        # Phase 4: greenfield shortcut (skipped for POAP bootstrap)
        if not skip_greenfield_check and self._is_greenfield_debug_enabled():
            self.log.info(
                "Greenfield debug flag enabled — "
                "skipping reload detection"
            )
            return True

        if skip_greenfield_check:
            self.log.info(
                "Greenfield debug check skipped "
                "(POAP bootstrap — device always reboots)"
            )

        # Phase 5: wait for "unreachable" (switch is reloading)
        if not self._wait_for_discovery_state(
            serial_numbers, "unreachable"
        ):
            return False

        # Phase 6: wait for "ok" (switch is ready)
        return self._wait_for_discovery_state(
            serial_numbers, "ok"
        )

    def wait_for_discovery(
        self,
        seed_ip: str,
        max_attempts: Optional[int] = None,
        wait_interval: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Poll until a single switch discovery completes.

        Args:
            seed_ip:       IP address of the switch being discovered.
            max_attempts:  Override max attempts (default ``30``).
            wait_interval: Override interval in seconds (default ``5``).

        Returns:
            Discovery data dict on success, ``None`` on failure or timeout.
        """
        attempts = max_attempts or 30
        interval = wait_interval or self.wait_interval

        self.log.info(f"Waiting for discovery of: {seed_ip}")

        for attempt in range(attempts):
            status = self._get_discovery_status(seed_ip)

            if status and status.get("status") in self.MANAGEABLE_STATUSES:
                self.log.info(f"Discovery completed for {seed_ip}")
                return status

            if status and status.get("status") in self.FAILED_STATUSES:
                self.log.error(f"Discovery failed for {seed_ip}: {status}")
                return None

            self.log.debug(
                f"Discovery attempt {attempt + 1}/{attempts} for {seed_ip}"
            )
            time.sleep(interval)

        self.log.warning(f"Discovery timeout for {seed_ip}")
        return None

    # =====================================================================
    # Phase Helpers – System Mode
    # =====================================================================

    def _wait_for_system_mode(self, serial_numbers: List[str]) -> bool:
        """Wait for switches to transition: migration → normal.

        Returns ``True`` when all switches are in ``normal`` mode,
        ``False`` on timeout or API failure.
        """
        # Sub-phase A: exit "migration" mode
        pending = self._poll_system_mode(
            serial_numbers, target_mode="migration", expect_match=True
        )
        if pending is None:
            return False

        # Sub-phase B: enter "normal" mode
        pending = self._poll_system_mode(
            serial_numbers, target_mode="normal", expect_match=False
        )
        if pending is None:
            return False

        self.log.info(
            "All switches in normal system mode — proceeding to discovery checks"
        )
        return True

    def _poll_system_mode(
        self,
        serial_numbers: List[str],
        target_mode: str,
        expect_match: bool,
    ) -> Optional[List[str]]:
        """Poll until no switches remain in (or outside) ``target_mode``.

        Args:
            serial_numbers: Switches to check.
            target_mode:    System mode string (e.g. ``"migration"``).
            expect_match:   If ``True``, wait for switches to **leave**
                            ``target_mode``.  If ``False``, wait for
                            switches to **enter** ``target_mode``.

        Returns:
            Empty list on success, ``None`` on timeout / API error.
        """
        pending = list(serial_numbers)
        label = f"exit '{target_mode}'" if expect_match else f"enter '{target_mode}'"

        for attempt in range(1, self.max_attempts + 1):
            if not pending:
                return pending

            switch_data = self._fetch_switch_data()
            if switch_data is None:
                return None

            remaining = self._filter_by_system_mode(
                pending, switch_data, target_mode, expect_match
            )

            if not remaining:
                self.log.info(f"All switches {label} mode (attempt {attempt})")
                return remaining

            pending = remaining
            self.log.debug(
                f"Attempt {attempt}/{self.max_attempts}: "
                f"{len(pending)} switch(es) waiting to {label}: {pending}"
            )
            time.sleep(self.wait_interval * self._MIGRATION_SLEEP_FACTOR)

        self.log.warning(
            f"Timeout waiting for switches to {label}: {pending}"
        )
        return None

    # =====================================================================
    # Filtering (static, pure-logic helpers)
    # =====================================================================

    @staticmethod
    def _filter_by_system_mode(
        serial_numbers: List[str],
        switch_data: List[Dict[str, Any]],
        target_mode: str,
        expect_match: bool,
    ) -> List[str]:
        """Return serial numbers that have NOT yet satisfied the mode check.

        Args:
            serial_numbers: Switches to inspect.
            switch_data:    Raw switch dicts from the GET API.
            target_mode:    e.g. ``"migration"`` or ``"normal"``.
            expect_match:   ``True`` → switch must *leave* target_mode to pass.
                            ``False`` → switch must *enter* target_mode to pass.

        Returns:
            Serial numbers still waiting.
        """
        switch_index = {
            sw.get("serialNumber"): sw for sw in switch_data
        }
        remaining: List[str] = []
        for sn in serial_numbers:
            sw = switch_index.get(sn)
            if sw is None:
                remaining.append(sn)
                continue
            mode = (
                sw.get("additionalData", {})
                .get("systemMode", "")
                .lower()
            )
            # expect_match=True:  "still in target_mode" → not done yet
            # expect_match=False: "not yet in target_mode" → not done yet
            still_waiting = (mode == target_mode) if expect_match else (mode != target_mode)
            if still_waiting:
                remaining.append(sn)
        return remaining

    @staticmethod
    def _filter_by_discovery_status(
        serial_numbers: List[str],
        switch_data: List[Dict[str, Any]],
        target_state: str,
    ) -> List[str]:
        """Return serial numbers that have NOT yet reached ``target_state``.

        Args:
            serial_numbers: Switches to inspect.
            switch_data:    Raw switch dicts from the GET API.
            target_state:   e.g. ``"unreachable"`` or ``"ok"``.

        Returns:
            Serial numbers still waiting.
        """
        switch_index = {
            sw.get("serialNumber"): sw for sw in switch_data
        }
        remaining: List[str] = []
        for sn in serial_numbers:
            sw = switch_index.get(sn)
            if sw is None:
                remaining.append(sn)
                continue
            status = (
                sw.get("additionalData", {})
                .get("discoveryStatus", "")
                .lower()
            )
            if status != target_state:
                remaining.append(sn)
        return remaining

    # =====================================================================
    # Phase Helpers – Discovery Status
    # =====================================================================

    def _wait_for_discovery_state(
        self,
        serial_numbers: List[str],
        target_state: str,
    ) -> bool:
        """Poll until all switches reach ``target_state`` discovery status.

        Triggers rediscovery on each iteration for switches that have not
        yet reached the target.

        Returns:
            ``True`` when all switches reach ``target_state``,
            ``False`` on timeout.
        """
        pending = list(serial_numbers)

        for attempt in range(1, self.max_attempts + 1):
            if not pending:
                return True

            switch_data = self._fetch_switch_data()
            if switch_data is None:
                return False

            pending = self._filter_by_discovery_status(
                pending, switch_data, target_state
            )

            if not pending:
                self.log.info(
                    f"All switches reached '{target_state}' state "
                    f"(attempt {attempt})"
                )
                return True

            self._trigger_rediscovery(pending)
            self.log.debug(
                f"Attempt {attempt}/{self.max_attempts}: "
                f"{len(pending)} switch(es) not yet '{target_state}': {pending}"
            )
            time.sleep(self.wait_interval * self._REDISCOVERY_SLEEP_FACTOR)

        self.log.warning(
            f"Timeout waiting for '{target_state}' state: {serial_numbers}"
        )
        return False

    # =====================================================================
    # API Helpers
    # =====================================================================

    def _fetch_switch_data(self) -> Optional[List[Dict[str, Any]]]:
        """GET current switch data for the fabric.

        Returns:
            List of switch dicts, or ``None`` on failure.
        """
        try:
            response = self.nd.request(
                self.ep_switches_get.path, verb=self.ep_switches_get.verb
            )
            switch_data = response.get("switches", [])
            if not switch_data:
                self.log.error("No switch data returned for fabric")
                return None
            return switch_data
        except Exception as e:
            self.log.error(f"Failed to fetch switch data: {e}")
            return None

    def _trigger_rediscovery(self, serial_numbers: List[str]) -> None:
        """POST a rediscovery request for the given switches.

        Args:
            serial_numbers: Switch serial numbers to rediscover.
        """
        if not serial_numbers:
            return

        payload = {"switchIds": serial_numbers}
        self.log.info(f"Triggering rediscovery for: {serial_numbers}")
        try:
            self.nd.request(
                self.ep_rediscover.path,
                verb=self.ep_rediscover.verb,
                data=payload,
            )
        except Exception as e:
            self.log.warning(f"Failed to trigger rediscovery: {e}")

    def _get_discovery_status(
        self, seed_ip: str,
    ) -> Optional[Dict[str, Any]]:
        """GET discovery status for a single switch by IP.

        Args:
            seed_ip: IP address of the switch.

        Returns:
            Switch dict from the discovery API, or ``None``.
        """
        try:
            response = self.nd.request(
                self.ep_inventory_discover.path,
                verb=self.ep_inventory_discover.verb,
            )
            for switch in response.get("switches", []):
                if switch.get("ip") == seed_ip or switch.get("ipaddr") == seed_ip:
                    return switch
            return None
        except Exception as e:
            self.log.debug(f"Discovery status check failed: {e}")
            return None

    def _is_greenfield_debug_enabled(self) -> bool:
        """Check whether the fabric has the greenfield debug flag enabled.

        Uses the injected ``FabricUtils`` instance (Dependency Inversion).
        Result is cached for the lifetime of the instance.

        Returns:
            ``True`` if the flag is ``"enable"``, ``False`` otherwise.
        """
        if self._greenfield_debug_enabled is not None:
            return self._greenfield_debug_enabled

        try:
            fabric_info = self.fabric_utils.get_fabric_info()
            self.log.debug(f"Fabric info retrieved for greenfield check: {fabric_info}")
            flag = (
                fabric_info
                .get("management", {})
                .get("greenfieldDebugFlag", "")
                .lower()
            )
            self.log.debug(f"Greenfield debug flag value: '{flag}'")
            self._greenfield_debug_enabled = flag == "enable"
        except Exception as e:
            self.log.debug(f"Failed to get greenfield debug flag: {e}")
            self._greenfield_debug_enabled = False

        return self._greenfield_debug_enabled
