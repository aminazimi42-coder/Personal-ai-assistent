"""
routes/control_center_routes.py
Control Center endpoints: dashboard metrics, cost breakdown.

- GET /control-center     — return dashboard metrics (auth required)
- GET /control-center/cost — return cost breakdown (auth required)
"""

import logging

from flask import Blueprint, jsonify

from services.auth_service import get_current_user
from services.control_center import (
    get_dashboard_metrics,
    get_control_center,
)
from services.cost_intelligence import get_cost_dashboard
from services.rate_limiter import general_limit

logger = logging.getLogger(__name__)


def init_control_center_routes(app, get_connection):
    control_center_routes = Blueprint("control_center_routes", __name__)

    @control_center_routes.route("/control-center", methods=["GET"])
    @general_limit()
    def control_center():
        """Authenticated: return comprehensive control center snapshot."""
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            snapshot = get_control_center(user["id"], get_connection)
            return jsonify({"status": "success", "control_center": snapshot})

        except Exception:
            logger.error("Control center error", exc_info=True)
            return jsonify(
                {"status": "error", "message": "Could not retrieve control center"}
            ), 500

    @control_center_routes.route("/control-center/cost", methods=["GET"])
    @general_limit()
    def control_center_cost():
        """Authenticated: return cost breakdown for the current user."""
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            cost = get_cost_dashboard(user["id"], get_connection)
            return jsonify({"status": "success", "cost": cost})

        except Exception:
            logger.error("Cost dashboard error", exc_info=True)
            return jsonify(
                {"status": "error", "message": "Could not retrieve cost dashboard"}
            ), 500

    app.register_blueprint(control_center_routes)
