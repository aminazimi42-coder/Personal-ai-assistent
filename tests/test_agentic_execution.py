"""
tests/test_agentic_execution.py
Tests for agentic task execution: action registry, approval gates,
failure recovery, idempotency, authorization, audit logging,
DB-backed persistence, state machine, cancellation, retries, user isolation.
"""

import pytest
from services.agentic_execution import (
    execute_action, get_action_registry, is_action_allowed,
    requires_approval, ActionStatus, ActionResult,
    cancel_action, get_agent_run, list_agent_runs, retry_action,
    approve_action, reset_runs_store,
)


@pytest.fixture(autouse=True)
def _reset():
    """Reset in-memory stores before each test."""
    reset_runs_store()
    yield
    reset_runs_store()


# ------------------------------------------------------------------ #
# Registry tests
# ------------------------------------------------------------------ #

def test_action_registry_has_actions():
    """Registry must contain known actions."""
    registry = get_action_registry()
    assert "create_task" in registry
    assert "delete_task" in registry
    assert "send_ai_reply" in registry


def test_is_action_allowed_known():
    assert is_action_allowed("create_task") is True


def test_is_action_allowed_unknown():
    assert is_action_allowed("unknown_action") is False


def test_requires_approval_destructive():
    assert requires_approval("delete_task") is True


def test_requires_approval_write():
    assert requires_approval("create_task") is False


def test_requires_approval_unknown_action():
    """Unknown actions should require approval by default."""
    assert requires_approval("unknown_action") is True


# ------------------------------------------------------------------ #
# Execution tests (in-memory, no DB)
# ------------------------------------------------------------------ #

def test_execute_action_without_approval_for_write():
    """Write actions should execute without approval."""
    result = execute_action("create_task", 1, {"title": "test"})
    assert result.status == ActionStatus.COMPLETED
    assert result.error is None


def test_execute_action_destructive_without_approval():
    """Destructive actions should be pending without approval."""
    result = execute_action("delete_task", 1, {"task_id": 1})
    assert result.status == ActionStatus.PENDING
    assert "approval" in result.error.lower()


def test_execute_action_destructive_with_approval():
    """Destructive actions with approval should complete."""
    result = execute_action("delete_task", 1, {"task_id": 1}, approved=True)
    assert result.status == ActionStatus.COMPLETED


def test_execute_action_unknown_denied():
    """Unknown actions should be denied."""
    result = execute_action("unknown", 1, {})
    assert result.status == ActionStatus.DENIED
    assert "Unknown" in result.error


def test_execute_action_with_executor():
    """Executor callable should be called and result returned."""
    def my_executor(user_id, **params):
        return {"user_id": user_id, "created": True, **params}

    result = execute_action("create_task", 42, {"title": "test"}, executor=my_executor)
    assert result.status == ActionStatus.COMPLETED
    assert result.result["user_id"] == 42
    assert result.result["created"] is True


def test_execute_action_executor_failure():
    """Executor failure should result in FAILED status, not crash."""
    def failing_executor(user_id, **params):
        raise ValueError("Something went wrong")

    result = execute_action("create_task", 1, {}, executor=failing_executor)
    assert result.status == ActionStatus.FAILED
    assert "Something went wrong" in result.error


def test_action_result_has_duration():
    """Action result should have a duration."""
    result = execute_action("create_task", 1, {})
    assert result.duration_ms >= 0


def test_action_result_has_action_id():
    """Each action should have a unique ID."""
    r1 = execute_action("create_task", 1, {})
    r2 = execute_action("create_task", 1, {})
    assert r1.action_id != r2.action_id


def test_action_result_to_dict():
    """ActionResult should serialize to dict."""
    result = execute_action("create_task", 1, {})
    d = result.to_dict()
    assert "action_id" in d
    assert "status" in d
    assert "user_id" in d
    assert d["user_id"] == 1


def test_read_only_actions():
    """Read-only actions should not require approval."""
    result = execute_action("search_memory", 1, {"query": "test"})
    assert result.status == ActionStatus.COMPLETED


def test_all_statuses_exist():
    """All expected action statuses should exist."""
    assert ActionStatus.PENDING.value == "pending"
    assert ActionStatus.APPROVED.value == "approved"
    assert ActionStatus.EXECUTING.value == "executing"
    assert ActionStatus.COMPLETED.value == "completed"
    assert ActionStatus.FAILED.value == "failed"
    assert ActionStatus.DENIED.value == "denied"
    assert ActionStatus.CANCELED.value == "canceled"


