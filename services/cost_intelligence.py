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
