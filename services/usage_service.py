"""
services/usage_service.py
Per-user AI usage accounting and quota enforcement.

Tracks AI call counts per user per calendar day (UTC).
Uses an in-memory store with thread-safe access.

NOTE: This in-memory store resets on process restart and is not shared
between Gunicorn workers. For production multi-worker deployments, replace
_store with a Redis-backed counter (e.g., INCR with daily key TTL) or a
'usage_events' DB table. The interface (check_and_increment / get_usage)
remains the same — only the backend changes.
"""

import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone

from config import settings

logger = logging.getLogger(__name__)

# Thread-safe in-memory store: {user_id: {date_str: count}}
_lock = threading.Lock()
_store: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_and_increment(user_id: int) -> tuple[bool, int]:
    """
    Check whether the user is within quota and increment their counter.

    Returns:
        (allowed: bool, current_count: int)

    If AI_DAILY_QUOTA_PER_USER == 0, quota checking is disabled and all
    requests are allowed.
    """
    quota = settings.AI_DAILY_QUOTA_PER_USER
    today = _today_utc()

    with _lock:
        current = _store[user_id][today]
        if quota > 0 and current >= quota:
            logger.warning(
                "AI quota exceeded",
                extra={"user_id": user_id, "daily_count": current, "quota": quota},
            )
            return False, current

        _store[user_id][today] += 1
        new_count = _store[user_id][today]

    if quota > 0:
        logger.debug(
            "AI usage recorded",
            extra={"user_id": user_id, "daily_count": new_count, "quota": quota},
        )

    return True, new_count


def get_usage(user_id: int) -> dict:
    """
    Return today's usage summary for a user.
    Safe to call from any context.
    """
    today = _today_utc()
    quota = settings.AI_DAILY_QUOTA_PER_USER
    with _lock:
        count = _store[user_id][today]

    return {
        "user_id": user_id,
        "date": today,
        "ai_calls_today": count,
        "quota": quota if quota > 0 else None,
        "quota_exceeded": (quota > 0 and count >= quota),
    }


def reset_usage(user_id: int) -> None:
    """Reset all stored usage for a user (e.g., for testing or admin action)."""
    with _lock:
        _store.pop(user_id, None)