# ------------------------------------------------------------------ #
# Persistence tests (in-memory store)
# ------------------------------------------------------------------ #

def test_persisted_run_retrievable():
    """A completed action should be retrievable via get_agent_run."""
    result = execute_action("create_task", 1, {"title": "test"})
    run = get_agent_run(result.action_id, 1)
    assert run is not None
    assert run["action_id"] == result.action_id
    assert run["status"] == "completed"


def test_list_agent_runs():
    """list_agent_runs should return user's runs."""
    execute_action("create_task", 1, {})
    execute_action("search_memory", 1, {})
    runs = list_agent_runs(1)
    assert len(runs) >= 2


def test_list_agent_runs_with_limit():
    """list_agent_runs should respect limit."""
    for _ in range(5):
        execute_action("create_task", 1, {})
    runs = list_agent_runs(1, limit=3)
    assert len(runs) <= 3


# ------------------------------------------------------------------ #
# Idempotency tests
# ------------------------------------------------------------------ #

def test_idempotency_completed_returns_existing():
    """Re-executing with same action_id and COMPLETED status returns existing."""
    result1 = execute_action("create_task", 1, {}, action_id="test-id-1")
    assert result1.status == ActionStatus.COMPLETED
    result2 = execute_action("create_task", 1, {}, action_id="test-id-1")
    assert result2.status == ActionStatus.COMPLETED
    assert result1.action_id == result2.action_id


def test_idempotency_with_executor():
    """Idempotency should work with custom executors."""
    call_count = [0]

    def counting_executor(user_id, **params):
        call_count[0] += 1
        return {"count": call_count[0]}

    r1 = execute_action("create_task", 1, {}, action_id="idem-1", executor=counting_executor)
    r2 = execute_action("create_task", 1, {}, action_id="idem-1", executor=counting_executor)
    assert call_count[0] == 1  # executor only called once


# ------------------------------------------------------------------ #
# Cancellation tests
# ------------------------------------------------------------------ #

def test_cancel_pending_action():
    """Canceling a pending action should succeed."""
    result = execute_action("delete_task", 1, {"task_id": 1})
    assert result.status == ActionStatus.PENDING
    canceled = cancel_action(result.action_id, 1)
    assert canceled is True
    run = get_agent_run(result.action_id, 1)
    assert run["status"] == "canceled"


def test_cancel_completed_action_fails():
    """Canceling a completed action should fail."""
    result = execute_action("create_task", 1, {})
    assert result.status == ActionStatus.COMPLETED
    canceled = cancel_action(result.action_id, 1)
    assert canceled is False


def test_cancel_nonexistent_action():
    """Canceling a non-existent action returns False."""
    canceled = cancel_action("nonexistent-id", 1)
    assert canceled is False


# ------------------------------------------------------------------ #
# Retry tests
# ------------------------------------------------------------------ #

def test_retry_failed_action():
    """Retrying a failed action should re-execute it."""
    def failing_executor(user_id, **params):
        raise ValueError("Temporary failure")

    result = execute_action("create_task", 1, {}, action_id="retry-1",
                            executor=failing_executor)
    assert result.status == ActionStatus.FAILED

    def success_executor(user_id, **params):
        return {"success": True}

    retried = retry_action("retry-1", 1, executor=success_executor)
    assert retried.status == ActionStatus.COMPLETED


def test_retry_non_failed_action():
    """Retrying a non-failed action should return error."""
    result = execute_action("create_task", 1, {}, action_id="retry-2")
    assert result.status == ActionStatus.COMPLETED
    retried = retry_action("retry-2", 1)
    assert "not in FAILED" in (retried.error or "")


def test_retry_nonexistent_action():
    """Retrying a non-existent action should return denied."""
    retried = retry_action("nonexistent-id", 1)
    assert retried.status == ActionStatus.DENIED


# ------------------------------------------------------------------ #
# Approval tests
# ------------------------------------------------------------------ #

def test_approve_pending_action():
    """Approving a pending destructive action should execute it."""
    result = execute_action("delete_task", 1, {"task_id": 5}, action_id="approve-1")
    assert result.status == ActionStatus.PENDING

    approved_result = approve_action("approve-1", 1)
    assert approved_result.status == ActionStatus.COMPLETED


