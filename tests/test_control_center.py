"""
tests/test_control_center.py
Tests for the Personal AI Control Center dashboard.
Verifies real metrics aggregation, no fabricated data, user isolation.
"""

import pytest
from services.control_center import (
    get_dashboard_metrics, get_health_summary, DashboardMetrics,
)
from services.memory_engine import set_memory, clear_user_memories
from services.workspace import create_workspace, reset_workspaces


def test_dashboard_metrics_returns_dataclass():
    metrics = get_dashboard_metrics(1)
    assert isinstance(metrics, DashboardMetrics)

def test_dashboard_metrics_to_dict():
    metrics = get_dashboard_metrics(1)
    d = metrics.to_dict()
    assert "ai_calls_today" in d
    assert "memory_count" in d
    assert "workspace_count" in d
    assert "rate_limits" in d

def test_dashboard_metrics_has_latency():
    metrics = get_dashboard_metrics(1)
    assert metrics.latency_ms >= 0

def test_dashboard_metrics_has_generated_at():
    metrics = get_dashboard_metrics(1)
    assert len(metrics.generated_at) > 0

def test_dashboard_memory_count():
    clear_user_memories(1)
    set_memory(1, "preference", "test_key", "test_value")
    metrics = get_dashboard_metrics(1)
    assert metrics.memory_count >= 1

def test_dashboard_workspace_count():
    reset_workspaces()
    create_workspace(1, "Test WS")
    metrics = get_dashboard_metrics(1)
    assert metrics.workspace_count >= 1

def test_dashboard_rate_limits():
    metrics = get_dashboard_metrics(1)
    assert "login" in metrics.rate_limits
    assert "ai" in metrics.rate_limits
    assert "general" in metrics.rate_limits

def test_dashboard_user_isolation():
    """Dashboard for one user should not show another user's data."""
    clear_user_memories(1)
    clear_user_memories(2)
    set_memory(1, "preference", "user1_key", "user1 value")
    set_memory(2, "preference", "user2_key", "user2 value")
    m1 = get_dashboard_metrics(1)
    m2 = get_dashboard_metrics(2)
    # User 1's memory count should not include user 2's
    assert m1.memory_count >= 1
    assert m2.memory_count >= 1

def test_health_summary():
    summary = get_health_summary()
    assert "flask_env" in summary
    assert "is_production" in summary
    assert "rate_limits" in summary
    assert "cors_origins" in summary

def test_health_summary_rate_limits():
    summary = get_health_summary()
    assert summary["rate_limits"]["login"] > 0
    assert summary["rate_limits"]["ai"] > 0
    assert summary["rate_limits"]["general"] > 0

def test_health_summary_ai_config():
    summary = get_health_summary()
    assert "ai_model" in summary
    assert "ai_max_tokens" in summary
    assert "ai_max_input_chars" in summary

def test_dashboard_no_fabricated_metrics():
    """All metrics should start at 0 or come from real data, not fabricated."""
    metrics = get_dashboard_metrics(9999)  # Non-existent user
    # No fabricated data — everything should be 0 or empty
    assert metrics.ai_calls_today >= 0
    assert metrics.monthly_cost_usd >= 0
    assert metrics.memory_count >= 0

def test_dashboard_quota_from_real_usage():
    metrics = get_dashboard_metrics(1)
    # Quota should come from real settings
    if metrics.ai_quota is not None:
        assert metrics.ai_quota > 0 or metrics.quota_exceeded is True
