"""
tests/test_tool_gateway.py
Tests for the AI Tool Gateway: registration, policy enforcement,
approval gates, audit logging, safe failure.
"""

import pytest
from services.tool_gateway import (
    call_tool, register_tool, get_tool_registry, is_tool_registered,
    ToolPolicy, ToolCallResult,
)


def test_tool_registry_has_default_tools():
    registry = get_tool_registry()
    assert "list_tasks" in registry
    assert "delete_task" in registry
    assert "ai_reply" in registry

def test_is_tool_registered_known():
    assert is_tool_registered("list_tasks") is True

def test_is_tool_registered_unknown():
    assert is_tool_registered("unknown_tool") is False

def test_call_read_only_tool():
    result = call_tool("list_tasks", 1, {})
    assert result.allowed is True
    assert result.error is None

def test_call_write_tool():
    result = call_tool("create_task", 1, {"title": "test"})
    assert result.allowed is True

def test_call_destructive_without_approval():
    result = call_tool("delete_task", 1, {"task_id": 1})
    assert result.allowed is False
    assert "approval" in result.error.lower()

def test_call_destructive_with_approval():
    result = call_tool("delete_task", 1, {"task_id": 1}, approved=True)
    assert result.allowed is True

def test_call_unregistered_tool():
    result = call_tool("unknown", 1, {})
    assert result.allowed is False
    assert "not registered" in result.error.lower()

def test_call_tool_with_handler():
    def handler(user_id, **params):
        return {"user": user_id, **params}
    register_tool("custom_tool", ToolPolicy.READ_ONLY, "Custom", handler=handler)
    result = call_tool("custom_tool", 1, {"x": "y"})
    assert result.allowed is True
    assert result.result["x"] == "y"

def test_call_tool_handler_failure():
    def failing_handler(user_id, **params):
        raise ValueError("handler error")
    register_tool("failing_tool", ToolPolicy.READ_ONLY, "Failing", handler=failing_handler)
    result = call_tool("failing_tool", 1, {})
    assert result.error == "handler error"

def test_tool_call_has_call_id():
    r1 = call_tool("list_tasks", 1, {})
    r2 = call_tool("list_tasks", 1, {})
    assert r1.call_id != r2.call_id

def test_tool_result_to_dict():
    result = call_tool("list_tasks", 1, {})
    d = result.to_dict()
    assert "call_id" in d
    assert "tool_name" in d
    assert "allowed" in d

def test_register_custom_tool():
    register_tool("my_tool", ToolPolicy.READ_ONLY, "My custom tool")
    assert is_tool_registered("my_tool") is True

def test_communication_tool_policy():
    """Communication tools may not require approval by default."""
    result = call_tool("ai_reply", 1, {})
    assert result.allowed is True

def test_tool_policies_exist():
    assert ToolPolicy.READ_ONLY.value == "read_only"
    assert ToolPolicy.WRITE.value == "write"
    assert ToolPolicy.DESTRUCTIVE.value == "destructive"
    assert ToolPolicy.COMMUNICATION.value == "communication"
