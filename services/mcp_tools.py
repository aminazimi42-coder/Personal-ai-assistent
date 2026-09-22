"""
services/mcp_tools.py
MCP-Compatible Tool Infrastructure — thin adapter over the Tool Gateway.

MCP tools are constrained to the same boundaries enforced by the gateway:
  - Permission / policy checks
  - Approval gates for destructive/communication tools
  - Audit logging
  - Tenant isolation (user-scoped)
  - Secret isolation
  - Sandboxing

MCP cannot bypass the gateway — it is a schema adapter only.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from services.tool_gateway import (
    call_tool,
    get_tool_registry,
    is_tool_registered,
    ToolPolicy,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# MCP Schema dataclass
# ------------------------------------------------------------------ #

@dataclass
class MCPToolSchema:
    """MCP-compatible tool schema."""
    name: str
    description: str
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    policy: str = "read_only"
    requires_approval: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "outputSchema": self.output_schema,
            "policy": self.policy,
            "requiresApproval": self.requires_approval,
        }


# ------------------------------------------------------------------ #
# JSON Schema builders for known tools
# ------------------------------------------------------------------ #

def _build_input_schema(tool_name: str) -> dict:
    """Build a deterministic JSON Schema for the tool's input."""
    if tool_name in ("list_tasks", "list_appointments", "search_memory"):
        return {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results to return"},
                "offset": {"type": "integer", "description": "Pagination offset"},
            },
            "additionalProperties": False,
        }
    if tool_name == "get_task":
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "Task ID"},
            },
            "required": ["task_id"],
            "additionalProperties": False,
        }
    if tool_name == "create_task":
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                "due": {"type": "string", "description": "Due date"},
            },
            "required": ["title"],
            "additionalProperties": False,
        }
    if tool_name == "update_task":
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "Task ID"},
                "title": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                "completed": {"type": "boolean"},
            },
            "required": ["task_id"],
            "additionalProperties": False,
        }
    if tool_name == "delete_task":
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "Task ID to delete"},
            },
            "required": ["task_id"],
            "additionalProperties": False,
        }
    if tool_name == "create_appointment":
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "date": {"type": "string"},
                "start_time": {"type": "string"},
                "end_time": {"type": "string"},
            },
            "required": ["title", "date"],
            "additionalProperties": False,
        }
    if tool_name == "delete_appointment":
        return {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "integer"},
            },
            "required": ["appointment_id"],
            "additionalProperties": False,
        }
    if tool_name == "ai_reply":
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to reply to"},
            },
            "required": ["message"],
            "additionalProperties": False,
        }
    if tool_name == "set_memory":
        return {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
            "additionalProperties": False,
        }
    if tool_name == "delete_memory":
        return {
            "type": "object",
            "properties": {
                "memory_id": {"type": "integer"},
            },
            "required": ["memory_id"],
            "additionalProperties": False,
        }
    # Generic fallback
    return {
        "type": "object",
        "properties": {},
        "additionalProperties": True,
    }


def _build_output_schema(tool_name: str, policy: ToolPolicy) -> dict:
    """Build a deterministic JSON Schema for the tool's output."""
    if policy == ToolPolicy.READ_ONLY:
        return {
            "type": "object",
            "properties": {
                "result": {"type": "array", "items": {"type": "object"}},
            },
        }
    if policy in (ToolPolicy.WRITE,):
        return {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "id": {"type": "integer"},
            },
            "required": ["success"],
        }
    if policy == ToolPolicy.DESTRUCTIVE:
        return {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "deleted": {"type": "boolean"},
            },
            "required": ["success"],
        }
    if policy == ToolPolicy.COMMUNICATION:
        return {
            "type": "object",
            "properties": {
                "reply": {"type": "string"},
            },
        }
    return {"type": "object", "properties": {}}


# ------------------------------------------------------------------ #
# Public API
# ------------------------------------------------------------------ #

def get_mcp_tool_schemas() -> list[MCPToolSchema]:
    """Export all registered tools in MCP-compatible format."""
    registry = get_tool_registry()
    schemas = []
    for name, tool_def in registry.items():
        schemas.append(MCPToolSchema(
            name=name,
            description=tool_def.description,
            input_schema=_build_input_schema(name),
            output_schema=_build_output_schema(name, tool_def.policy),
            policy=tool_def.policy.value,
            requires_approval=tool_def.requires_approval,
        ))
    return schemas


def get_mcp_tool_schema(tool_name: str) -> Optional[MCPToolSchema]:
    """Get the MCP schema for a single tool, or None if not registered."""
    if not is_tool_registered(tool_name):
        return None
    registry = get_tool_registry()
    tool_def = registry[tool_name]
    return MCPToolSchema(
        name=tool_name,
        description=tool_def.description,
        input_schema=_build_input_schema(tool_name),
        output_schema=_build_output_schema(tool_name, tool_def.policy),
        policy=tool_def.policy.value,
        requires_approval=tool_def.requires_approval,
    )


def call_mcp_tool(
    tool_name: str,
    user_id: int,
    params: dict,
    approved: bool = False,
) -> dict:
    """
    Call a tool via the MCP adapter — routes through tool_gateway.

    MCP cannot bypass the gateway: permission, approval, audit, and
    sandboxing are all enforced by call_tool() in tool_gateway.py.

    Returns a dict with: success, tool_name, result, error.
    """
    t0 = time.monotonic()

    # Validate tool is registered via MCP schema
    schema = get_mcp_tool_schema(tool_name)
    if schema is None:
        return {
            "success": False,
            "tool_name": tool_name,
            "result": None,
            "error": f"Tool not registered: {tool_name}",
            "mcp_routed": True,
            "gateway_bypassed": False,
            "duration_ms": round((time.monotonic() - t0) * 1000, 3),
        }

    # Route through the gateway — no shortcut
    gateway_result = call_tool(tool_name, user_id, params, approved=approved)

    return {
        "success": gateway_result.allowed,
        "tool_name": tool_name,
        "result": gateway_result.result,
        "error": gateway_result.error,
        "call_id": gateway_result.call_id,
        "mcp_routed": True,
        "gateway_bypassed": False,
        "duration_ms": round((time.monotonic() - t0) * 1000, 3),
    }
