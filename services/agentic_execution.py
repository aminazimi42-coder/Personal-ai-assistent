"""
services/agentic_execution.py
Agentic Task Execution — controlled multi-step execution with DB-backed
persistence, explicit state machine, idempotency, retries, cancellation,
and user isolation.

State Machine:
    PENDING → APPROVED → EXECUTING → COMPLETED
                                    → FAILED
    PENDING → DENIED
    PENDING / EXECUTING → CANCELED

Safety:
  - Action boundaries: only approved action types
  - Human-in-loop for sensitive actions (requires approval flag)
  - Failure recovery: structured error states, no silent failures
  - Idempotency: action_id prevents duplicate execution (if COMPLETED,
    return existing result)
  - Authorization: user_id — all actions user-scoped
  - Audit log: every action persisted to agent_runs table
  - No unrestricted autonomy: all actions bounded by registry
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ActionStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    DENIED = "denied"
    CANCELED = "canceled"


class ActionType(Enum):
    READ_ONLY = "read_only"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    COMMUNICATION = "communication"


# Registry of allowed actions — extend with new actions as needed
_ACTION_REGISTRY: dict[str, dict] = {
    "create_task": {
        "type": ActionType.WRITE,
        "requires_approval": False,
        "description": "Create a new task",
    },
    "update_task": {
        "type": ActionType.WRITE,
        "requires_approval": False,
        "description": "Update an existing task",
    },
    "delete_task": {
        "type": ActionType.DESTRUCTIVE,
        "requires_approval": True,
        "description": "Delete a task (requires approval)",
    },
    "create_appointment": {
        "type": ActionType.WRITE,
        "requires_approval": False,
        "description": "Create a new appointment",
    },
    "delete_appointment": {
        "type": ActionType.DESTRUCTIVE,
        "requires_approval": True,
        "description": "Delete an appointment (requires approval)",
    },
    "send_ai_reply": {
        "type": ActionType.COMMUNICATION,
        "requires_approval": False,
        "description": "Generate and send an AI reply",
    },
    "search_memory": {
        "type": ActionType.READ_ONLY,
        "requires_approval": False,
        "description": "Search user memories",
    },
}


# Valid state transitions for the state machine
_VALID_TRANSITIONS: dict[ActionStatus, set[ActionStatus]] = {
    ActionStatus.PENDING: {ActionStatus.APPROVED, ActionStatus.DENIED, ActionStatus.CANCELED},
    ActionStatus.APPROVED: {ActionStatus.EXECUTING, ActionStatus.CANCELED},
    ActionStatus.EXECUTING: {ActionStatus.COMPLETED, ActionStatus.FAILED, ActionStatus.CANCELED},
    ActionStatus.COMPLETED: set(),
    ActionStatus.FAILED: {ActionStatus.EXECUTING},  # retry
    ActionStatus.DENIED: set(),
    ActionStatus.CANCELED: set(),
}


# ------------------------------------------------------------------ #
# In-memory store for when no DB connection is available (tests/dev)
# ------------------------------------------------------------------ #

_runs_store: dict[str, dict] = {}
_runs_lock = None


def _get_runs_lock():
    global _runs_lock
    if _runs_lock is None:
        import threading
        _runs_lock = threading.Lock()
    return _runs_lock


def reset_runs_store():
    """Reset the in-memory runs store (for tests)."""
    with _get_runs_lock():
        _runs_store.clear()


@dataclass
class ActionResult:
    """Result of an agentic action execution."""
    action_id: str
    action_name: str
    status: ActionStatus
    user_id: int
    result: Any = None
    error: Optional[str] = None
    started_at: float = 0.0
    completed_at: float = 0.0
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "action_name": self.action_name,
            "status": self.status.value,
            "user_id": self.user_id,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


# ------------------------------------------------------------------ #
# Registry helpers
# ------------------------------------------------------------------ #

def get_action_registry() -> dict:
    """Return the action registry."""
    return _ACTION_REGISTRY.copy()


def is_action_allowed(action_name: str) -> bool:
    """Check if an action is in the registry."""
    return action_name in _ACTION_REGISTRY


def requires_approval(action_name: str) -> bool:
    """Check if an action requires human approval."""
    info = _ACTION_REGISTRY.get(action_name)
    if not info:
        return True  # Unknown actions require approval by default
    return info.get("requires_approval", True)


# ------------------------------------------------------------------ #
# DB persistence helpers
# ------------------------------------------------------------------ #

def _serialize_result(result: Any) -> Optional[str]:
    """Serialize result for JSON storage."""
    if result is None:
        return None
    try:
        return json.dumps(result, default=str)
    except (TypeError, ValueError):
        return str(result)


def _deserialize_result(raw: Any) -> Any:
    """Deserialize result from JSON storage."""
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
    return raw


def _persist_run(
    action_id: str,
    user_id: int,
    action_name: str,
    status: ActionStatus,
    params: dict,
    result: Any = None,
    error: Optional[str] = None,
    get_connection_fn: Optional[Callable] = None,
) -> None:
    """Persist (or update) a run record in the DB, or fall back to in-memory."""
    if get_connection_fn:
        try:
            _db_persist_run(
                action_id, user_id, action_name, status,
                params, result, error, get_connection_fn,
            )
            return
        except Exception as exc:
            logger.warning("DB persist failed, using in-memory: %s", exc)

    _mem_persist_run(action_id, user_id, action_name, status, params, result, error)


def _mem_persist_run(action_id, user_id, action_name, status, params, result, error):
    """Store run in in-memory dict."""
    with _get_runs_lock():
        existing = _runs_store.get(action_id, {})
        existing.update({
            "action_id": action_id,
            "user_id": user_id,
            "action_name": action_name,
            "status": status.value,
            "params": params,
            "result": _serialize_result(result),
            "error": error,
            "updated_at": time.time(),
        })
        if status in (ActionStatus.COMPLETED, ActionStatus.FAILED, ActionStatus.DENIED, ActionStatus.CANCELED):
            existing["completed_at"] = time.time()
        _runs_store[action_id] = existing


def _db_persist_run(action_id, user_id, action_name, status, params, result, error, get_connection_fn):
    """Persist run to agent_runs table."""
    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        result_json = _serialize_result(result)
        params_json = json.dumps(params, default=str) if params else None
        cur.execute("""
            INSERT INTO agent_runs (action_id, user_id, action_name, status, params, result, error, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (action_id) DO UPDATE SET
                status = EXCLUDED.status,
                result = EXCLUDED.result,
                error = EXCLUDED.error,
                updated_at = NOW()
        """, (action_id, user_id, action_name, status.value, params_json, result_json, error))
        if status in (ActionStatus.COMPLETED, ActionStatus.FAILED, ActionStatus.DENIED, ActionStatus.CANCELED):
            cur.execute("""
                UPDATE agent_runs SET completed_at = NOW() WHERE action_id = %s
            """, (action_id,))
        conn.commit()
    finally:
        cur.close()
        return_connection(conn)


def _get_run_from_db(action_id: str, user_id: int, get_connection_fn) -> Optional[dict]:
    """Fetch a run from the DB (user-scoped)."""
    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, action_id, user_id, action_name, status, params, result, error,
                   created_at, updated_at, completed_at
            FROM agent_runs
            WHERE action_id = %s AND user_id = %s
        """, (action_id, user_id))
        row = cur.fetchone()
    finally:
        cur.close()
        return_connection(conn)
    if not row:
        return None
    return dict(row)


