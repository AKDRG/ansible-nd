# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Unit tests for config_actions_resolver.py.
"""

from __future__ import annotations

import pytest

from ansible_collections.cisco.nd.plugins.module_utils.config_actions_resolver import (
    ConfigDeployCapability,
    ConfigDeployPlan,
    resolve_config_deploy_plan,
)


def test_config_actions_resolver_00000_capability_rejects_impossible_defaults() -> None:
    """
    # Summary

    Verify capability construction rejects internally inconsistent module contracts.

    ## Raises

    None
    """
    with pytest.raises(ValueError, match="default_deploy=True requires supports_deploy=True"):
        ConfigDeployCapability(supports_deploy=False, deploy_types=(), default_deploy=True)

    with pytest.raises(ValueError, match="default_type='global' must be one of"):
        ConfigDeployCapability(deploy_types=("switch",), default_type="global")

    with pytest.raises(ValueError, match="deploy_requires_save=True requires supports_save=True"):
        ConfigDeployCapability(deploy_requires_save=True)

    with pytest.raises(ValueError, match="resource_deploy_type must be one of deploy_types"):
        ConfigDeployCapability(
            deploy_types=("switch",),
            item_deploy_requires_resource_type=True,
        )


def test_config_actions_resolver_00200_resolve_plan_uses_defaults_and_item_overrides() -> None:
    """
    # Summary

    Verify the resolved plan preserves module defaults and tri-state item-level deploy override semantics.

    ## Raises

    None
    """
    capability = ConfigDeployCapability(deploy_types=("switch", "resource"), default_deploy=False, default_type="resource")
    plan = resolve_config_deploy_plan(
        capability=capability,
        params={
            "state": "merged",
            "config_actions": {},
            "config": [
                {"name": "inherits"},
                {"name": "included", "deploy": True},
                {"name": "excluded", "deploy": False},
            ],
        },
        raw_args={},
    )

    assert plan == ConfigDeployPlan(save=False, deploy=False, deploy_type="resource")
    assert plan.item_deploy_enabled({"name": "inherits"}) is False
    assert plan.item_deploy_enabled({"name": "included", "deploy": True}) is True
    assert plan.item_deploy_enabled({"name": "excluded", "deploy": False}) is False
    assert [item["name"] for item in plan.deploy_enabled_items([{"name": "a"}, {"name": "b", "deploy": True}])] == ["b"]
    assert plan.to_dict() == {"save": False, "deploy": False, "type": "resource"}


def test_config_actions_resolver_00210_resolve_plan_accepts_save_when_capability_supports_it() -> None:
    """
    # Summary

    Verify modules that support save can require save before deploy.

    ## Raises

    None
    """
    capability = ConfigDeployCapability(
        supports_save=True,
        deploy_requires_save=True,
        deploy_types=("switch", "global"),
        default_save=False,
        default_deploy=False,
    )
    plan = resolve_config_deploy_plan(
        capability=capability,
        params={"state": "merged", "config_actions": {"save": True, "deploy": True, "type": "global"}},
        raw_args={"config_actions": {"save": True, "deploy": True, "type": "global"}},
    )

    assert plan.save is True
    assert plan.deploy is True
    assert plan.deploy_type == "global"


def test_config_actions_resolver_00300_resolve_plan_rejects_invalid_deploy_contracts() -> None:
    """
    # Summary

    Verify invalid config_actions and item-level deploy values fail before a module mutates controller state.

    ## Raises

    None
    """
    capability = ConfigDeployCapability(deploy_types=("switch", "resource"))

    with pytest.raises(ValueError, match="not supported"):
        resolve_config_deploy_plan(capability=capability, params={"state": "merged", "config_actions": {"type": "global"}}, raw_args={})

    with pytest.raises(ValueError, match="Unsupported config_actions option"):
        resolve_config_deploy_plan(
            capability=capability,
            params={"state": "merged", "config_actions": {"deploy": True}},
            raw_args={"config_actions": {"save": False}},
        )

    with pytest.raises(ValueError, match=r"config\[0\]\.deploy must be a boolean"):
        resolve_config_deploy_plan(
            capability=capability,
            params={"state": "merged", "config": [{"name": "bad", "deploy": "yes"}]},
            raw_args={},
        )

    with pytest.raises(ValueError, match="config_actions.deploy must be a boolean"):
        resolve_config_deploy_plan(
            capability=capability,
            params={"state": "merged", "config_actions": {"deploy": "false"}},
            raw_args={},
        )

    with pytest.raises(ValueError, match="config_actions.type must be a string"):
        resolve_config_deploy_plan(
            capability=capability,
            params={"state": "merged", "config_actions": {"type": 123}},
            raw_args={},
        )

    with pytest.raises(ValueError, match="config item deploy must be a boolean"):
        ConfigDeployPlan(save=False, deploy=True, deploy_type="switch").item_deploy_enabled({"deploy": "yes"})


def test_config_actions_resolver_00310_resolve_plan_rejects_deploy_without_required_save() -> None:
    """
    # Summary

    Verify deploy_requires_save capabilities reject deploy=true with save=false.

    ## Raises

    None
    """
    capability = ConfigDeployCapability(
        supports_save=True,
        deploy_requires_save=True,
        default_save=False,
        default_deploy=False,
    )
    with pytest.raises(ValueError, match="config_actions.deploy=true requires config_actions.save=true"):
        resolve_config_deploy_plan(
            capability=capability,
            params={"state": "merged", "config_actions": {"save": False, "deploy": True}},
            raw_args={"config_actions": {"save": False, "deploy": True}},
        )


def test_config_actions_resolver_00320_item_deploy_requires_resource_scope_when_enabled() -> None:
    """
    # Summary

    Verify modules can restrict per-item deploy overrides to resource-scoped deploy.

    ## Raises

    None
    """
    capability = ConfigDeployCapability(
        deploy_types=("switch", "resource"),
        item_deploy_requires_resource_type=True,
    )

    with pytest.raises(ValueError, match=r"config\[0\]\.deploy is allowed only when config_actions.type='resource'"):
        resolve_config_deploy_plan(
            capability=capability,
            params={
                "state": "merged",
                "config_actions": {"type": "switch"},
                "config": [{"name": "BLUE", "deploy": True}],
            },
            raw_args={
                "config_actions": {"type": "switch"},
                "config": [{"name": "BLUE", "deploy": True}],
            },
        )

    plan = resolve_config_deploy_plan(
        capability=capability,
        params={
            "state": "merged",
            "config_actions": {"type": "resource"},
            "config": [{"name": "BLUE", "deploy": False}],
        },
        raw_args={
            "config_actions": {"type": "resource"},
            "config": [{"name": "BLUE", "deploy": False}],
        },
    )
    assert plan.item_deploy_enabled({"name": "BLUE", "deploy": False}) is False

    plan = resolve_config_deploy_plan(
        capability=capability,
        params={
            "state": "merged",
            "config_actions": {"type": "switch"},
            "config": [{"name": "BLUE", "deploy": True}],
        },
        raw_args={"config_actions": {"type": "switch"}, "config": [{"name": "BLUE"}]},
    )
    assert plan.deploy is True
    assert plan.deploy_type == "switch"


def test_config_actions_resolver_00400_gathered_ignores_defaults_but_rejects_explicit_writes() -> None:
    """
    # Summary

    Verify read-only states are not broken by argspec defaults, while explicit write intent still fails.

    ## Raises

    None
    """
    capability = ConfigDeployCapability(supports_save=True, default_save=True, default_deploy=True)
    plan = resolve_config_deploy_plan(
        capability=capability,
        params={"state": "gathered", "config_actions": {"save": True, "deploy": True}, "config": [{"name": "filter"}]},
        raw_args={},
    )
    assert plan.save is False
    assert plan.deploy is False
    assert plan.deploy_type == "switch"

    with pytest.raises(ValueError, match="not allowed for state='gathered'"):
        resolve_config_deploy_plan(
            capability=capability,
            params={"state": "gathered", "config_actions": {"save": True, "deploy": True}},
            raw_args={"config_actions": {"deploy": True}},
        )

    with pytest.raises(ValueError, match=r"config\[0\]\.deploy=true is not allowed"):
        resolve_config_deploy_plan(
            capability=capability,
            params={"state": "gathered", "config_actions": {"save": True, "deploy": True}, "config": [{"name": "filter", "deploy": True}]},
            raw_args={"config": [{"name": "filter", "deploy": True}]},
        )