def test_approve_non_pending_action():
    """Approving a non-pending action should return error."""
    result = execute_action("create_task", 1, {}, action_id="approve-2")
    assert result.status == ActionStatus.COMPLETED
    approved = approve_action("approve-2", 1)
    assert "not pending" in (approved.error or "").lower() or approved.status != ActionStatus.COMPLETED


def test_approve_nonexistent_action():
    """Approving a non-existent action should return denied."""
    result = approve_action("nonexistent-id", 1)
    assert result.status == ActionStatus.DENIED


# ------------------------------------------------------------------ #
# User isolation tests
# ------------------------------------------------------------------ #

def test_get_agent_run_user_isolation():
    """User 2 should not see user 1's runs."""
    result = execute_action("create_task", 1, {}, action_id="iso-1")
    run = get_agent_run("iso-1", 2)
    assert run is None


def test_list_agent_runs_user_isolation():
    """list_agent_runs should only return the requesting user's runs."""
    execute_action("create_task", 1, {}, action_id="iso-2")
    execute_action("create_task", 2, {}, action_id="iso-3")
    runs_1 = list_agent_runs(1)
    runs_2 = list_agent_runs(2)
    for r in runs_1:
        assert r["user_id"] == 1
    for r in runs_2:
        assert r["user_id"] == 2


def test_cancel_user_isolation():
    """User 2 should not be able to cancel user 1's action."""
    result = execute_action("delete_task", 1, {"task_id": 1}, action_id="iso-4")
    canceled = cancel_action("iso-4", 2)
    assert canceled is False


def test_retry_user_isolation():
    """User 2 should not be able to retry user 1's action."""
    result = execute_action("create_task", 1, {}, action_id="iso-5")
    retried = retry_action("iso-5", 2)
    assert retried.status == ActionStatus.DENIED


# ------------------------------------------------------------------ #
# State machine tests
# ------------------------------------------------------------------ #

def test_canceled_status_exists():
    """CANCELED status should exist in the enum."""
    assert ActionStatus.CANCELED.value == "canceled"


def test_state_transitions_pending_to_completed():
    """PENDING → (approved) → COMPLETED for write actions."""
    # Write action goes directly to COMPLETED without approval
    result = execute_action("create_task", 1, {}, action_id="state-1")
    assert result.status == ActionStatus.COMPLETED
    run = get_agent_run("state-1", 1)
    assert run["status"] == "completed"


def test_state_transitions_pending_to_denied():
    """Unknown action → DENIED."""
    result = execute_action("unknown_action", 1, {}, action_id="state-2")
    assert result.status == ActionStatus.DENIED


def test_state_pending_to_canceled():
    """PENDING → CANCELED via cancel_action."""
    result = execute_action("delete_task", 1, {"task_id": 1}, action_id="state-3")
    assert result.status == ActionStatus.PENDING
    cancel_action("state-3", 1)
    run = get_agent_run("state-3", 1)
    assert run["status"] == "canceled"


# ------------------------------------------------------------------ #
# A6: No silent simulation on live routes
# ------------------------------------------------------------------ #

def test_live_route_no_executor_does_not_simulate():
    """When get_connection_fn is provided (live route), a write action
    without an executor must NOT report COMPLETED with a simulated result.
    It must return PENDING so the caller knows a real executor is required."""
    from unittest.mock import MagicMock
    mock_conn = MagicMock()
    result = execute_action(
        "create_task", 1, {"title": "test"},
        get_connection_fn=lambda: mock_conn,
    )
    assert result.status == ActionStatus.PENDING
    assert "executor" in (result.error or "").lower()
    assert result.result is None  # no simulated result


def test_live_route_with_executor_completes():
    """When get_connection_fn is provided AND an executor is provided,
    the action should complete normally."""
    from unittest.mock import MagicMock
    mock_conn = MagicMock()
    def my_executor(user_id, **params):
        return {"done": True}
    result = execute_action(
        "create_task", 1, {"title": "test"},
        executor=my_executor,
        get_connection_fn=lambda: mock_conn,
    )
    assert result.status == ActionStatus.COMPLETED
    assert result.result == {"done": True}


def test_inmemory_simulate_still_works():
    """In-memory path (no get_connection_fn) still simulates for unit tests."""
    result = execute_action("create_task", 1, {"title": "test"})
    assert result.status == ActionStatus.COMPLETED
    assert result.result == {"simulated": True, "action": "create_task", "params": {"title": "test"}}