def _list_runs_from_db(user_id: int, limit: int, get_connection_fn) -> list[dict]:
    """List runs from the DB (user-scoped)."""
    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, action_id, user_id, action_name, status, params, result, error,
                   created_at, updated_at, completed_at
            FROM agent_runs
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))
        rows = cur.fetchall()
    finally:
        cur.close()
        return_connection(conn)
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ #
# Public API — execution, approval, cancellation, retrieval, retry
# ------------------------------------------------------------------ #

def execute_action(
    action_name: str,
    user_id: int,
    params: dict,
    approved: bool = False,
    executor: Optional[Callable] = None,
    action_id: Optional[str] = None,
    get_connection_fn: Optional[Callable] = None,
) -> ActionResult:
    """
    Execute an agentic action with safety checks and DB persistence.

    Idempotency: if action_id is provided and a COMPLETED run already exists
    for this user, return the existing result without re-executing.

    Args:
        action_name: Name of the action from the registry
        user_id: ID of the user requesting the action
        params: Parameters for the action
        approved: Whether human approval has been given
        executor: Optional callable to execute; if None, action is simulated
        action_id: Optional explicit action_id for idempotency
        get_connection_fn: Optional DB connection provider for persistence

    Returns:
        ActionResult with status and result/error
    """
    if action_id is None:
        action_id = str(uuid.uuid4())[:8]

    t0 = time.monotonic()

    # Idempotency check: if COMPLETED run exists, return it
    if get_connection_fn:
        try:
            existing = _get_run_from_db(action_id, user_id, get_connection_fn)
            if existing and existing.get("status") == ActionStatus.COMPLETED.value:
                logger.info("Idempotent return: action_id=%s already completed", action_id)
                return ActionResult(
                    action_id=action_id,
                    action_name=action_name,
                    status=ActionStatus.COMPLETED,
                    user_id=user_id,
                    result=_deserialize_result(existing.get("result")),
                )
        except Exception as exc:
            logger.warning("Idempotency check failed (non-fatal): %s", exc)
    else:
        with _get_runs_lock():
            existing = _runs_store.get(action_id)
            if existing and existing.get("status") == ActionStatus.COMPLETED.value:
                logger.info("Idempotent return: action_id=%s already completed", action_id)
                return ActionResult(
                    action_id=action_id,
                    action_name=action_name,
                    status=ActionStatus.COMPLETED,
                    user_id=user_id,
                    result=_deserialize_result(existing.get("result")),
                )

    result = ActionResult(
        action_id=action_id,
        action_name=action_name,
        status=ActionStatus.PENDING,
        user_id=user_id,
        started_at=t0,
    )

    # Check: action must be registered
    if not is_action_allowed(action_name):
        result.status = ActionStatus.DENIED
        result.error = f"Unknown action: {action_name}"
        result.completed_at = time.monotonic()
        result.duration_ms = round((result.completed_at - t0) * 1000)
        _persist_run(action_id, user_id, action_name, ActionStatus.DENIED,
                     params, None, result.error, get_connection_fn)
        logger.warning("Agentic action denied (unknown): %s", action_name)
        return result

    # Check: approval required?
    if requires_approval(action_name) and not approved:
        result.status = ActionStatus.PENDING
        result.error = "This action requires human approval"
        result.completed_at = time.monotonic()
        result.duration_ms = round((result.completed_at - t0) * 1000)
        _persist_run(action_id, user_id, action_name, ActionStatus.PENDING,
                     params, None, result.error, get_connection_fn)
        logger.info(
            "Agentic action pending approval: %s (user=%d)",
            action_name, user_id,
        )
        return result

    # Execute
    result.status = ActionStatus.EXECUTING
    _persist_run(action_id, user_id, action_name, ActionStatus.EXECUTING,
                 params, None, None, get_connection_fn)
    try:
        if executor:
            result.result = executor(user_id=user_id, **params)
        else:
            result.result = {"simulated": True, "action": action_name, "params": params}

        result.status = ActionStatus.COMPLETED
        logger.info(
            "Agentic action completed: %s (user=%d, action_id=%s)",
            action_name, user_id, action_id,
        )
    except Exception as exc:
        result.status = ActionStatus.FAILED
        result.error = str(exc)
        logger.error(
            "Agentic action failed: %s (user=%d, error=%s)",
            action_name, user_id, exc,
            exc_info=True,
        )

    result.completed_at = time.monotonic()
    result.duration_ms = round((result.completed_at - t0) * 1000)
    _persist_run(action_id, user_id, action_name, result.status,
                 params, result.result, result.error, get_connection_fn)
    return result


