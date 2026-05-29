# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>

# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Unit tests for VRF workflow result aggregation.
"""

from __future__ import absolute_import, annotations, division, print_function

__metaclass__ = type  # pylint: disable=invalid-name

from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.vrf_workflow_coordinator import (
    VrfWorkflowCoordinator,
)
from ansible_collections.cisco.nd.plugins.module_utils.models.manage_vrfs.config_models import (
    VrfParentConfigModel,
)
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.vrf_fabric_resolver import (
    VrfFabricResolver,
)


class _Module:
    def __init__(self, params):
        self.params = params
        self.check_mode = False
        self._verbosity = 3

    def fail_json(self, **kwargs):
        raise AssertionError(kwargs)


class _ParentStrategy:
    config_model_cls = VrfParentConfigModel
    fabric_data = {"members": [{"fabricName": "AK-VXLAN"}]}

    def child_fabric_members(self):
        return ["AK-VXLAN"]

    def build_child_task_args(self, child_fabric_name, vrf_configs, state):
        return {
            "fabric": child_fabric_name,
            "state": state,
            "config": vrf_configs,
        }


class _ChildStrategy:
    fabric_type = "multisite_child"


def test_vrf_workflow_coordinator_00010_parent_child_results_keep_state_machine_shape():
    """
    # Summary

    Verify MSD/MCFG parent aggregation preserves the standalone-style
    state-machine result fields under parent_fabric and child_fabrics.
    """
    coordinator = VrfWorkflowCoordinator.__new__(VrfWorkflowCoordinator)
    parent_result = {
        "changed": False,
        "output_level": "debug",
        "before": [],
        "after": [{"vrf_name": "ansible-msd-vrf"}],
        "diff": [],
        "api_paths": ["/api/v1/manage/fabrics/msd_p/vrfs"],
        "api_verbs": ["GET"],
        "api_payload": [None],
        "api_response": [{"RETURN_CODE": 200}],
        "api_result": [{"success": True}],
        "api_diff": [],
        "api_metadata": [{}],
    }
    child_result = {
        "child_fabric": "AK-VXLAN",
        "fabric_type": "multisite_child",
        "changed": True,
        "output_level": "debug",
        "before": [],
        "after": [{"vrf_name": "ansible-msd-vrf"}],
        "diff": [],
        "api_paths": ["/api/v1/manage/fabrics/AK-VXLAN/vrfs/ansible-msd-vrf"],
        "api_verbs": ["PUT"],
        "api_payload": [{"vrfName": "ansible-msd-vrf"}],
        "api_response": [{"RETURN_CODE": 204}],
        "api_result": [{"success": True, "changed": True}],
        "api_diff": [],
        "api_metadata": [{}],
    }

    result = coordinator._build_structured_result(
        parent_result,
        [child_result],
        "msd_p",
        "multisite_parent",
        "multisite",
    )

    assert result["changed"] is True
    assert result["fabric_type"] == "multisite_parent"
    assert result["workflow"] == "Multisite Parent with Child Fabric Processing"

    parent = result["parent_fabric"]
    assert parent["fabric"] == "msd_p"
    assert parent["fabric_type"] == "multisite_parent"
    assert parent["after"] == parent_result["after"]
    assert parent["api_paths"] == parent_result["api_paths"]
    assert parent["api_response"] == parent_result["api_response"]
    assert "child_fabric" not in parent

    child = result["child_fabrics"][0]
    assert child["fabric"] == "AK-VXLAN"
    assert child["fabric_type"] == "multisite_child"
    assert child["after"] == child_result["after"]
    assert child["api_paths"] == child_result["api_paths"]
    assert child["api_payload"] == child_result["api_payload"]
    assert "child_fabric" not in child


def test_vrf_workflow_coordinator_00020_parent_deploy_deferred_after_child_tasks(monkeypatch):
    """
    # Summary

    Verify parent attach/deploy fields stay on the parent task, are stripped
    from child tasks, and the parent deploy runs after child processing.
    """
    module_args = {
        "fabric": "msd_p",
        "state": "merged",
        "output_level": "debug",
        "config": [
            {
                "vrf_name": "ansible-msd-vrf",
                "deploy": True,
                "attach": [{"ip_address": "192.168.1.224"}],
                "child_fabric_config": [
                    {
                        "fabric": "AK-VXLAN",
                        "adv_default_routes": False,
                    }
                ],
            }
        ],
    }
    coordinator = VrfWorkflowCoordinator(
        module=_Module(dict(module_args)),
        strategy=_ParentStrategy(),
    )
    call_order = []

    monkeypatch.setattr(
        VrfFabricResolver,
        "strategy_from_fabric_details",
        staticmethod(lambda _name, _data: _ChildStrategy()),
    )

    def run_parent(args, defer_deploy=False):
        call_order.append("parent")
        parent_vrf = args["config"][0]
        assert defer_deploy is True
        assert parent_vrf["attach"] == [{"ip_address": "192.168.1.224"}]
        assert parent_vrf["deploy"] is True
        assert "child_fabric_config" not in parent_vrf
        return {
            "changed": True,
            "output_level": "debug",
            "before": [],
            "after": [],
            "diff": [],
            "_deferred_deploy_payload": {
                "vrfNames": ["ansible-msd-vrf"],
                "switchIds": ["SERIAL1"],
            },
        }

    def run_child(child_task):
        call_order.append("child")
        child_vrf = child_task["module_args"]["config"][0]
        assert "attach" not in child_vrf
        assert "deploy" not in child_vrf
        assert child_vrf["vrf_name"] == "ansible-msd-vrf"
        assert child_vrf["adv_default_routes"] is False
        return {
            "changed": False,
            "output_level": "debug",
            "before": [],
            "after": [],
            "diff": [],
            "fabric_type": "multisite_child",
        }

    def deploy_parent(_args, _strategy, payload):
        call_order.append("deploy")
        assert payload == {
            "vrfNames": ["ansible-msd-vrf"],
            "switchIds": ["SERIAL1"],
        }
        return {}

    monkeypatch.setattr(coordinator, "_run_state_machine_with_attachments", run_parent)
    monkeypatch.setattr(coordinator, "_run_child_task", run_child)
    monkeypatch.setattr(coordinator, "_deploy_vrf_attachments", deploy_parent)

    result = coordinator._handle_parent_workflow(dict(module_args), "multisite_parent")

    assert call_order == ["parent", "child", "deploy"]
    assert result["changed"] is True
    assert result["fabric_type"] == "multisite_parent"
    assert result["parent_fabric"]["fabric_type"] == "multisite_parent"
    assert result["child_fabrics"][0]["fabric_type"] == "multisite_child"


def test_vrf_workflow_coordinator_00030_build_pending_vrf_deploy_payload():
    """
    # Summary

    Verify deploy=true can deploy an already-pending VRF even when no fresh
    attachment payload was generated during the current task.
    """
    coordinator = VrfWorkflowCoordinator.__new__(VrfWorkflowCoordinator)
    coordinator._current_attachment_details = lambda *_args, **_kwargs: [
        {
            "vrfName": "ansible-msd-vrf",
            "switchId": "SERIAL1",
            "attach": False,
        }
    ]
    payloads = coordinator._build_pending_vrf_deploy_payloads(
        {
            "after": [
                {
                    "vrf_name": "ansible-msd-vrf",
                    "vrf_status": "pending",
                },
                {
                    "vrf_name": "ansible-no-deploy",
                    "vrf_status": "pending",
                },
                {
                    "vrf_name": "ansible-deployed",
                    "vrf_status": "deployed",
                },
            ]
        },
        [
            {"vrf_name": "ansible-msd-vrf", "deploy": True},
            {"vrf_name": "ansible-no-deploy", "deploy": False},
            {"vrf_name": "ansible-deployed", "deploy": True},
        ],
        {"config": []},
        _ParentStrategy(),
    )

    assert payloads == [
        {
            "switchIds": ["SERIAL1"],
            "vrfNames": ["ansible-msd-vrf"],
        }
    ]


def test_vrf_workflow_coordinator_00040_build_vrf_level_deploy_payload():
    """
    # Summary

    Verify deploy_type=vrf omits switchIds even when attachment changes
    provide affected switch IDs.
    """
    coordinator = VrfWorkflowCoordinator.__new__(VrfWorkflowCoordinator)
    payloads = coordinator._build_deploy_payloads(
        [
            {"vrf_name": "ansible-switch-scope", "deploy_type": "switch"},
            {"vrf_name": "ansible-vrf-scope", "deploy_type": "vrf"},
        ],
        {
            "ansible-switch-scope": {"SERIAL1"},
            "ansible-vrf-scope": {"SERIAL2"},
        },
    )

    assert payloads == [
        {
            "switchIds": ["SERIAL1"],
            "vrfNames": ["ansible-switch-scope"],
        },
        {
            "vrfNames": ["ansible-vrf-scope"],
        },
    ]


def test_vrf_workflow_coordinator_00050_deleted_ignores_child_fabric_config(monkeypatch):
    """
    # Summary

    Verify state=deleted strips child_fabric_config and does not create or
    execute child fabric tasks.
    """
    module_args = {
        "fabric": "msd_p",
        "state": "deleted",
        "output_level": "debug",
        "config": [
            {
                "vrf_name": "ansible-msd-vrf",
                "child_fabric_config": [{"fabric": "not-a-member"}],
            }
        ],
    }
    coordinator = VrfWorkflowCoordinator(
        module=_Module(dict(module_args)),
        strategy=_ParentStrategy(),
    )
    calls = []

    def run_parent(args, defer_deploy=False):
        calls.append("parent")
        assert defer_deploy is True
        parent_vrf = args["config"][0]
        assert parent_vrf["vrf_name"] == "ansible-msd-vrf"
        assert "child_fabric_config" not in parent_vrf
        assert "not-a-member" not in parent_vrf.values()
        return {
            "changed": True,
            "output_level": "debug",
            "before": [],
            "after": [],
            "diff": [],
        }

    def fail_child(_child_task):
        raise AssertionError("deleted state must not execute child tasks")

    monkeypatch.setattr(coordinator, "_run_state_machine_with_attachments", run_parent)
    monkeypatch.setattr(coordinator, "_run_child_task", fail_child)

    result = coordinator._handle_parent_workflow(dict(module_args), "multisite_parent")

    assert calls == ["parent"]
    assert result["changed"] is True
    assert result["workflow"] == "Multisite Parent without Child Fabric Processing"
