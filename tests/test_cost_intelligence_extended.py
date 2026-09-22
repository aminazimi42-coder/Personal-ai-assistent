"""
tests/test_cost_intelligence_extended.py
Tests for extended cost intelligence: monthly usage, workspace budget,
cost dashboard, route_request, cache stats.
"""

import os
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:***@localhost/testdb")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5000")

from services.cost_intelligence import (
    get_monthly_usage,
    check_workspace_budget,
    get_cost_dashboard,
    route_request,
    record_cache_hit,
    record_cache_miss,
    get_cache_stats,
    reset_cache_stats,
    clear_cache,
    record_monthly_cost,
    get_monthly_cost,
)


# ------------------------------------------------------------------ #
# Monthly usage
# ------------------------------------------------------------------ #

def test_get_monthly_usage_structure():
    usage = get_monthly_usage(1)
    assert isinstance(usage, dict)
    assert "user_id" in usage
    assert "month" in usage
    assert "total_cost_usd" in usage
    assert "budget_limit_usd" in usage
    assert "budget_exceeded" in usage
    assert "budget_remaining" in usage
    assert "daily" in usage


def test_get_monthly_usage_no_cost():
    """Monthly usage with no recorded cost should be 0."""
    # Use a unique user_id to avoid interference
    usage = get_monthly_usage(99998)
    assert usage["total_cost_usd"] == 0.0
    assert usage["budget_exceeded"] is False


def test_get_monthly_usage_month_format():
    usage = get_monthly_usage(1)
    # Month should be YYYY-MM
    assert len(usage["month"]) == 7
    assert "-" in usage["month"]


# ------------------------------------------------------------------ #
# Workspace budget
# ------------------------------------------------------------------ #

def test_check_workspace_budget_no_limit():
    """With no limit set (0), budget check should pass."""
    # Default config has AI_MONTHLY_COST_LIMIT_PER_USER = 0
    result = check_workspace_budget(1, workspace_id=1)
    assert result is True


def test_check_workspace_budget_returns_bool():
    result = check_workspace_budget(1, workspace_id=1)
    assert isinstance(result, bool)


# ------------------------------------------------------------------ #
# Cost dashboard
# ------------------------------------------------------------------ #

def test_get_cost_dashboard_structure():
    dashboard = get_cost_dashboard(1)
    assert isinstance(dashboard, dict)
    assert "user_id" in dashboard
    assert "monthly" in dashboard
    assert "cache" in dashboard
    assert "model_costs" in dashboard
    assert "configured_model" in dashboard
    assert "generated_at" in dashboard


def test_get_cost_dashboard_cache_stats():
    reset_cache_stats()
    record_cache_hit()
    record_cache_hit()
    record_cache_miss()
    dashboard = get_cost_dashboard(1)
    cache = dashboard["cache"]
    assert cache["hits"] == 2
    assert cache["misses"] == 1
    assert cache["total_entries"] >= 0


def test_get_cost_dashboard_hit_rate():
    reset_cache_stats()
    record_cache_hit()
    record_cache_miss()
    dashboard = get_cost_dashboard(1)
    hit_rate = dashboard["cache"]["hit_rate"]
    assert 0 <= hit_rate <= 1
    assert hit_rate == pytest.approx(0.5, abs=0.01)


def test_get_cost_dashboard_hit_rate_zero():
    """Hit rate should be 0 when no cache activity."""
    reset_cache_stats()
    dashboard = get_cost_dashboard(1)
    assert dashboard["cache"]["hit_rate"] == 0.0


# ------------------------------------------------------------------ #
# Route request
# ------------------------------------------------------------------ #

def test_route_request_simple():
    result = route_request("simple", user_id=1)
    assert isinstance(result, dict)
    assert result["model"] == "gpt-4o-mini"
    assert result["complexity"] == "simple"
    assert "cost_estimate" in result
    assert "within_budget" in result
    assert "budget_status" in result


def test_route_request_complex():
    result = route_request("complex", user_id=1)
    assert result["model"] == "gpt-4o"


def test_route_request_cost_estimate():
    result = route_request("simple", user_id=1)
    est = result["cost_estimate"]
    assert est["input_tokens"] > 0
    assert est["output_tokens"] > 0
    assert est["total_cost_usd"] > 0


def test_route_request_within_budget_no_limit():
    """With no budget limit, within_budget should be True."""
    result = route_request("simple", user_id=1)
    assert result["within_budget"] is True
    assert result["budget_status"] == "ok"


def test_route_request_returns_dict():
    result = route_request("simple", user_id=1)
    assert isinstance(result, dict)
    assert "monthly_cost_usd" in result


# ------------------------------------------------------------------ #
# Cache stats
# ------------------------------------------------------------------ #

def test_cache_stats_record_hit():
    reset_cache_stats()
    record_cache_hit()
    stats = get_cache_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 0


def test_cache_stats_record_miss():
    reset_cache_stats()
    record_cache_miss()
    stats = get_cache_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 1


def test_cache_stats_reset():
    record_cache_hit()
    record_cache_miss()
    reset_cache_stats()
    stats = get_cache_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0
