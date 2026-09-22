"""
services/usage_service.py
Per-user AI usage accounting and quota enforcement.

Tracks AI call counts per user per calendar day (UTC).
Uses a database-backed store for multi-worker correctness:
  - Atomic check-and-increment via SQL UPSERT
  - Daily partition via date-column (one row per user per day)
  - Fail-closed: if the DB is unavailable in production, deny the
    request rather than silently allowing unlimited AI calls.

Table: ai_usage_events
  (user_id INTEGER, usage_date DATE, ai_calls INTEGER,
   PRIMARY KEY (user_id, usage_date))

Created by migration 003_add_ai_usage_events.py.

A thread-safe in-memory store is used ONLY when no DB connection is
available (e.g., unit tests with no DB).  In production, the DB-backed
path is used exclusively; if the DB query fails, the request is denied.
"""

import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone

from config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# In-memory store — used ONLY when no get_connection_fn is provided
# (e.g., unit tests).  NOT used in production paths.
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

    Production: uses atomic SQL UPSERT (multi-worker safe).
    If the DB query fails in production (IS_PRODUCTION), the request
    is DENIED (fail-closed) — never silently allow unlimited AI calls.
    If no get_connection_fn is provided (tests), uses in-memory store.
    """
    quota = settings.AI_DAILY_QUOTA_PER_USER
    today = _today_utc()

    # --- No connection function → in-memory (unit tests) ---
    if get_connection_fn is None:
        return _mem_check_and_increment(user_id, today, quota)

    # --- DB-backed (production) ---
    if not _is_db_available(get_connection_fn):
        # DB table not available
        if settings.IS_PRODUCTION:
            logger.error(
                "AI quota DB table not available in production — denying request (fail-closed)"
            )
            return False, 0
        # Non-production: use in-memory
        return _mem_check_and_increment(user_id, today, quota)

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

        # Quota check: if we just exceeded, deny
        if quota > 0 and new_count > quota:
            logger.warning(
                "AI quota exceeded",
                extra={"user_id": user_id, "daily_count": new_count, "quota": quota},
            )
            return False, new_count

        return True, new_count
    except Exception as exc:
        logger.error("DB usage check failed: %s", exc, exc_info=True)
        if settings.IS_PRODUCTION:
            # Fail-closed in production — deny the request
            return False, 0
        # Non-production: fall back to in-memory
        logger.warning("Falling back to in-memory usage store (non-production)")
        return _mem_check_and_increment(user_id, today, quota)


def _mem_check_and_increment(user_id: int, today: str, quota: int) -> tuple[bool, int]:
    """In-memory check-and-increment (thread-safe, single-worker only)."""
    with _lock:
        current = _mem_store[user_id][today]
        if quota > 0 and current >= quota:
            logger.warning(
                "AI quota exceeded (in-memory)",
                extra={"user_id": user_id, "daily_count": current, "quota": quota},
            )
            return False, current

        _mem_store[user_id][today] += 1
        new_count = _mem_store[user_id][today]

    if quota > 0:
        logger.debug(
            "AI usage recorded (in-memory)",
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