def approve_action(
    action_id: str,
    user_id: int,
    executor: Optional[Callable] = None,
    get_connection_fn: Optional[Callable] = None,
) -> ActionResult:
    """
    Approve a pending action and execute it.

    State transition: PENDING → APPROVED → EXECUTING → COMPLETED/FAILED
    """
    # Fetch the pending run
    run = get_agent_run(action_id, user_id, get_connection_fn)
    if not run:
        return ActionResult(
            action_id=action_id,
            action_name="unknown",
            status=ActionStatus.DENIED,
            user_id=user_id,
            error="Action not found or not accessible by this user",
        )

    if run["status"] != ActionStatus.PENDING.value:
        return ActionResult(
            action_id=action_id,
            action_name=run.get("action_name", "unknown"),
            status=ActionStatus(run["status"]),
            user_id=user_id,
            error=f"Action is not pending (current status: {run['status']})",
        )

    # Re-execute with approval
    action_name = run["action_name"]
    params = run.get("params") or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except (json.JSONDecodeError, TypeError):
            params = {}

    return execute_action(
        action_name=action_name,
        user_id=user_id,
        params=params,
        approved=True,
        executor=executor,
        action_id=action_id,
        get_connection_fn=get_connection_fn,
    )


def cancel_action(
    action_id: str,
    user_id: int,
    get_connection_fn: Optional[Callable] = None,
) -> bool:
    """
    Cancel a pending or executing action.

    State transition: PENDING/EXECUTING → CANCELED
    Returns True if canceled, False if not cancelable (already completed/failed)
    or not owned by the requesting user.
    """
    # Use get_agent_run which enforces user isolation
    run = get_agent_run(action_id, user_id, get_connection_fn)
    if not run:
        return False

    current_status = run.get("status", "")
    if current_status not in (ActionStatus.PENDING.value, ActionStatus.EXECUTING.value, ActionStatus.APPROVED.value):
        return False

    _persist_run(action_id, user_id, run.get("action_name", "unknown"),
                  ActionStatus.CANCELED, run.get("params") or {},
                  None, "Action canceled by user", get_connection_fn)
    logger.info("Agentic action canceled: %s (user=%d)", action_id, user_id)
    return True


