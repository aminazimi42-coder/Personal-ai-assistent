"""
services/usage_service.py
Per-user AI usage accounting and quota enforcement.

Tracks AI call counts per user per calendar day (UTC).
Uses a database-backed store for multi-worker correctness:
  - Atomic check-and-increment via SQL
  - Daily partition via date-column (one row per user per day)
  - No in-memory state for production — safe across Gunicorn workers and restarts

Table: ai_usage_events
  (user_id INTEGER, usage_date DATE, ai_calls INTEGER,
   PRIMARY KEY (user_id, usage_date))

Created by migration 003_add_ai_usage_events.py.
A fallback in-memory store is used if the DB table is not yet migrated
(e.g., during tests), so the interface stays the same.
"""

import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone

from config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Fallback in-memory store (used when DB table is not available)
# Thread-safe, but NOT shared across workers — only for tests/dev.
# ------------------------------------------------------------------ #
_lock = threading.Lock()
_mem_store: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
_db_available: bool | None = None  # cached check result


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _is_db_available(get_connection_fn) -> bool:
    """Check whether the ai_usage_events table exists (cached)."""
    global _db_available
    if _db_available is not None:
        return _db_available
    if get_connection_fn is None:
        _db_available = False
        return False
    try:
        conn = get_connection_fn()
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'ai_usage_events'
            )
        """)
        result = cur.fetchone()
        cur.close()
        from db.pool import return_connection
        return_connection(conn)
        _db_available = bool(result[0]) if result else False
    except Exception:
        _db_available = False
    return _db_available


def check_and_increment(user_id: int, get_connection_fn=None) -> tuple[bool, int]:
    """
    Check whether the user is within quota and atomically increment.

    Returns:
        (allowed: bool, current_count: int)

    If AI_DAILY_QUOTA_PER_USER == 0, quota is unlimited.

    Uses atomic SQL UPSERT when the DB table is available;
    falls back to in-memory for tests/dev.
    """
    quota = settings.AI_DAILY_QUOTA_PER_USER
    today = _today_utc()

    # --- DB-backed (multi-worker safe) ---
    if get_connection_fn and _is_db_available(get_connection_fn):
        try:
            conn = get_connection_fn()
            cur = conn.cursor()
            # Atomic upsert — get the count AFTER increment
            cur.execute("""
                INSERT INTO ai_usage_events (user_id, usage_date, ai_calls)
                VALUES (%s, %s, 1)
                ON CONFLICT (user_id, usage_date)
                DO UPDATE SET ai_calls = ai_usage_events.ai_calls + 1
                RETURNING ai_calls
            """, (user_id, today))
            result = cur.fetchone()
            conn.commit()
            cur.close()
            from db.pool import return_connection
            return_connection(conn)

            new_count = result[0] if result else 1

            # Quota check: if we just exceeded, deny (but keep the increment
            # — the call was attempted, even if we now reject it).
            if quota > 0 and new_count > quota:
                logger.warning(
                    "AI quota exceeded",
                    extra={"user_id": user_id, "daily_count": new_count, "quota": quota},
                )
                return False, new_count

            return True, new_count
        except Exception as exc:
            logger.warning("DB usage check failed, falling back to memory: %s", exc)
            global _db_available
            _db_available = False  # don't retry DB on subsequent calls

    # --- In-memory fallback (tests / single-worker) ---
    with _lock:
        current = _mem_store[user_id][today]
        if quota > 0 and current >= quota:
            logger.warning(
                "AI quota exceeded",
                extra={"user_id": user_id, "daily_count": current, "quota": quota},
            )
            return False, current

        _mem_store[user_id][today] += 1
        new_count = _mem_store[user_id][today]

    if quota > 0:
        logger.debug(
            "AI usage recorded",
            extra={"user_id": user_id, "daily_count": new_count, "quota": quota},
        )

    return True, new_count


def get_usage(user_id: int, get_connection_fn=None) -> dict:
    """
    Return today's usage summary for a user.
    Safe to call from any context.
    """
    today = _today_utc()
    quota = settings.AI_DAILY_QUOTA_PER_USER

    if get_connection_fn and _is_db_available(get_connection_fn):
        try:
            conn = get_connection_fn()
            cur = conn.cursor()
            cur.execute("""
                SELECT ai_calls FROM ai_usage_events
                WHERE user_id = %s AND usage_date = %s
            """, (user_id, today))
            result = cur.fetchone()
            cur.close()
            from db.pool import return_connection
            return_connection(conn)
            count = result[0] if result else 0
        except Exception:
            count = _get_mem_count(user_id, today)
    else:
        count = _get_mem_count(user_id, today)

    return {
        "user_id": user_id,
        "date": today,
        "ai_calls_today": count,
        "quota": quota if quota > 0 else None,
        "quota_exceeded": (quota > 0 and count >= quota),
    }


def _get_mem_count(user_id: int, today: str) -> int:
    with _lock:
        return _mem_store[user_id][today]


def reset_usage(user_id: int) -> None:
    """Reset all stored usage for a user (for testing or admin action)."""
    with _lock:
        _mem_store.pop(user_id, None)
