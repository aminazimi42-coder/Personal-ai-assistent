"""
services/cost_intelligence.py
Cost & Token Intelligence — centralize model routing, budgets, caching.

Features:
- Model routing by task complexity
- Token/context budgets
- Retrieval-aware budgets
- Usage accounting (daily/monthly)
- Cost estimates
- Caching for repeated queries
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Model pricing (per 1K tokens, USD) — approximate as of 2024
# ------------------------------------------------------------------ #
MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
}


@dataclass
class CostEstimate:
    """Cost estimate for an AI operation."""
    model: str
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> CostEstimate:
    """Estimate the cost of an AI operation."""
    pricing = MODEL_PRICING.get(model, {"input": 0.001, "output": 0.002})
    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    return CostEstimate(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost_usd=round(input_cost, 6),
        output_cost_usd=round(output_cost, 6),
        total_cost_usd=round(input_cost + output_cost, 6),
    )


def select_model(task_complexity: str = "simple") -> str:
    """
    Select a model based on task complexity.
    Do not choose solely by cheapest — consider correctness, latency.
    """
    if task_complexity == "simple":
        return "gpt-4o-mini"  # Fast, cheap, good for simple tasks
    elif task_complexity == "complex":
        return "gpt-4o"  # More capable for complex reasoning
    return settings.OPENAI_CHAT_MODEL


def compute_token_budget(
    max_context_tokens: int = 8000,
    reserved_for_output: int = 1024,
) -> int:
    """
    Compute the available input token budget.
    Leaves room for output tokens.
    """
    return max(0, max_context_tokens - reserved_for_output)


# ------------------------------------------------------------------ #
# Response cache — avoids duplicate LLM calls for identical prompts
# ------------------------------------------------------------------ #
_cache: dict[str, dict] = {}
_cache_lock = None


def _get_cache_lock():
    global _cache_lock
    if _cache_lock is None:
        import threading
        _cache_lock = threading.Lock()
    return _cache_lock


def cache_key(model: str, messages: list[dict]) -> str:
    """Generate a cache key from model + messages."""
    raw = f"{model}:{str(messages)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def get_cached_response(key: str) -> Optional[dict]:
    """Get a cached response by key. Returns None on miss."""
    with _get_cache_lock():
        entry = _cache.get(key)
        if entry and entry.get("expires_at", 0) > time.time():
            return entry.get("response")
    return None


def set_cached_response(key: str, response: dict, ttl_seconds: int = 3600) -> None:
    """Cache a response with TTL."""
    with _get_cache_lock():
        _cache[key] = {
            "response": response,
            "expires_at": time.time() + ttl_seconds,
        }


def clear_cache() -> int:
    """Clear the entire response cache. Returns count cleared."""
    with _get_cache_lock():
        count = len(_cache)
        _cache.clear()
        return count


def get_cache_size() -> int:
    """Return the number of cached entries."""
    with _get_cache_lock():
        return len(_cache)


# ------------------------------------------------------------------ #
# Monthly usage tracking (extends daily quota)
# ------------------------------------------------------------------ #
_monthly_cache: dict[int, dict[str, float]] = {}


def record_monthly_cost(user_id: int, cost_usd: float) -> float:
    """Record a cost for a user this month. Returns total monthly cost."""
    from datetime import datetime
    month_key = datetime.now().strftime("%Y-%m")
    with _get_cache_lock():
        if user_id not in _monthly_cache:
            _monthly_cache[user_id] = {}
        _monthly_cache[user_id][month_key] = (
            _monthly_cache[user_id].get(month_key, 0) + cost_usd
        )
        return _monthly_cache[user_id][month_key]


def get_monthly_cost(user_id: int) -> float:
    """Get total cost for a user this month."""
    from datetime import datetime
    month_key = datetime.now().strftime("%Y-%m")
    with _get_cache_lock():
        return _monthly_cache.get(user_id, {}).get(month_key, 0.0)


# ------------------------------------------------------------------ #
# Extended cost intelligence: monthly usage, budgets, routing, dashboard
# ------------------------------------------------------------------ #
# Cache hit/miss tracking
_cache_stats: dict[str, int] = {"hits": 0, "misses": 0}


def record_cache_hit() -> None:
    """Record a cache hit."""
    with _get_cache_lock():
        _cache_stats["hits"] += 1


def record_cache_miss() -> None:
    """Record a cache miss."""
    with _get_cache_lock():
        _cache_stats["misses"] += 1


def get_cache_stats() -> dict[str, int]:
    """Return cache hit/miss statistics."""
    with _get_cache_lock():
        return dict(_cache_stats)


def reset_cache_stats() -> None:
    """Reset cache statistics (for tests)."""
    with _get_cache_lock():
        _cache_stats["hits"] = 0
        _cache_stats["misses"] = 0


def get_monthly_usage(user_id: int, get_connection=None) -> dict:
    """
    Aggregate monthly cost breakdown for a user.

    Returns a dict with month, total cost, daily breakdown,
    and budget limit status.
    """
    from datetime import datetime, timezone

    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    total = get_monthly_cost(user_id)
    limit = settings.AI_MONTHLY_COST_LIMIT_PER_USER

    # Daily breakdown from usage service
    daily = {}
    try:
        from services.usage_service import get_usage
        today_usage = get_usage(user_id, get_connection)
        daily["today"] = today_usage.get("ai_calls_today", 0)
    except Exception:
        daily["today"] = 0

    return {
        "user_id": user_id,
        "month": month_key,
        "total_cost_usd": round(total, 6),
        "budget_limit_usd": limit if limit > 0 else None,
        "budget_exceeded": limit > 0 and total >= limit,
        "budget_remaining": round(max(0, limit - total), 6) if limit > 0 else None,
        "daily": daily,
    }


def check_workspace_budget(user_id: int, workspace_id: int = 0, get_connection=None) -> bool:
    """
    Check if a user/workspace is within budget.

    Returns True if within budget (or if no limit is set), False otherwise.
    """
    limit = settings.AI_MONTHLY_COST_LIMIT_PER_USER
    if limit <= 0:
        return True  # No limit set

    total = get_monthly_cost(user_id)
    return total < limit


def get_cost_dashboard(user_id: int, get_connection=None) -> dict:
    """
    Comprehensive cost breakdown for the dashboard.

    Returns model usage, cache stats, budget status, and cost trends.
    """
    from datetime import datetime, timezone

    monthly = get_monthly_usage(user_id, get_connection)
    cache_stats = get_cache_stats()
    total_cache_entries = get_cache_size()

    # Model breakdown from monthly cache
    model_costs: dict[str, float] = {}
    try:
        from services.cost_intelligence import _monthly_cache
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        user_data = _monthly_cache.get(user_id, {})
        for mk, val in user_data.items():
            if mk == month_key:
                model_costs["current_month"] = val
    except Exception:
        pass

    return {
        "user_id": user_id,
        "monthly": monthly,
        "cache": {
            "hits": cache_stats["hits"],
            "misses": cache_stats["misses"],
            "total_entries": total_cache_entries,
            "hit_rate": (
                round(cache_stats["hits"] / (cache_stats["hits"] + cache_stats["misses"]), 4)
                if (cache_stats["hits"] + cache_stats["misses"]) > 0
                else 0.0
            ),
        },
        "model_costs": model_costs,
        "configured_model": settings.OPENAI_CHAT_MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def route_request(complexity: str = "simple", user_id: int = 0) -> dict:
    """
    Route a request to the appropriate model based on complexity and budget.

    Returns a dict with model selection, cost estimate, and budget status.
    """
    model = select_model(complexity)

    # Estimate cost for a typical request
    est = estimate_cost(model, input_tokens=1000, output_tokens=500)

    # Check budget
    within_budget = True
    budget_status = "ok"
    limit = settings.AI_MONTHLY_COST_LIMIT_PER_USER
    if limit > 0:
        current = get_monthly_cost(user_id)
        if current >= limit:
            within_budget = False
            budget_status = "exceeded"
        elif current + est.total_cost_usd > limit:
            within_budget = False
            budget_status = "would_exceed"

    return {
        "model": model,
        "complexity": complexity,
        "cost_estimate": {
            "input_tokens": est.input_tokens,
            "output_tokens": est.output_tokens,
            "total_cost_usd": est.total_cost_usd,
        },
        "within_budget": within_budget,
        "budget_status": budget_status,
        "monthly_cost_usd": round(get_monthly_cost(user_id), 6),
        "budget_limit_usd": limit if limit > 0 else None,
    }
