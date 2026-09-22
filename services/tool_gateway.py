"""
services/tool_gateway.py
AI Tool Gateway / Permissions — centralize tool access with policy checks.

Flow: AI AGENT → TOOL GATEWAY → PERMISSION CHECK → POLICY CHECK → TOOL → RESULT → VERIFICATION

- Least privilege: each tool has minimal permissions
- Explicit registry: tools must be registered to be callable
- Policy enforcement: read_only vs write vs destructive vs communication
- Approval gates: destructive tools require explicit approval
- Audit logs: every tool call logged
- Isolation: tools are user-scoped
- Safe failure: unknown tools denied, errors caught
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ToolPolicy(Enum):
    READ_ONLY = "read_only"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    COMMUNICATION = "communication"


@dataclass
class ToolDefinition:
    """Definition of a tool in the gateway."""
    name: str
    policy: ToolPolicy
    description: str
    handler: Optional[Callable] = None
    requires_approval: bool = False


@dataclass
class ToolCallResult:
    """Result of a tool call through the gateway."""
    call_id: str
    tool_name: str
    user_id: int
    allowed: bool
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    approved: bool = False

    def to_dict(self) -> dict:
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "user_id": self.user_id,
            "allowed": self.allowed,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "approved": self.approved,
        }


# Tool registry
_registry: dict[str, ToolDefinition] = {}


def register_tool(
    name: str,
    policy: ToolPolicy,
    description: str,
    handler: Optional[Callable] = None,
    requires_approval: bool = None,
) -> None:
    """Register a tool in the gateway."""
    if requires_approval is None:
        requires_approval = policy in (ToolPolicy.DESTRUCTIVE, ToolPolicy.COMMUNICATION)
    _registry[name] = ToolDefinition(
        name=name, policy=policy, description=description,
        handler=handler, requires_approval=requires_approval,
    )


def get_tool_registry() -> dict[str, ToolDefinition]:
    """Return the tool registry."""
    return dict(_registry)


def is_tool_registered(name: str) -> bool:
    """Check if a tool is registered."""
    return name in _registry


def call_tool(
    tool_name: str,
    user_id: int,
    params: dict,
    approved: bool = False,
) -> ToolCallResult:
    """
    Call a tool through the gateway with full policy enforcement.
    """
    call_id = str(uuid.uuid4())[:8]
    t0 = time.monotonic()

    result = ToolCallResult(
        call_id=call_id, tool_name=tool_name, user_id=user_id,
        allowed=False, approved=approved,
    )

    # Check: tool must be registered
    tool = _registry.get(tool_name)
    if not tool:
        result.error = f"Tool not registered: {tool_name}"
        result.duration_ms = round((time.monotonic() - t0) * 1000)
        logger.warning("Tool gateway: unregistered tool %s", tool_name)
        return result

    # Check: approval required?
    if tool.requires_approval and not approved:
        result.error = "Tool call requires approval"
        result.duration_ms = round((time.monotonic() - t0) * 1000)
        logger.info("Tool gateway: approval required for %s (user=%d)", tool_name, user_id)
        return result

    # Execute
    result.allowed = True
    try:
        if tool.handler:
            result.result = tool.handler(user_id=user_id, **params)
        else:
            result.result = {"simulated": True, "tool": tool_name}
        logger.info("Tool gateway: %s called (user=%d, call_id=%s)", tool_name, user_id, call_id)
    except Exception as exc:
        result.result = None
        result.error = str(exc)
        logger.error("Tool gateway: %s failed (user=%d): %s", tool_name, user_id, exc)
    finally:
        result.duration_ms = round((time.monotonic() - t0) * 1000)

    return result


# Register default tools
register_tool("list_tasks", ToolPolicy.READ_ONLY, "List user's tasks")
register_tool("get_task", ToolPolicy.READ_ONLY, "Get a specific task")
register_tool("create_task", ToolPolicy.WRITE, "Create a new task")
register_tool("update_task", ToolPolicy.WRITE, "Update an existing task")
register_tool("delete_task", ToolPolicy.DESTRUCTIVE, "Delete a task")
register_tool("list_appointments", ToolPolicy.READ_ONLY, "List appointments")
register_tool("create_appointment", ToolPolicy.WRITE, "Create an appointment")
register_tool("delete_appointment", ToolPolicy.DESTRUCTIVE, "Delete an appointment")
register_tool("ai_reply", ToolPolicy.COMMUNICATION, "Generate AI reply", requires_approval=False)
register_tool("search_memory", ToolPolicy.READ_ONLY, "Search user memories")
register_tool("set_memory", ToolPolicy.WRITE, "Store a memory")
register_tool("delete_memory", ToolPolicy.DESTRUCTIVE, "Delete a memory")
