"""
routes/agent_routes.py
Agent execution endpoints: execute, approve, cancel, list, get runs.
All require authentication. Uses DB-backed agentic execution service.
"""

import logging

from flask import Blueprint, jsonify, request

from services.auth_service import get_current_user
from services.agentic_execution import (
    execute_action,
    approve_action,
    cancel_action,
    get_agent_run,
    list_agent_runs,
    retry_action,
    is_action_allowed,
    ActionStatus,
)
from db.pool import return_connection

logger = logging.getLogger(__name__)


def init_agent_routes(app, get_connection):
    agent_routes = Blueprint("agent_routes", __name__)
    from services.rate_limiter import general_limit

    @agent_routes.route("/agent/execute", methods=["POST"])
    @general_limit()
    def agent_execute():
        """Create and execute an agentic action."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

            action_name = str(data.get("action_name", "")).strip()
            if not action_name:
                return jsonify({"status": "error", "message": "action_name is required"}), 400

            if not is_action_allowed(action_name):
                return jsonify({"status": "error", "message": f"Unknown action: {action_name}"}), 400

            params = data.get("params", {})
            if not isinstance(params, dict):
                return jsonify({"status": "error", "message": "params must be a JSON object"}), 400

            action_id = data.get("action_id")
            approved = bool(data.get("approved", False))

            result = execute_action(
                action_name=action_name,
                user_id=current_user["id"],
                params=params,
                approved=approved,
                action_id=action_id,
                get_connection_fn=get_connection,
            )
            return jsonify({"status": "success", "run": result.to_dict()})
        except Exception:
            logger.error("Agent execute error", exc_info=True)
            return jsonify({"status": "error", "message": "Agent execution failed"}), 500

    @agent_routes.route("/agent/approve/<action_id>", methods=["POST"])
    @general_limit()
    def agent_approve(action_id):
        """Approve a pending agentic action."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            result = approve_action(
                action_id=action_id,
                user_id=current_user["id"],
                get_connection_fn=get_connection,
            )
            if result.status.value in ("denied",) and "not found" in (result.error or "").lower():
                return jsonify({"status": "error", "message": result.error}), 404
            return jsonify({"status": "success", "run": result.to_dict()})
        except Exception:
            logger.error("Agent approve error", exc_info=True)
            return jsonify({"status": "error", "message": "Approval failed"}), 500

    @agent_routes.route("/agent/cancel/<action_id>", methods=["POST"])
    @general_limit()
    def agent_cancel(action_id):
        """Cancel a pending or executing agentic action."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            canceled = cancel_action(
                action_id=action_id,
                user_id=current_user["id"],
                get_connection_fn=get_connection,
            )
            if not canceled:
                return jsonify({
                    "status": "error",
                    "message": "Action not found, not owned by user, or not cancelable",
                }), 404
            return jsonify({"status": "success", "message": "Action canceled"})
        except Exception:
            logger.error("Agent cancel error", exc_info=True)
            return jsonify({"status": "error", "message": "Cancellation failed"}), 500

    @agent_routes.route("/agent/retry/<action_id>", methods=["POST"])
    @general_limit()
    def agent_retry(action_id):
        """Retry a failed agentic action."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            result = retry_action(
                action_id=action_id,
                user_id=current_user["id"],
                get_connection_fn=get_connection,
            )
            if result.status == ActionStatus.DENIED and "not found" in (result.error or "").lower():
                return jsonify({"status": "error", "message": result.error}), 404
            return jsonify({"status": "success", "run": result.to_dict()})
        except Exception:
            logger.error("Agent retry error", exc_info=True)
            return jsonify({"status": "error", "message": "Retry failed"}), 500

    @agent_routes.route("/agent/runs", methods=["GET"])
    @general_limit()
    def agent_list_runs():
        """List the current user's agent runs."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            limit = request.args.get("limit", 50, type=int)
            if limit < 1 or limit > 500:
                limit = 50

            runs = list_agent_runs(
                user_id=current_user["id"],
                limit=limit,
                get_connection_fn=get_connection,
            )
            return jsonify({"status": "success", "runs": runs, "count": len(runs)})
        except Exception:
            logger.error("Agent list runs error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not list runs"}), 500

    @agent_routes.route("/agent/run/<action_id>", methods=["GET"])
    @general_limit()
    def agent_get_run(action_id):
        """Get a specific agent run (user-scoped)."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            run = get_agent_run(
                action_id=action_id,
                user_id=current_user["id"],
                get_connection_fn=get_connection,
            )
            if not run:
                return jsonify({"status": "error", "message": "Run not found"}), 404
            return jsonify({"status": "success", "run": run})
        except Exception:
            logger.error("Agent get run error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not retrieve run"}), 500

    app.register_blueprint(agent_routes)
