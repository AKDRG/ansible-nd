# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Switch removal failures through the actual NDModule and response pipeline."""

# pylint: disable=protected-access
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.cisco.nd.plugins.module_utils.enums import HttpVerbEnum
from ansible_collections.cisco.nd.plugins.module_utils.manage_switches.nd_switch_resources import SwitchFabricOps, SwitchServiceContext
from ansible_collections.cisco.nd.plugins.module_utils.nd_v2 import NDModule
from ansible_collections.cisco.nd.plugins.module_utils.rest.response_handler_nd import ResponseHandler
from ansible_collections.cisco.nd.plugins.module_utils.rest.rest_send import RestSend
from ansible_collections.cisco.nd.tests.unit.module_utils.mock_ansible_module import MockAnsibleModule
from ansible_collections.cisco.nd.tests.unit.module_utils.response_generator import ResponseGenerator
from ansible_collections.cisco.nd.tests.unit.module_utils.sender_file import Sender
from ansible_collections.cisco.nd.tests.unit.module_utils.test_nd_switch_resources import _empty_plan, _resource, _sw


class ModuleFailure(SystemExit):
    """Match Ansible's non-returning failure boundary and retain the full result."""

    def __init__(self, result):
        super().__init__(1)
        self.result = result


def _fail_json(**result):
    raise ModuleFailure(result)


def _response(items, code=207):
    return {
        "RETURN_CODE": code,
        "METHOD": "POST",
        "REQUEST_PATH": "/api/v1/manage/fabrics/FAB1/switchActions/remove",
        "MESSAGE": "Multi-Status" if code == 207 else "OK",
        "DATA": {"items": items},
    }


def _item(serial, status):
    return {"switchId": serial, "status": status, "message": f"Controller result for {serial}: {status}"}


def _pipeline(items, state="deleted", check_mode=False):
    switches = [_sw("192.0.2.10", "SERIAL1"), _sw("192.0.2.11", "SERIAL2")]
    resource = _resource(state=state, check_mode=check_mode, existing=switches, output_level="debug")
    resource.module._debug = False
    resource.module.fail_json = _fail_json
    response = _response(items)

    def responses():
        yield copy.deepcopy(response)

    sender = Sender()
    sender.ansible_module = MockAnsibleModule()
    sender.gen = ResponseGenerator(responses())
    handler = ResponseHandler()
    rest = RestSend({"check_mode": check_mode, "state": state})
    rest.sender = sender
    rest.response_handler = handler
    rest.unit_test = True
    nd = NDModule(resource.module)
    nd._rest_send = rest
    nd._response_handler = handler
    resource.nd = nd
    resource.ctx = SwitchServiceContext(nd=nd, results=resource.results, fabric="FAB1", log=resource.log, save_config=True, deploy_config=True)
    resource.fabric_ops = SwitchFabricOps(resource.ctx, fabric_utils=SimpleNamespace())
    return resource, switches, rest


@pytest.mark.parametrize(
    "statuses,success,changed",
    [
        (["success", "success"], True, True),
        (["success", "failed"], False, True),
        (["failed", "failed"], False, False),
        (["success", None], False, True),
        (["warning", "unknown"], False, False),
        ([False, ""], False, False),
    ],
)
@pytest.mark.parametrize("envelope", ["items", "results", "switchIds", "links"])
def test_shared_item_classification(statuses, success, changed, envelope):
    """The added envelope uses the same failure/change/retry contract as existing ones."""
    response = _response([_item(f"SERIAL{index}", status) for index, status in enumerate(statuses, 1)])
    response["DATA"][envelope] = response["DATA"].pop("items")
    handler = ResponseHandler()
    handler.response = response
    handler.verb = HttpVerbEnum.POST
    handler.commit()
    assert handler.result == {"success": success, "changed": changed, "retryable": False}
    if not success:
        assert "SERIAL" in handler.error_message


@pytest.mark.parametrize("items", [[{"hostname": "switch-a"}], []])
def test_plain_get_items_without_status_are_not_errors(items):
    """Ordinary list GET responses remain valid and read-only."""
    handler = ResponseHandler()
    handler.response = {**_response(items, 200), "METHOD": "GET"}
    handler.verb = HttpVerbEnum.GET
    handler.commit()
    assert handler.result == {"found": True, "success": True, "retryable": False}


@pytest.mark.parametrize("state", ["deleted", "replaced", "overridden"])
@pytest.mark.parametrize("first_status,changed,deleted", [("success", True, ["SERIAL1"]), ("failed", False, [])])
def test_partial_removal_preserves_failure_output_and_stops_lifecycle(state, first_status, changed, deleted):
    """One real request records the successful subset and fails before later phases."""
    items = [_item("SERIAL1", first_status), _item("SERIAL2", "failed")]
    resource, switches, rest = _pipeline(items, state)
    with pytest.raises(ModuleFailure) as caught:
        if state == "deleted":
            resource._handle_deleted_state()
        else:
            plan = _empty_plan(**({"to_delete": switches} if state == "overridden" else {"to_delete_existing": switches}))
            getattr(resource, f"_handle_{state}_state")(plan, {})
    result = caught.value.result
    assert result["failed"] is True and result["changed"] is changed
    assert "SERIAL2" in result["msg"]
    assert resource.results.diffs[0]["deleted"] == deleted
    assert len(rest.responses) == resource.results.task_sequence_number == 1
    assert resource.results.path == ["/api/v1/manage/fabrics/FAB1/switchActions/remove"]
    assert rest.committed_payload == {"switchIds": ["SERIAL1", "SERIAL2"]}
    assert resource.results.responses[0]["DATA"]["items"] == items


def test_all_success_and_check_mode_keep_existing_removal_contract():
    """Successful deletes return targets; check mode does not contact the sender."""
    items = [_item("SERIAL1", "success"), _item("SERIAL2", "success")]
    resource, switches, rest = _pipeline(items)
    assert resource.fabric_ops.bulk_delete(switches) == ["SERIAL1", "SERIAL2"]
    assert len(rest.responses) == 1
    preview, switches, rest = _pipeline(items, check_mode=True)
    assert preview.fabric_ops.bulk_delete(switches) == []
    assert preview.results.task_sequence_number == 0


@pytest.mark.parametrize("items", [None, "invalid", [], [None], [_item("OTHER_SWITCH", "success")], [_item("SERIAL1", "success")]])
def test_incomplete_or_malformed_remove_response_cannot_claim_all_deleted(items):
    """Missing confirmations never count as successful removal of requested switches."""
    resource, switches, rest = _pipeline(items)
    with pytest.raises(ModuleFailure) as caught:
        resource.fabric_ops.bulk_delete(switches)
    assert caught.value.result["failed"] is True
    assert len(rest.responses) == 1
    assert "SERIAL2" not in resource.results.diffs[0]["deleted"]
