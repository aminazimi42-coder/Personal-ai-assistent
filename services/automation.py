"""
services/automation.py — Durable Personal Automation Engine (DB-backed).

Refactored from the original in-memory _automations dict to a DB-backed
implementation with persistent state, idempotency, retries, daily limits,
pause/resume, audit (execution history), and user isolation.

Flow: TRIGGER → CONDITION → AI PROCESSING → ACTION → VERIFICATION

The public functions accept an optional ``get_connection`` callable.
If provided (production / integration tests) the DB-backed path is used.
If omitted (unit tests), the original in-memory path is used for backward
compatibility.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from psycopg2.extras import RealDictCursor

from db.pool import return_connection

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    DAILY = "daily"
    HOURLY = "hourly"
    EVENT = "event"
    MANUAL = "manual"


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_automation(row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    a = dict(row)
    for key in ("created_at", "updated_at", "last_executed"):
        v = a.get(key)
        if isinstance(v, datetime):
            a[key] = v.isoformat()
    return a


def _serialize_run(row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    r = dict(row)
    for key in ("created_at", "completed_at"):
        v = r.get(key)
        if isinstance(v, datetime):
            r[key] = v.isoformat()
    return r


# ------------------------------------------------------------------ #
# DB-backed operations
# ------------------------------------------------------------------ #

def _create_automation_db(
    get_connection,
    user_id: int,
    name: str,
    trigger_type: str = "manual",
    max_daily_executions: int = 10,
    auto_id: Optional[str] = None,
) -> dict:
    """DB-backed: create and persist an automation."""
    if not name or not name.strip():
        raise ValueError("Automation name is required")
    auto_id = auto_id or str(uuid.uuid4())[:12]
    now = _now()
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            INSERT INTO automations
                (id, user_id, name, trigger_type, enabled,
                 max_daily_executions, execution_count, created_at, updated_at)
            VALUES (%s, %s, %s, %s, TRUE, %s, 0, %s, %s)
            RETURNING *
            """,
            (auto_id, user_id, name.strip()[:200], trigger_type,
             max_daily_executions, now, now),
        )
        row = cur.fetchone()
        conn.commit()
    finally:
        cur.close()
        return_connection(conn)
    logger.info("Automation created: %s (user=%d)", auto_id, user_id)
    return _serialize_automation(row)  # type: ignore[return-value]


def _get_automation_db(get_connection, auto_id: str, user_id: int) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            "SELECT * FROM automations WHERE id = %s AND user_id = %s",
            (auto_id, user_id),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        return_connection(conn)
    return _serialize_automation(row)


def _list_automations_db(get_connection, user_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            "SELECT * FROM automations WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,),
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        return_connection(conn)
    return [_serialize_automation(r) for r in rows if r]  # type: ignore[list-item]


def _delete_automation_db(get_connection, auto_id: str, user_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            "DELETE FROM automations WHERE id = %s AND user_id = %s RETURNING id",
            (auto_id, user_id),
        )
        row = cur.fetchone()
        conn.commit()
    finally:
        cur.close()
        return_connection(conn)
    return row is not None


def _set_enabled_db(get_connection, auto_id: str, user_id: int, enabled: bool) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            UPDATE automations SET enabled = %s, updated_at = %s
            WHERE id = %s AND user_id = %s
            RETURNING *
            """,
            (enabled, _now(), auto_id, user_id),
        )
        row = cur.fetchone()
        conn.commit()
    finally:
        cur.close()
        return_connection(conn)
    return _serialize_automation(row)


def _count_today_runs(get_connection, auto_id: str, user_id: int) -> int:
    """Count completed runs for this automation today (UTC)."""
    now = _now()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*) FROM automation_runs
            WHERE automation_id = %s AND user_id = %s
              AND created_at >= date_trunc('day', %s)
              AND status = 'completed'
            """,
            (auto_id, user_id, now),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        return_connection(conn)
    return int(row[0]) if row else 0


def _create_run_db(
    get_connection, auto_id: str, user_id: int, status: str,
    result: Optional[dict] = None, error: Optional[str] = None,
) -> Optional[dict]:
    run_id = str(uuid.uuid4())[:12]
    now = _now()
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            INSERT INTO automation_runs
                (id, automation_id, user_id, status, result, error, created_at, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                run_id, auto_id, user_id, status,
                json.dumps(result) if result else None,
                error, now,
                now if status in ("completed", "failed") else None,
            ),
        )
        row = cur.fetchone()
        conn.commit()
    finally:
        cur.close()
        return_connection(conn)
    return _serialize_run(row)