def retry_action(
    action_id: str,
    user_id: int,
    executor: Optional[Callable] = None,
    get_connection_fn: Optional[Callable] = None,
) -> ActionResult:
    """
    Retry a failed action. Re-executes with the same action_id and params.

    State transition: FAILED → EXECUTING → COMPLETED/FAILED
    """
    run = get_agent_run(action_id, user_id, get_connection_fn)
    if not run:
        return ActionResult(
            action_id=action_id,
            action_name="unknown",
            status=ActionStatus.DENIED,
            user_id=user_id,
            error="Action not found or not accessible by this user",
        )

    if run["status"] != ActionStatus.FAILED.value:
        return ActionResult(
            action_id=action_id,
            action_name=run.get("action_name", "unknown"),
            status=ActionStatus(run["status"]),
            user_id=user_id,
            error=f"Action is not in FAILED state (current: {run['status']})",
        )

    action_name = run["action_name"]
    params = run.get("params") or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except (json.JSONDecodeError, TypeError):
            params = {}

    # Determine if the original action required approval
    was_approved = not requires_approval(action_name)

    return execute_action(
        action_name=action_name,
        user_id=user_id,
        params=params,
        approved=was_approved,
        executor=executor,
        action_id=action_id,
        get_connection_fn=get_connection_fn,
    )


def get_agent_run(
    action_id: str,
    user_id: int,
    get_connection_fn: Optional[Callable] = None,
) -> Optional[dict]:
    """
    Get a specific agent run (user-scoped).

    Returns a dict with run details, or None if not found / not owned by user.
    """
    if get_connection_fn:
        try:
            run = _get_run_from_db(action_id, user_id, get_connection_fn)
            if run:
                return _normalize_run(run)
        except Exception as exc:
            logger.warning("DB get_run failed, using in-memory: %s", exc)

    with _get_runs_lock():
        run = _runs_store.get(action_id)
        if run and run.get("user_id") == user_id:
            return _normalize_run(run)
    return None


def list_agent_runs(
    user_id: int,
    limit: int = 50,
    get_connection_fn: Optional[Callable] = None,
) -> list[dict]:
    """
    List agent runs for a user (user-scoped).

    Returns a list of run dicts, most recent first.
    """
    if get_connection_fn:
        try:
            runs = _list_runs_from_db(user_id, limit, get_connection_fn)
            return [_normalize_run(r) for r in runs]
        except Exception as exc:
            logger.warning("DB list_runs failed, using in-memory: %s", exc)

    with _get_runs_lock():
        runs = [r for r in _runs_store.values() if r.get("user_id") == user_id]
    runs.sort(key=lambda r: r.get("updated_at", 0), reverse=True)
    return [_normalize_run(r) for r in runs[:limit]]


def _normalize_run(run: dict) -> dict:
    """Normalize a run dict for API output."""
    return {
        "action_id": run.get("action_id"),
        "user_id": run.get("user_id"),
        "action_name": run.get("action_name"),
        "status": run.get("status"),
        "params": _deserialize_result(run.get("params")) if run.get("params") else None,
        "result": _deserialize_result(run.get("result")),
        "error": run.get("error"),
        "created_at": str(run.get("created_at", "")) if run.get("created_at") else None,
        "updated_at": str(run.get("updated_at", "")) if run.get("updated_at") else None,
        "completed_at": str(run.get("completed_at", "")) if run.get("completed_at") else None,
    }
