"""
routes/privacy_routes.py
Privacy operations endpoints: policy, data export, account deletion, data categories.

- GET  /privacy/policy         — public, returns the privacy policy
- GET  /privacy/export         — auth required, exports all user data
- DELETE /privacy/account      — auth required, deletes account (confirm=true)
- GET  /privacy/data-categories — auth required, returns data classifications
"""

import logging

from flask import Blueprint, jsonify, request

from services.auth_service import get_current_user
from services.privacy import (
    get_privacy_policy,
    export_user_data,
    delete_user_account,
    DataCategory,
    get_data_policy,
    classify_data,
    privacy_safe_log,
)
from services.rate_limiter import general_limit

logger = logging.getLogger(__name__)


def init_privacy_routes(app, get_connection):
    privacy_routes = Blueprint("privacy_routes", __name__)

    @privacy_routes.route("/privacy/policy", methods=["GET"])
    def privacy_policy():
        """Public endpoint: return the privacy policy."""
        policy = get_privacy_policy()
        return jsonify({"status": "success", "policy": policy})

    @privacy_routes.route("/privacy/export", methods=["GET"])
    @general_limit()
    def privacy_export():
        """Authenticated: export all data for the current user."""
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            data = export_user_data(user["id"], get_connection)
            logger.info(
                privacy_safe_log(
                    "User data exported",
                    user_id=user["id"],
                )
            )
            return jsonify({"status": "success", "data": data})

        except Exception:
            logger.error("Privacy export error", exc_info=True)
            return jsonify(
                {"status": "error", "message": "Data export failed"}
            ), 500

    @privacy_routes.route("/privacy/account", methods=["DELETE"])
    @general_limit()
    def privacy_delete_account():
        """Authenticated: delete the user's account and all data.

        Requires confirm=true query parameter to prevent accidental deletion.
        """
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            confirm = request.args.get("confirm", "").lower() in ("true", "1", "yes")
            if not confirm:
                return jsonify({
                    "status": "error",
                    "message": "Confirmation required: pass confirm=true to delete account",
                }), 400

            deleted = delete_user_account(user["id"], get_connection, confirm=True)
            if deleted:
                logger.info(
                    privacy_safe_log(
                        "User account deleted",
                        user_id=user["id"],
                    )
                )
                return jsonify({
                    "status": "success",
                    "message": "Account and all associated data deleted",
                })
            return jsonify({
                "status": "error",
                "message": "Account deletion failed — user may not exist",
            }), 404

        except Exception:
            logger.error("Account deletion error", exc_info=True)
            return jsonify(
                {"status": "error", "message": "Account deletion failed"}
            ), 500

    @privacy_routes.route("/privacy/data-categories", methods=["GET"])
    @general_limit()
    def privacy_data_categories():
        """Authenticated: return data classification for all categories."""
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            categories = []
            for cat in DataCategory:
                policy = get_data_policy(cat)
                categories.append({
                    "category": cat.value,
                    "classification": classify_data(cat).value,
                    "retention_days": policy.retention_days,
                    "encrypted_at_rest": policy.encrypted_at_rest,
                    "user_deletable": policy.user_deletable,
                })

            return jsonify({
                "status": "success",
                "categories": categories,
            })

        except Exception:
            logger.error("Data categories error", exc_info=True)
            return jsonify(
                {"status": "error", "message": "Could not retrieve data categories"}
            ), 500

    app.register_blueprint(privacy_routes)