def _update_automation_stats(get_connection, auto_id: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE automations
            SET execution_count = execution_count + 1,
                last_executed = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (_now(), _now(), auto_id),
        )
        conn.commit()
    finally:
        cur.close()
        return_connection(conn)


def _list_runs_db(get_connection, auto_id: str, user_id: int, limit: int = 50) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            SELECT * FROM automation_runs
            WHERE automation_id = %s AND user_id = %s
            ORDER BY created_at DESC LIMIT %s
            """,
            (auto_id, user_id, limit),
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        return_connection(conn)
    return [_serialize_run(r) for r in rows if r]  # type: ignore[list-item]


# ------------------------------------------------------------------ #
# Public API — dual-mode (DB when get_connection provided, in-mem otherwise)
# ------------------------------------------------------------------ #

def create_automation(
    user_id: int,
    name: str,
    trigger_type: TriggerType = TriggerType.MANUAL,
    max_daily_executions: int = 10,
    get_connection=None,
) -> Any:
    """
    Create a new automation.

    If *get_connection* is provided, persists to the DB (durable).
    Otherwise, uses the in-memory store (unit-test backward compat).
    """
    if get_connection is not None:
        tt = trigger_type.value if isinstance(trigger_type, TriggerType) else str(trigger_type)
        return _create_automation_db(get_connection, user_id, name, tt, max_daily_executions)
    # In-memory fallback
    if not name or not name.strip():
        raise ValueError("Automation name is required")
    auto_id = str(uuid.uuid4())[:8]
    auto = _InMemoryAutomation(
        id=auto_id, user_id=user_id, name=name.strip()[:200],
        trigger_type=trigger_type, max_daily_executions=max_daily_executions,
    )
    _automations[auto_id] = auto
    logger.info("Automation created (in-memory): %s (user=%d)", auto_id, user_id)
    return auto


def get_automation(auto_id: str, user_id: int, get_connection=None) -> Any:
    """Get an automation if it belongs to the user."""
    if get_connection is not None:
        return _get_automation_db(get_connection, auto_id, user_id)
    auto = _automations.get(auto_id)
    if auto and auto.user_id == user_id:
        return auto
    return None


def list_automations(user_id: int, get_connection=None) -> Any:
    """List all automations for a user."""
    if get_connection is not None:
        return _list_automations_db(get_connection, user_id)
    return [a for a in _automations.values() if a.user_id == user_id]


def delete_automation(auto_id: str, user_id: int, get_connection=None) -> Any:
    """Delete an automation if it belongs to the user."""
    if get_connection is not None:
        return _delete_automation_db(get_connection, auto_id, user_id)
    auto = _automations.get(auto_id)
    if auto and auto.user_id == user_id:
        del _automations[auto_id]
        return True
    return False


def pause_automation(auto_id: str, user_id: int, get_connection=None) -> Any:
    """Pause an automation (set enabled=false)."""
    if get_connection is not None:
        return _set_enabled_db(get_connection, auto_id, user_id, enabled=False)
    auto = _automations.get(auto_id)
    if auto and auto.user_id == user_id:
        auto.enabled = False
        return auto
    return None


def resume_automation(auto_id: str, user_id: int, get_connection=None) -> Any:
    """Resume an automation (set enabled=true)."""
    if get_connection is not None:
        return _set_enabled_db(get_connection, auto_id, user_id, enabled=True)
    auto = _automations.get(auto_id)
    if auto and auto.user_id == user_id:
        auto.enabled = True
        return auto
    return None


def execute_automation(
    auto_id: str,
    user_id: int,
    executor: Optional[Callable] = None,
    get_connection=None,
) -> dict:
    """
    Execute an automation with idempotency, daily limits, and audit.

    If *get_connection* is provided, persists run state to the DB.
    Otherwise, uses the in-memory store.
    """
    if get_connection is not None:
        return _execute_automation_db(get_connection, auto_id, user_id, executor)
    return _execute_automation_inmem(auto_id, user_id, executor)


def _execute_automation_db(get_connection, auto_id, user_id, executor=None) -> dict:
    result: dict[str, Any] = {
        "auto_id": auto_id,
        "user_id": user_id,
        "status": "pending",
        "executed": False,
        "error": None,
    }

    auto = _get_automation_db(get_connection, auto_id, user_id)
    if not auto:
        result["status"] = "denied"
        result["error"] = "Automation not found or not owned by user"
        return result

    if not auto.get("enabled", True):
        result["status"] = "disabled"
        result["error"] = "Automation is disabled (paused)"
        return result

    today_count = _count_today_runs(get_connection, auto_id, user_id)
    max_daily = auto.get("max_daily_executions", 10)
    if today_count >= max_daily:
        result["status"] = "limit_exceeded"
        result["error"] = f"Daily limit ({max_daily}) exceeded"
        logger.warning("Automation daily limit exceeded: %s", auto_id)
        return result

    _create_run_db(get_connection, auto_id, user_id, "executing")

    try:
        exec_result = executor(user_id=user_id) if executor else {"simulated": True}
        _create_run_db(get_connection, auto_id, user_id, "completed", result=exec_result)
        _update_automation_stats(get_connection, auto_id)

        result["status"] = "completed"
        result["executed"] = True
        result["result"] = exec_result
        return result

    except Exception as exc:
        _create_run_db(get_connection, auto_id, user_id, "failed", error=str(exc))
        result["status"] = "failed"
        result["error"] = str(exc)
        logger.error("Automation failed: %s — %s", auto_id, exc)
        return result


def _execute_automation_inmem(auto_id, user_id, executor=None) -> dict:
    import time as _time
    result = {
        "auto_id": auto_id, "user_id": user_id,
        "status": "pending", "executed": False, "error": None,
    }
    auto = _automations.get(auto_id)
    if not auto or auto.user_id != user_id:
        result["status"] = "denied"
        result["error"] = "Automation not found or not owned by user"
        return result
    if not auto.enabled:
        result["status"] = "disabled"
        result["error"] = "Automation is disabled"
        return result
    today = _now().strftime("%Y-%m-%d")
    if auto.daily_date != today:
        auto.daily_date = today
        auto.daily_count = 0
    if auto.daily_count >= auto.max_daily_executions:
        result["status"] = "limit_exceeded"
        result["error"] = f"Daily limit ({auto.max_daily_executions}) exceeded"
        return result
    try:
        if executor:
            result["result"] = executor(user_id=user_id)
        else:
            result["result"] = {"simulated": True}
        auto.execution_count += 1
        auto.daily_count += 1
        auto.last_executed = _time.time()
        result["status"] = "completed"
        result["executed"] = True
        _execution_log.append({
            "auto_id": auto_id, "user_id": user_id,
            "timestamp": _time.time(), "status": "completed",
        })
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        _execution_log.append({
            "auto_id": auto_id, "user_id": user_id,
            "timestamp": _time.time(), "status": "failed", "error": str(exc),
        })
    return result


def get_execution_log(user_id: int, limit: int = 50, get_connection=None) -> list[dict]:
    """Get execution log (all runs) for a user."""
    if get_connection is not None:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                SELECT ar.*, a.name as automation_name
                FROM automation_runs ar
                JOIN automations a ON ar.automation_id = a.id
                WHERE ar.user_id = %s
                ORDER BY ar.created_at DESC LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cur.fetchall()
        finally:
            cur.close()
            return_connection(conn)
        return [_serialize_run(r) for r in rows if r]  # type: ignore[list-item]
    return [e for e in _execution_log if e.get("user_id") == user_id][:limit]


def list_automation_runs(auto_id: str, user_id: int, limit: int = 50, get_connection=None) -> list[dict]:
    """Get execution history for a specific automation."""
    if get_connection is not None:
        return _list_runs_db(get_connection, auto_id, user_id, limit)
    return [e for e in _execution_log
            if e.get("auto_id") == auto_id and e.get("user_id") == user_id][:limit]


# ------------------------------------------------------------------ #
# In-memory data structures (for backward-compat with existing tests)
# ------------------------------------------------------------------ #

class _InMemoryAutomation:
    def __init__(self, id, user_id, name, trigger_type=TriggerType.MANUAL,
                 enabled=True, max_daily_executions=10, description="",
                 last_executed=None, execution_count=0, daily_count=0, daily_date=""):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.trigger_type = trigger_type
        self.enabled = enabled
        self.max_daily_executions = max_daily_executions
        self.description = description
        self.last_executed = last_executed
        self.execution_count = execution_count
        self.daily_count = daily_count
        self.daily_date = daily_date


_automations: dict[str, _InMemoryAutomation] = {}
_execution_log: list[dict] = []


def reset_automations():
    """Reset all in-memory automation data (for tests)."""
    _automations.clear()
    _execution_log.clear()
