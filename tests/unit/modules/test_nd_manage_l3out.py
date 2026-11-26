# Copyright: (c) 2026, Cisco Systems, Inc.
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Focused attachment lifecycle tests for nd_manage_l3out."""

from types import SimpleNamespace

import pytest

from ansible_collections.cisco.nd.plugins.module_utils.models.l3out.l3out import (
    L3OutModel,
)
from ansible_collections.cisco.nd.plugins.modules.nd_manage_l3out import (
    _attachment_requests,
    _handle_attachments,
)


def _state(before, proposed, effects=None, action=None):
    orchestrator = SimpleNamespace(
        attachment_effects=effects or {},
        attach_l3outs=action or (lambda requests: {"results": requests}),
    )
    return SimpleNamespace(
        before=[L3OutModel(**item) for item in before],
        proposed=[L3OutModel(**item) for item in proposed],
        model_orchestrator=orchestrator,
    )


def test_attachment_requests_use_observed_and_in_run_state() -> None:
    state = _state(
        before=[
            {"name": "same", "attach": True},
            {"name": "detach", "attach": True},
            {"name": "restored", "attach": True},
        ],
        proposed=[
            {"name": "same", "attach": True},
            {"name": "detach", "attach": False},
            {"name": "new-false", "attach": False},
            {"name": "new-true", "attach": True},
            {"name": "restored", "attach": True},
        ],
        effects={"restored": True},
    )

    assert _attachment_requests(state) == [
        {"name": "detach", "attach": False},
        {"name": "new-true", "attach": True},
    ]


def test_attachment_failure_is_fatal() -> None:
    def fail(_requests):
        raise RuntimeError("attachment rejected")

    state = _state(
        before=[{"name": "one", "attach": False}],
        proposed=[{"name": "one", "attach": True}],
        action=fail,
    )

    with pytest.raises(RuntimeError, match="attachment rejected"):
        _handle_attachments(state, check_mode=False)


def test_attachment_check_mode_reports_only_real_transition() -> None:
    state = _state(
        before=[{"name": "one", "attach": False}],
        proposed=[{"name": "one", "attach": True}],
    )

    assert _handle_attachments(state, check_mode=True) == {
        "attachment_changed": True,
        "attachment_results": [{"name": "one", "attach": True}],
    }
