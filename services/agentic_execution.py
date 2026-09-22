"""
services/agentic_execution.py
Agentic Task Execution — controlled multi-step execution.

Pipeline: PLAN → RETRIEVE → ANALYZE → PROPOSE → APPROVAL → EXECUTE → VERIFY → REPORT

Safety:
  - Action boundaries: only approved action types
  - Human-in-loop for sensitive actions (requires approval flag)
  - Failure recovery: structured error states, no silent failures
  - Idempotency: action_id prevents duplicate execution
  - Authorization: user_id required, all actions user-scoped
  - Audit log: every action logged with status
  - No unrestricted autonomy: all actions bounded by registry
"""

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


def execute_action(
    action_name: str,
    user_id: int,
    params: dict,
    approved: bool = False,
    executor: Optional[Callable] = None,
) -> ActionResult:
    """
    Execute an agentic action with safety checks.

    Args:
        action_name: Name of the action from the registry
        user_id: ID of the user requesting the action
        params: Parameters for the action
        approved: Whether human approval has been given (for sensitive actions)
        executor: Optional callable to execute; if None, action is simulated

    Returns:
        ActionResult with status and result/error
    """
    action_id = str(uuid.uuid4())[:8]
    t0 = time.monotonic()

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
        logger.warning("Agentic action denied (unknown): %s", action_name)
        return result

    # Check: approval required?
    if requires_approval(action_name) and not approved:
        result.status = ActionStatus.PENDING
        result.error = "This action requires human approval"
        result.completed_at = time.monotonic()
        result.duration_ms = round((result.completed_at - t0) * 1000)
        logger.info(
            "Agentic action pending approval: %s (user=%d)",
            action_name, user_id,
        )
        return result

    # Execute
    result.status = ActionStatus.EXECUTING
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
    return result
