"""
routes/evaluation_routes.py
AI evaluation and MCP tool schema endpoints.
"""

import logging

from flask import Blueprint, jsonify, request

from services.auth_service import get_current_user
from services.usage_service import check_and_increment
from services.ai_evaluation import (
    run_default_evaluations,
    run_evaluations,
    get_default_scenarios,
    EvaluationScenario,
)
from services.mcp_tools import (
    get_mcp_tool_schemas,
    call_mcp_tool,
    get_mcp_tool_schema,
)

logger = logging.getLogger(__name__)


def init_evaluation_routes(app, get_connection):
    """Register evaluation and MCP route blueprints."""
    eval_routes = Blueprint("evaluation_routes", __name__)

    @eval_routes.route("/api/v1/ai-evaluation", methods=["GET"])
    def get_ai_evaluation():
        """Run all default evaluations and return results."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            allowed, _ = check_and_increment(current_user["id"], get_connection)
            if not allowed:
                return jsonify({
                    "status": "error",
                    "message": "Daily AI request limit reached. Please try again tomorrow.",
                }), 429

            run = run_default_evaluations()
            return jsonify({
                "status": "success",
                "run": run.to_dict(),
                "total_scenarios": run.pass_count + run.fail_count,
            })
        except Exception:
            logger.error("AI evaluation GET error", exc_info=True)
            return jsonify({"status": "error", "message": "Evaluation failed"}), 503

    @eval_routes.route("/api/v1/ai-evaluation", methods=["POST"])
    def post_ai_evaluation():
        """Run specific evaluation scenarios from the request body."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            allowed, _ = check_and_increment(current_user["id"], get_connection)
            if not allowed:
                return jsonify({
                    "status": "error",
                    "message": "Daily AI request limit reached. Please try again tomorrow.",
                }), 429

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

            scenarios_data = data.get("scenarios", [])
            if not isinstance(scenarios_data, list):
                return jsonify({"status": "error", "message": "scenarios must be a list"}), 400

            scenarios = []
            for s in scenarios_data:
                if not isinstance(s, dict) or "category" not in s or "input" not in s:
                    return jsonify({
                        "status": "error",
                        "message": "Each scenario needs at least 'category' and 'input'",
                    }), 400
                scenarios.append(EvaluationScenario(
                    id=s.get("id", f"custom-{len(scenarios)}"),
                    name=s.get("name", "Custom scenario"),
                    category=s["category"],
                    input=s["input"],
                    expected_properties=s.get("expected_properties", {}),
                    expected_result=s.get("expected_result", {}),
                ))

            if not scenarios:
                return jsonify({"status": "error", "message": "No scenarios provided"}), 400

            run = run_evaluations(scenarios)
            return jsonify({
                "status": "success",
                "run": run.to_dict(),
                "total_scenarios": run.pass_count + run.fail_count,
            })
        except Exception:
            logger.error("AI evaluation POST error", exc_info=True)
            return jsonify({"status": "error", "message": "Evaluation failed"}), 503

    @eval_routes.route("/api/v1/ai-evaluation/scenarios", methods=["GET"])
    def list_ai_evaluation_scenarios():
        """List all default evaluation scenarios."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            scenarios = get_default_scenarios()
            return jsonify({
                "status": "success",
                "scenarios": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "category": s.category,
                        "input": s.input if not isinstance(s.input, str) or len(s.input) < 200 else s.input[:200],
                        "expected_properties": s.expected_properties,
                        "expected_result": s.expected_result,
                    }
                    for s in scenarios
                ],
                "count": len(scenarios),
            })
        except Exception:
            logger.error("List scenarios error", exc_info=True)
            return jsonify({"status": "error", "message": "Failed to list scenarios"}), 503

    @eval_routes.route("/api/v1/mcp-tools", methods=["GET"])
    def get_mcp_tools():
        """Export all registered tools as MCP-compatible schemas."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            schemas = get_mcp_tool_schemas()
            return jsonify({
                "status": "success",
                "tools": [s.to_dict() for s in schemas],
                "count": len(schemas),
            })
        except Exception:
            logger.error("MCP tools GET error", exc_info=True)
            return jsonify({"status": "error", "message": "Failed to list MCP tools"}), 503

    @eval_routes.route("/api/v1/mcp-tools/<tool_name>", methods=["GET"])
    def get_mcp_tool_detail(tool_name):
        """Get MCP schema for a single tool."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            schema = get_mcp_tool_schema(tool_name)
            if schema is None:
                return jsonify({
                    "status": "error",
                    "message": f"Tool not registered: {tool_name}",
                }), 404

            return jsonify({
                "status": "success",
                "tool": schema.to_dict(),
            })
        except Exception:
            logger.error("MCP tool detail error", exc_info=True)
            return jsonify({"status": "error", "message": "Failed to get tool"}), 503

    @eval_routes.route("/api/v1/mcp-tools/<tool_name>/call", methods=["POST"])
    def invoke_mcp_tool(tool_name):
        """Call a tool through the MCP adapter (routes through gateway)."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            data = request.get_json(silent=True) or {}
            params = data.get("params", {})
            approved = data.get("approved", False)

            result = call_mcp_tool(
                tool_name=tool_name,
                user_id=current_user["id"],
                params=params,
                approved=approved,
            )
            return jsonify({
                "status": "success" if result["success"] else "error",
                "result": result,
            })
        except Exception:
            logger.error("MCP tool call error", exc_info=True)
            return jsonify({"status": "error", "message": "Tool call failed"}), 503

    app.register_blueprint(eval_routes)
