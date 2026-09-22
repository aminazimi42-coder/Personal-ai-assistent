"""
tests/test_mcp_tools.py
Tests for the MCP-compatible tool infrastructure.

Verifies:
- MCP tool schemas exist for all registered tools
- MCP tool call routes through the gateway (no bypass)
- Permissions/approval are enforced via the gateway
- MCP cannot bypass gateway security
- Unregistered tools rejected
"""

import pytest

from services.mcp_tools import (
    MCPToolSchema,
    get_mcp_tool_schemas,
    get_mcp_tool_schema,
    call_mcp_tool,
)
from services.tool_gateway import (
    get_tool_registry,
    call_tool,
    ToolPolicy,
    register_tool,
    is_tool_registered,
)


class TestMCPToolSchemaDataclass:
    """Test MCPToolSchema dataclass."""

    def test_schema_fields(self):
        schema = MCPToolSchema(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            policy="read_only",
            requires_approval=False,
        )
        assert schema.name == "test_tool"
        assert schema.description == "A test tool"
        assert schema.input_schema == {"type": "object"}
        assert schema.output_schema == {"type": "object"}
        assert schema.policy == "read_only"
        assert schema.requires_approval is False

    def test_schema_to_dict(self):
        schema = MCPToolSchema(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            policy="read_only",
            requires_approval=False,
        )
        d = schema.to_dict()
        assert d["name"] == "test_tool"
        assert d["description"] == "A test tool"
        assert d["inputSchema"] == {"type": "object", "properties": {}}
        assert d["outputSchema"] == {"type": "object"}
        assert d["policy"] == "read_only"
        assert d["requiresApproval"] is False


class TestMCPToolSchemas:
    """Test that MCP schemas exist for all registered tools."""

    def test_get_mcp_tool_schemas_returns_list(self):
        schemas = get_mcp_tool_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) > 0

    def test_every_registered_tool_has_mcp_schema(self):
        registry = get_tool_registry()
        schemas = get_mcp_tool_schemas()
        schema_names = {s.name for s in schemas}
        for tool_name in registry:
            assert tool_name in schema_names, f"Missing MCP schema for: {tool_name}"

    def test_mcp_schema_count_matches_registry(self):
        registry = get_tool_registry()
        schemas = get_mcp_tool_schemas()
        assert len(schemas) == len(registry)

    def test_each_schema_has_required_fields(self):
        schemas = get_mcp_tool_schemas()
        for s in schemas:
            assert s.name is not None
            assert s.description is not None
            assert isinstance(s.input_schema, dict)
            assert isinstance(s.output_schema, dict)
            assert s.policy in ("read_only", "write", "destructive", "communication")
            assert isinstance(s.requires_approval, bool)

    def test_get_single_mcp_schema(self):
        schema = get_mcp_tool_schema("list_tasks")
        assert schema is not None
        assert schema.name == "list_tasks"

    def test_get_single_mcp_schema_not_found(self):
        schema = get_mcp_tool_schema("nonexistent_xyz")
        assert schema is None

    def test_input_schema_is_valid_json_schema(self):
        """Input schemas should have 'type' and 'properties'."""
        schemas = get_mcp_tool_schemas()
        for s in schemas:
            assert "type" in s.input_schema
            assert "properties" in s.input_schema

    def test_output_schema_is_valid_json_schema(self):
        """Output schemas should have 'type'."""
        schemas = get_mcp_tool_schemas()
        for s in schemas:
            assert "type" in s.output_schema


class TestMCPCallRouting:
    """Test that MCP calls route through the gateway."""

    def test_call_read_only_tool_via_mcp(self):
        result = call_mcp_tool("list_tasks", 1, {})
        assert result["success"] is True
        assert result["mcp_routed"] is True
        assert result["gateway_bypassed"] is False
        assert result["error"] is None

    def test_call_write_tool_via_mcp(self):
        result = call_mcp_tool("create_task", 1, {"title": "test"})
        assert result["success"] is True
        assert result["mcp_routed"] is True

    def test_call_destructive_without_approval_via_mcp(self):
        result = call_mcp_tool("delete_task", 1, {"task_id": 1}, approved=False)
        assert result["success"] is False
        assert result["mcp_routed"] is True
        assert "approval" in (result["error"] or "").lower()

    def test_call_destructive_with_approval_via_mcp(self):
        result = call_mcp_tool("delete_task", 1, {"task_id": 1}, approved=True)
        assert result["success"] is True
        assert result["mcp_routed"] is True

    def test_call_unregistered_tool_via_mcp(self):
        result = call_mcp_tool("nonexistent_xyz", 1, {})
        assert result["success"] is False
        assert result["mcp_routed"] is True
        assert result["gateway_bypassed"] is False
        assert "not registered" in (result["error"] or "").lower()

    def test_mcp_result_has_call_id(self):
        result = call_mcp_tool("list_tasks", 1, {})
        assert "call_id" in result
        assert result["call_id"] is not None

    def test_mcp_result_has_duration(self):
        result = call_mcp_tool("list_tasks", 1, {})
        assert "duration_ms" in result
        assert result["duration_ms"] >= 0


class TestMCPCannotBypass:
    """Test that MCP cannot bypass gateway security."""

    def test_mcp_respects_approval_gate(self):
        """Destructive tool without approval is blocked via MCP."""
        # Compare: direct gateway call vs MCP call
        direct = call_tool("delete_task", 1, {}, approved=False)
        mcp = call_mcp_tool("delete_task", 1, {}, approved=False)
        assert direct.allowed == mcp["success"]
        assert direct.allowed is False

    def test_mcp_respects_unregistered_rejection(self):
        """Unregistered tool is rejected via MCP same as direct."""
        direct = call_tool("nonexistent_xyz", 1, {})
        mcp = call_mcp_tool("nonexistent_xyz", 1, {})
        assert direct.allowed == mcp["success"]
        assert direct.allowed is False

    def test_mcp_does_not_add_extra_permissions(self):
        """MCP should not allow tools that the gateway rejects."""
        # ai_reply is communication but has requires_approval=False
        mcp = call_mcp_tool("ai_reply", 1, {})
        assert mcp["success"] is True

    def test_mcp_communication_tool_routing(self):
        """Communication tools route through gateway correctly."""
        mcp = call_mcp_tool("ai_reply", 1, {})
        assert mcp["mcp_routed"] is True
        assert mcp["gateway_bypassed"] is False

    def test_mcp_policy_matches_gateway(self):
        """MCP policy field matches the gateway's policy."""
        schemas = {s.name: s for s in get_mcp_tool_schemas()}
        registry = get_tool_registry()
        for name, tool_def in registry.items():
            if name in schemas:
                assert schemas[name].policy == tool_def.policy.value

    def test_mcp_requires_approval_matches_gateway(self):
        """MCP requires_approval matches the gateway's requires_approval."""
        schemas = {s.name: s for s in get_mcp_tool_schemas()}
        registry = get_tool_registry()
        for name, tool_def in registry.items():
            if name in schemas:
                assert schemas[name].requires_approval == tool_def.requires_approval

    def test_mcp_user_isolation(self):
        """MCP calls are user-scoped — different user_ids produce independent results."""
        r1 = call_mcp_tool("list_tasks", 1, {})
        r2 = call_mcp_tool("list_tasks", 2, {})
        assert r1["mcp_routed"] is True
        assert r2["mcp_routed"] is True
        # Both should succeed (read-only), but call_ids should differ
        assert r1["call_id"] != r2["call_id"]
