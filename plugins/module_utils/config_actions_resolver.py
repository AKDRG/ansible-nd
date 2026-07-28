# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Shared config_actions intent utilities for ND modules.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from typing import Any


@dataclass(frozen=True)
class ConfigDeployCapability:
    """
    # Summary

    Describe the config_actions contract supported by one module.

    The capability is intentionally endpoint-free.  It declares which deploy controls a module exposes; the module still
    owns the API calls, payloads, wait loops, and fabric-strategy routing used to execute the resulting plan.

    ## Raises

    ### ValueError

    - If defaults or supported types describe an impossible module contract.
    """

    supports_save: bool = False
    supports_deploy: bool = True
    deploy_types: tuple[str, ...] = ("switch",)
    default_save: bool = False
    default_deploy: bool = True
    default_type: str = "switch"
    read_only_states: tuple[str, ...] = ("gathered",)
    deploy_requires_save: bool = False
    config_key: str = "config"
    item_deploy_key: str = "deploy"

    def __post_init__(self) -> None:
        if len(set(self.deploy_types)) != len(self.deploy_types):
            raise ValueError("ConfigDeployCapability.deploy_types must not contain duplicates")
        if not self.supports_save and self.default_save:
            raise ValueError("default_save=True requires supports_save=True")
        if not self.supports_deploy and self.default_deploy:
            raise ValueError("default_deploy=True requires supports_deploy=True")
        if self.deploy_requires_save and not self.supports_save:
            raise ValueError("deploy_requires_save=True requires supports_save=True")
        if self.supports_deploy and not self.deploy_types:
            raise ValueError("supports_deploy=True requires at least one deploy type")
        if self.supports_deploy and self.default_type not in self.deploy_types:
            raise ValueError(f"default_type={self.default_type!r} must be one of {list(self.deploy_types)!r}")
        if not self.supports_deploy and self.deploy_types:
            raise ValueError("deploy_types must be empty when supports_deploy=False")


