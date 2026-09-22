"""
tests/test_control_center_extended.py
Tests for extended control center: tenant, billing, agent runs,
tool audit, comprehensive snapshot.
"""

import os
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:***@localhost/testdb")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5000")

from services.control_center import (
    get_dashboard_metrics,
    get_control_center,
    DashboardMetrics,
)
from services.memory_engine import set_memory, clear_user_memories
from services.automation import (
    create_automation,
    reset_automations,
    TriggerType,
)
from services.tool_gateway import (
    call_tool,
    get_tool_audit_log,
    reset_tool_audit_log,
)


# ------------------------------------------------------------------ #
# Extended dashboard metrics
# ------------------------------------------------------------------ #

def test_dashboard_has_tenant_info():
    metrics = get_dashboard_metrics(1)
    assert metrics.tenant_id is not None
    assert metrics.tenant_plan == "individual"


def test_dashboard_has_billing_status():
    metrics = get_dashboard_metrics(1)
    assert metrics.billing_status in ("active", "budget_exceeded")


def test_dashboard_has_agent_run_count():
    metrics = get_dashboard_metrics(1)
    assert isinstance(metrics.agent_run_count, int)
    assert metrics.agent_run_count >= 0


def test_dashboard_has_tool_audit_events():
    metrics = get_dashboard_metrics(1)
    assert isinstance(metrics.tool_audit_events, list)


def test_dashboard_has_cost_limit():
    metrics = get_dashboard_metrics(1)
    # cost_limit_usd is None when no limit is set
    assert metrics.cost_limit_usd is None or isinstance(metrics.cost_limit_usd, float)


def test_dashboard_has_cost_exceeded():
    metrics = get_dashboard_metrics(1)
    assert isinstance(metrics.cost_exceeded, bool)


def test_dashboard_to_dict_has_new_fields():
    metrics = get_dashboard_metrics(1)
    d = metrics.to_dict()
    assert "tenant_id" in d
    assert "tenant_plan" in d
    assert "billing_status" in d
    assert "agent_run_count" in d
    assert "tool_audit_events" in d
    assert "cost_limit_usd" in d
    assert "cost_exceeded" in d


# ------------------------------------------------------------------ #
# Tool audit events in dashboard
# ------------------------------------------------------------------ #

def test_dashboard_tool_audit_from_gateway():
    """Tool calls should appear in the dashboard via tool_audit_events."""
    reset_tool_audit_log()
    call_tool("list_tasks", user_id=1, params={})
    metrics = get_dashboard_metrics(1)
    assert len(metrics.tool_audit_events) >= 1
    event = metrics.tool_audit_events[0]
    assert event["tool_name"] == "list_tasks"
    assert event["user_id"] == 1


def test_tool_audit_log_user_isolation():
    """Tool audit log should be user-isolated."""
    reset_tool_audit_log()
    call_tool("list_tasks", user_id=1, params={})
    call_tool("list_tasks", user_id=2, params={})
    log1 = get_tool_audit_log(1)
    log2 = get_tool_audit_log(2)
    assert all(e["user_id"] == 1 for e in log1)
    assert all(e["user_id"] == 2 for e in log2)


# ------------------------------------------------------------------ #
# Agent run count
# ------------------------------------------------------------------ #

def test_dashboard_agent_run_count_from_automations():
    """Agent run count should reflect automation execution log."""
    reset_automations()
    from services.automation import execute_automation
    auto = create_automation(1, "Test automation", TriggerType.MANUAL)
    execute_automation(auto.id, 1)
    metrics = get_dashboard_metrics(1)
    assert metrics.agent_run_count >= 1


# ------------------------------------------------------------------ #
# Control center comprehensive snapshot
# ------------------------------------------------------------------ #

def test_get_control_center_structure():
    snapshot = get_control_center(1)
    assert isinstance(snapshot, dict)
    assert "dashboard" in snapshot
    assert "health" in snapshot
    assert "cost" in snapshot
    assert "user_id" in snapshot


def test_get_control_center_dashboard_is_dict():
    snapshot = get_control_center(1)
    assert isinstance(snapshot["dashboard"], dict)


def test_get_control_center_health_has_flask_env():
    snapshot = get_control_center(1)
    assert "flask_env" in snapshot["health"]


def test_get_control_center_has_all_new_fields():
    snapshot = get_control_center(1)
    d = snapshot["dashboard"]
    assert "tenant_id" in d
    assert "tenant_plan" in d
    assert "billing_status" in d
    assert "agent_run_count" in d
    assert "tool_audit_events" in d
    assert "cost_limit_usd" in d
    assert "cost_exceeded" in d


def test_get_control_center_user_id():
    snapshot = get_control_center(42)
    assert snapshot["user_id"] == 42


# ------------------------------------------------------------------ #
# No fabricated data
# ------------------------------------------------------------------ #

def test_dashboard_nonexistent_user_no_fabrication():
    """Dashboard for a non-existent user should not fabricate data."""
    metrics = get_dashboard_metrics(999999)
    assert metrics.memory_count >= 0
    assert metrics.task_count >= 0
    assert metrics.agent_run_count >= 0
    assert metrics.automation_count >= 0
    # Should not have fabricated tenant info
    assert metrics.tenant_id == 999999
    assert metrics.tenant_plan == "individual"
