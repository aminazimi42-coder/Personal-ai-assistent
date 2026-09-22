"""
tests/test_cost_intelligence.py
Tests for cost & token intelligence: model routing, budgets, caching, estimates.
"""

import pytest
from services.cost_intelligence import (
    estimate_cost, select_model, compute_token_budget,
    cache_key, get_cached_response, set_cached_response,
    clear_cache, get_cache_size,
    record_monthly_cost, get_monthly_cost,
)


def test_estimate_cost():
    est = estimate_cost("gpt-4o-mini", 1000, 500)
    assert est.input_tokens == 1000
    assert est.output_tokens == 500
    assert est.total_cost_usd > 0

def test_estimate_cost_unknown_model():
    est = estimate_cost("unknown-model", 100, 100)
    assert est.total_cost_usd > 0

def test_select_model_simple():
    assert select_model("simple") == "gpt-4o-mini"

def test_select_model_complex():
    assert select_model("complex") == "gpt-4o"

def test_select_model_default():
    model = select_model("unknown")
    assert len(model) > 0

def test_compute_token_budget():
    budget = compute_token_budget(8000, 1024)
    assert budget == 6976

def test_compute_token_budget_zero():
    budget = compute_token_budget(0, 1024)
    assert budget == 0

def test_cache_key_unique():
    k1 = cache_key("model", [{"role": "user", "content": "hello"}])
    k2 = cache_key("model", [{"role": "user", "content": "world"}])
    assert k1 != k2

def test_cache_set_and_get():
    clear_cache()
    key = "test_key_123"
    set_cached_response(key, {"reply": "hello"}, ttl_seconds=60)
    result = get_cached_response(key)
    assert result == {"reply": "hello"}

def test_cache_miss():
    result = get_cached_response("nonexistent_key")
    assert result is None

def test_cache_expiry():
    clear_cache()
    key = "expiry_test"
    set_cached_response(key, {"data": "x"}, ttl_seconds=0)
    # TTL=0 means it expires immediately
    result = get_cached_response(key)
    assert result is None

def test_clear_cache():
    set_cached_response("a", {"x": 1})
    set_cached_response("b", {"y": 2})
    count = clear_cache()
    assert count >= 2
    assert get_cache_size() == 0

def test_monthly_cost():
    record_monthly_cost(1, 0.001)
    record_monthly_cost(1, 0.002)
    total = get_monthly_cost(1)
    assert total == pytest.approx(0.003, abs=0.0001)

def test_monthly_cost_different_users():
    record_monthly_cost(10, 0.01)
    record_monthly_cost(20, 0.02)
    assert get_monthly_cost(10) != get_monthly_cost(20)

def test_cost_estimate_has_breakdown():
    est = estimate_cost("gpt-4o-mini", 2000, 1000)
    assert est.input_cost_usd > 0
    assert est.output_cost_usd > 0
    assert est.total_cost_usd == pytest.approx(
        est.input_cost_usd + est.output_cost_usd
    )