@dataclass(frozen=True)
class ConfigDeployPlan:
    """
    # Summary

    Normalized deployment intent derived from config_actions.

    Modules should use this plan to decide whether to run their existing save/deploy flow.  The plan does not call APIs
    and does not know endpoint payload details.

    ## Raises

    None
    """

    save: bool
    deploy: bool
    deploy_type: str
    item_deploy_key: str = "deploy"

    def item_deploy_enabled(self, item: Mapping[str, Any] | None) -> bool:
        """
        # Summary

        Return the effective deploy decision for one config item.

        A missing item-level deploy value inherits the top-level plan.  An explicit item-level boolean overrides the
        top-level default.

        ## Raises

        ### ValueError

        - If the item-level deploy value is present but is not boolean.
        """
        if not item or self.item_deploy_key not in item or item.get(self.item_deploy_key) is None:
            return self.deploy
        value = item.get(self.item_deploy_key)
        if not isinstance(value, bool):
            raise ValueError("config item deploy must be a boolean when provided")
        return value

    def deploy_enabled_items(self, config: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        """
        # Summary

        Return config items whose effective deploy decision is enabled.

        ## Raises

        ### ValueError

        - If any item-level deploy value is present but is not boolean.
        """
        return [item for item in config if self.item_deploy_enabled(item)]

    def to_dict(self) -> dict[str, Any]:
        """
        # Summary

        Return a plain dict representation safe for module params, traces, and unit-test assertions.

        ## Raises

        None
        """
        return {
            "save": self.save,
            "deploy": self.deploy,
            "type": self.deploy_type,
        }


def get_raw_module_args() -> dict[str, Any]:
    """
    # Summary

    Return raw user-provided module arguments before Ansible applies argspec defaults.

    This is best-effort and intentionally side-effect free.  It allows config_actions validation to distinguish explicit
    user intent from Ansible-injected defaults.

    ## Raises

    None
    """
    try:
        from ansible.module_utils import basic as ansible_basic

        raw_payload = getattr(ansible_basic, "_ANSIBLE_ARGS", None)
        if raw_payload is None:
            return {}
        if isinstance(raw_payload, (bytes, bytearray)):
            decoded = raw_payload.decode("utf-8")
        elif isinstance(raw_payload, str):
            decoded = raw_payload
        else:
            return {}

        parsed = json.loads(decoded)
        module_args = parsed.get("ANSIBLE_MODULE_ARGS")
        return module_args if isinstance(module_args, dict) else {}
    except Exception:
        return {}


def resolve_config_deploy_plan(
    *,
    capability: ConfigDeployCapability,
    module: Any | None = None,
    params: Mapping[str, Any] | None = None,
    raw_args: Mapping[str, Any] | None = None,
    state: str | None = None,
) -> ConfigDeployPlan:
    """
    # Summary

    Validate module config_actions input and return a normalized deployment intent plan.

    The function only resolves intent.  The caller remains responsible for applying the plan through its existing module
    workflow and endpoint strategy.

    ## Raises

    ### ValueError

    - If config_actions contains options unsupported by the module capability.
    - If the requested deploy type is unsupported.
    - If read-only states request save or deploy.
    - If item-level deploy overrides are not boolean.
    """
    module_params = dict(params or getattr(module, "params", {}) or {})
    explicit_args = dict(raw_args or get_raw_module_args())
    current_state = state or module_params.get("state")

    raw_config_actions = explicit_args.get("config_actions")
    explicit_config_actions = raw_config_actions if isinstance(raw_config_actions, Mapping) else {}
    config_actions = module_params.get("config_actions") or {}
    if not isinstance(config_actions, Mapping):
        raise ValueError("config_actions must be a dictionary")

    _validate_supported_explicit_options(explicit_config_actions, capability)
    _validate_config_actions_value_types(config_actions, capability)

    save = _resolve_save(config_actions, capability)
    deploy = _resolve_deploy(config_actions, capability)
    deploy_type = _resolve_deploy_type(config_actions, capability)

    config_items = _config_items(module_params.get(capability.config_key))
    _validate_item_deploy_values(config_items, capability)

    if current_state in capability.read_only_states:
        _validate_read_only_state(
            state=current_state,
            explicit_config_actions=explicit_config_actions,
            raw_config=explicit_args.get(capability.config_key),
            capability=capability,
        )
        return ConfigDeployPlan(save=False, deploy=False, deploy_type=deploy_type, item_deploy_key=capability.item_deploy_key)

    if capability.deploy_requires_save and deploy and not save:
        raise ValueError("config_actions.deploy=true requires config_actions.save=true")

    return ConfigDeployPlan(save=save, deploy=deploy, deploy_type=deploy_type, item_deploy_key=capability.item_deploy_key)


def _resolve_save(config_actions: Mapping[str, Any], capability: ConfigDeployCapability) -> bool:
    if not capability.supports_save:
        return False
    return bool(config_actions.get("save", capability.default_save))


def _resolve_deploy(config_actions: Mapping[str, Any], capability: ConfigDeployCapability) -> bool:
    if not capability.supports_deploy:
        return False
    return bool(config_actions.get("deploy", capability.default_deploy))


def _resolve_deploy_type(config_actions: Mapping[str, Any], capability: ConfigDeployCapability) -> str:
    deploy_type = str(config_actions.get("type", capability.default_type))
    if capability.supports_deploy and deploy_type not in capability.deploy_types:
        raise ValueError(f"config_actions.type={deploy_type!r} is not supported. Supported values: {list(capability.deploy_types)!r}")
    return deploy_type


def _validate_supported_explicit_options(explicit_config_actions: Mapping[str, Any], capability: ConfigDeployCapability) -> None:
    unsupported = []
    if "save" in explicit_config_actions and not capability.supports_save:
        unsupported.append("save")
    if "deploy" in explicit_config_actions and not capability.supports_deploy:
        unsupported.append("deploy")
    if "type" in explicit_config_actions and not capability.supports_deploy:
        unsupported.append("type")
    if unsupported:
        raise ValueError(f"Unsupported config_actions option(s): {', '.join(sorted(unsupported))}")


def _validate_config_actions_value_types(config_actions: Mapping[str, Any], capability: ConfigDeployCapability) -> None:
    for key in ("save", "deploy"):
        if key not in config_actions or config_actions.get(key) is None:
            continue
        if not isinstance(config_actions.get(key), bool):
            raise ValueError(f"config_actions.{key} must be a boolean")
    if capability.supports_deploy and "type" in config_actions and config_actions.get("type") is not None and not isinstance(config_actions.get("type"), str):
        raise ValueError("config_actions.type must be a string")


def _config_items(config: Any) -> list[Mapping[str, Any]]:
    if config is None:
        return []
    if not isinstance(config, list):
        return []
    return [item for item in config if isinstance(item, Mapping)]


def _validate_item_deploy_values(config: list[Mapping[str, Any]], capability: ConfigDeployCapability) -> None:
    for index, item in enumerate(config):
        if capability.item_deploy_key not in item or item.get(capability.item_deploy_key) is None:
            continue
        if not isinstance(item.get(capability.item_deploy_key), bool):
            raise ValueError(f"{capability.config_key}[{index}].{capability.item_deploy_key} must be a boolean when provided")


def _validate_read_only_state(
    *,
    state: str | None,
    explicit_config_actions: Mapping[str, Any],
    raw_config: Any,
    capability: ConfigDeployCapability,
) -> None:
    explicit_save = bool(explicit_config_actions.get("save", False))
    explicit_deploy = bool(explicit_config_actions.get("deploy", False))
    if explicit_save or explicit_deploy:
        raise ValueError(f"config_actions.save/config_actions.deploy are not allowed for state={state!r}")

    for index, item in enumerate(_config_items(raw_config)):
        if bool(item.get(capability.item_deploy_key, False)):
            raise ValueError(f"{capability.config_key}[{index}].{capability.item_deploy_key}=true is not allowed for state={state!r}")
