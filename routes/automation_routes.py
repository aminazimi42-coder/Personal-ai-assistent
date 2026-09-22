"""
routes/automation_routes.py
Automation endpoints — CRUD, execute, pause/resume, execution history.
All require authentication, user-isolated.
"""

import logging

from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor

from services.auth_service import get_current_user
from services.automation import (
    create_automation,
    get_automation,
    list_automations,
    delete_automation,
    execute_automation,
    pause_automation,
    resume_automation,
    list_automation_runs,
    TriggerType,
)
from db.pool import return_connection

logger = logging.getLogger(__name__)

VALID_TRIGGER_TYPES = {"daily", "hourly", "event", "manual"}


def init_automation_routes(app, get_connection):
    automation_routes = Blueprint("automation_routes", __name__)
    from services.rate_limiter import general_limit

    @automation_routes.route("/automations", methods=["POST"])
    @general_limit()
    def create_automation_route():
        """Create a new automation."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

            name = str(data.get("name", "")).strip()
            if not name:
                return jsonify({"status": "error", "message": "Automation name is required"}), 400

            trigger_type_str = str(data.get("trigger_type", "manual")).strip().lower()
            if trigger_type_str not in VALID_TRIGGER_TYPES:
                return jsonify({"status": "error", "message": f"Invalid trigger_type. Allowed: {', '.join(sorted(VALID_TRIGGER_TYPES))}"}), 400

            max_daily = int(data.get("max_daily_executions", 10))
            if max_daily < 1 or max_daily > 1000:
                return jsonify({"status": "error", "message": "max_daily_executions must be between 1 and 1000"}), 400

            try:
                trigger_type = TriggerType(trigger_type_str)
            except ValueError:
                trigger_type = TriggerType.MANUAL

            auto = create_automation(
                user_id=current_user["id"],
                name=name,
                trigger_type=trigger_type,
                max_daily_executions=max_daily,
                get_connection=get_connection,
            )
            return jsonify({"status": "success", "automation": auto}), 201

        except ValueError as ve:
            return jsonify({"status": "error", "message": str(ve)}), 400
        except Exception:
            logger.error("Create automation error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not create automation"}), 500

    @automation_routes.route("/automations", methods=["GET"])
    @general_limit()
    def list_automations_route():
        """List all automations for the current user."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            automations = list_automations(
                user_id=current_user["id"],
                get_connection=get_connection,
            )
            return jsonify({"status": "success", "automations": automations})

        except Exception:
            logger.error("List automations error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not retrieve automations"}), 500

    @automation_routes.route("/automations/<auto_id>", methods=["DELETE"])
    @general_limit()
    def delete_automation_route(auto_id):
        """Delete an automation."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            deleted = delete_automation(auto_id, current_user["id"], get_connection=get_connection)
            if not deleted:
                return jsonify({"status": "error", "message": "Automation not found"}), 404

            return jsonify({"status": "success", "message": "Automation deleted"})

        except Exception:
            logger.error("Delete automation error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not delete automation"}), 500

    @automation_routes.route("/automations/<auto_id>/execute", methods=["POST"])
    @general_limit()
    def execute_automation_route(auto_id):
        """Trigger an automation execution."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            result = execute_automation(
                auto_id=auto_id,
                user_id=current_user["id"],
                get_connection=get_connection,
            )

            status_code = 200 if result["status"] == "completed" else 422
            if result["status"] == "denied":
                status_code = 404
            elif result["status"] == "disabled":
                status_code = 409
            elif result["status"] == "limit_exceeded":
                status_code = 429

            return jsonify({"status": result["status"], "result": result}), status_code

        except Exception:
            logger.error("Execute automation error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not execute automation"}), 500

    @automation_routes.route("/automations/<auto_id>/pause", methods=["POST"])
    @general_limit()
    def pause_automation_route(auto_id):
        """Pause an automation."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            auto = pause_automation(auto_id, current_user["id"], get_connection=get_connection)
            if not auto:
                return jsonify({"status": "error", "message": "Automation not found"}), 404

            return jsonify({"status": "success", "automation": auto})

        except Exception:
            logger.error("Pause automation error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not pause automation"}), 500

    @automation_routes.route("/automations/<auto_id>/resume", methods=["POST"])
    @general_limit()
    def resume_automation_route(auto_id):
        """Resume a paused automation."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            auto = resume_automation(auto_id, current_user["id"], get_connection=get_connection)
            if not auto:
                return jsonify({"status": "error", "message": "Automation not found"}), 404

            return jsonify({"status": "success", "automation": auto})

        except Exception:
            logger.error("Resume automation error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not resume automation"}), 500

    @automation_routes.route("/automations/<auto_id>/runs", methods=["GET"])
    @general_limit()
    def list_automation_runs_route(auto_id):
        """Get execution history for an automation."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            runs = list_automation_runs(
                auto_id=auto_id,
                user_id=current_user["id"],
                limit=50,
                get_connection=get_connection,
            )
            return jsonify({"status": "success", "runs": runs})

        except Exception:
            logger.error("List automation runs error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not retrieve runs"}), 500

    app.register_blueprint(automation_routes)
