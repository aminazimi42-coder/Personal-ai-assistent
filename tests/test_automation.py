"""
tests/test_automation.py
Tests for personal automation: scheduling, idempotency, limits, audit.
"""

import pytest
from services.automation import (
    create_automation, get_automation, list_automations, delete_automation,
    execute_automation, get_execution_log, reset_automations, TriggerType,
)


def test_create_automation():
    reset_automations()
    auto = create_automation(1, "Daily Summary", TriggerType.DAILY)
    assert auto.user_id == 1
    assert auto.name == "Daily Summary"
    assert auto.id is not None

def test_create_automation_empty_name():
    with pytest.raises(ValueError):
        create_automation(1, "", TriggerType.DAILY)

def test_get_automation():
    reset_automations()
    auto = create_automation(1, "Test")
    retrieved = get_automation(auto.id, 1)
    assert retrieved is not None
    assert retrieved.name == "Test"

def test_get_automation_wrong_user():
    reset_automations()
    auto = create_automation(1, "Test")
    assert get_automation(auto.id, 2) is None

def test_list_automations():
    reset_automations()
    create_automation(1, "A1")
    create_automation(1, "A2")
    create_automation(2, "Other")
    autos = list_automations(1)
    assert len(autos) == 2
    assert all(a.user_id == 1 for a in autos)

def test_delete_automation():
    reset_automations()
    auto = create_automation(1, "ToDelete")
    assert delete_automation(auto.id, 1) is True
    assert get_automation(auto.id, 1) is None

def test_delete_automation_wrong_user():
    reset_automations()
    auto = create_automation(1, "Test")
    assert delete_automation(auto.id, 2) is False

def test_execute_automation():
    reset_automations()
    auto = create_automation(1, "Test")
    result = execute_automation(auto.id, 1)
    assert result["status"] == "completed"
    assert result["executed"] is True

def test_execute_automation_with_executor():
    reset_automations()
    auto = create_automation(1, "Test")
    def executor(user_id):
        return {"summary": "test done"}
    result = execute_automation(auto.id, 1, executor=executor)
    assert result["status"] == "completed"
    assert result["result"]["summary"] == "test done"

def test_execute_automation_daily_limit():
    reset_automations()
    auto = create_automation(1, "Test", TriggerType.DAILY, max_daily_executions=2)
    r1 = execute_automation(auto.id, 1)
    r2 = execute_automation(auto.id, 1)
    r3 = execute_automation(auto.id, 1)
    assert r1["status"] == "completed"
    assert r2["status"] == "completed"
    assert r3["status"] == "limit_exceeded"

def test_execute_automation_unknown_id():
    result = execute_automation("nonexistent", 1)
    assert result["status"] == "denied"

def test_execute_automation_disabled():
    reset_automations()
    auto = create_automation(1, "Test")
    auto.enabled = False
    result = execute_automation(auto.id, 1)
    assert result["status"] == "disabled"

def test_execution_log():
    reset_automations()
    auto = create_automation(1, "Test")
    execute_automation(auto.id, 1)
    log = get_execution_log(1)
    assert len(log) >= 1
    assert log[0]["status"] == "completed"

def test_execution_log_user_isolation():
    reset_automations()
    auto1 = create_automation(1, "User1")
    auto2 = create_automation(2, "User2")
    execute_automation(auto1.id, 1)
    execute_automation(auto2.id, 2)
    log1 = get_execution_log(1)
    log2 = get_execution_log(2)
    assert all(e["user_id"] == 1 for e in log1)
    assert all(e["user_id"] == 2 for e in log2)
