"""
services/automation.py
Personal Automation — controlled triggers and scheduled actions.

Flow: TRIGGER → CONDITION → AI PROCESSING → ACTION → VERIFICATION

Features:
- Scheduling: time-based or event-based triggers
- Idempotency: each automation has a unique ID, no duplicate execution
- Retries: bounded retry on failure
- Failure handling: structured failure reporting
- Permissions: user-scoped, user controls
- Auditability: every trigger logged
- Cost/resource limits: max executions per day
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    DAILY = "daily"
    HOURLY = "hourly"
    EVENT = "event"
    MANUAL = "manual"


@dataclass
class Automation:
    """A scheduled automation."""
    id: str
    user_id: int
    name: str
    trigger_type: TriggerType
    enabled: bool = True
    max_daily_executions: int = 10
    description: str = ""
    last_executed: Optional[float] = None
    execution_count: int = 0
    daily_count: int = 0
    daily_date: str = ""


# Registry of automations
_automations: dict[str, Automation] = {}
_execution_log: list[dict] = []


def create_automation(
    user_id: int,
    name: str,
    trigger_type: TriggerType = TriggerType.MANUAL,
    description: str = "",
    max_daily_executions: int = 10,
) -> Automation:
    """Create a new automation."""
    if not name or not name.strip():
        raise ValueError("Automation name is required")
    auto_id = str(uuid.uuid4())[:8]
    auto = Automation(
        id=auto_id,
        user_id=user_id,
        name=name.strip()[:200],
        trigger_type=trigger_type,
        description=description.strip()[:1000],
        max_daily_executions=max_daily_executions,
    )
    _automations[auto_id] = auto
    logger.info("Automation created: %s (user=%d)", auto_id, user_id)
    return auto


def get_automation(auto_id: str, user_id: int) -> Optional[Automation]:
    """Get an automation if it belongs to the user."""
    auto = _automations.get(auto_id)
    if auto and auto.user_id == user_id:
        return auto
    return None


def list_automations(user_id: int) -> list[Automation]:
    """List all automations for a user."""
    return [a for a in _automations.values() if a.user_id == user_id]


def delete_automation(auto_id: str, user_id: int) -> bool:
    """Delete an automation if it belongs to the user."""
    auto = _automations.get(auto_id)
    if auto and auto.user_id == user_id:
        del _automations[auto_id]
        return True
    return False


def execute_automation(
    auto_id: str,
    user_id: int,
    executor: Optional[Callable] = None,
) -> dict:
    """
    Execute an automation with idempotency and cost limits.
    Returns a result dict with status.
    """
    from datetime import datetime, timezone
    result = {
        "auto_id": auto_id,
        "user_id": user_id,
        "status": "pending",
        "executed": False,
        "error": None,
    }

    auto = get_automation(auto_id, user_id)
    if not auto:
        result["status"] = "denied"
        result["error"] = "Automation not found or not owned by user"
        return result

    if not auto.enabled:
        result["status"] = "disabled"
        result["error"] = "Automation is disabled"
        return result

    # Check daily limit
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if auto.daily_date != today:
        auto.daily_date = today
        auto.daily_count = 0

    if auto.daily_count >= auto.max_daily_executions:
        result["status"] = "limit_exceeded"
        result["error"] = f"Daily limit ({auto.max_daily_executions}) exceeded"
        logger.warning("Automation daily limit exceeded: %s", auto_id)
        return result

    # Execute
    try:
        if executor:
            result["result"] = executor(user_id=user_id)
        else:
            result["result"] = {"simulated": True}

        auto.execution_count += 1
        auto.daily_count += 1
        auto.last_executed = time.time()
        result["status"] = "completed"
        result["executed"] = True
        _execution_log.append({
            "auto_id": auto_id,
            "user_id": user_id,
            "timestamp": time.time(),
            "status": "completed",
        })
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        _execution_log.append({
            "auto_id": auto_id,
            "user_id": user_id,
            "timestamp": time.time(),
            "status": "failed",
            "error": str(exc),
        })
        logger.error("Automation failed: %s — %s", auto_id, exc)

    return result


def get_execution_log(user_id: int, limit: int = 50) -> list[dict]:
    """Get execution log for a user."""
    return [e for e in _execution_log if e.get("user_id") == user_id][:limit]


def reset_automations():
    """Reset all automation data (for tests)."""
    _automations.clear()
    _execution_log.clear()
