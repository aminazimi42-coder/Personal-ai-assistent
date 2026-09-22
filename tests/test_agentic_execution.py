"""
tests/test_agentic_execution.py
Tests for agentic task execution: action registry, approval gates,
failure recovery, idempotency, authorization, audit logging.
"""

import pytest
from services.agentic_execution import (
    execute_action, get_action_registry, is_action_allowed,
    requires_approval, ActionStatus, ActionResult,
)


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
