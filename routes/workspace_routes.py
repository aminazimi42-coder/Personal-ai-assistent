"""
routes/workspace_routes.py
Workspace API endpoints — authenticated, user-isolated CRUD.
Uses centralized auth_service for authentication.
No schema DDL here — managed by migrations.
"""

import logging

from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor

from services.auth_service import get_current_user
from services.workspace import (
    create_workspace as ws_create,
    get_workspace as ws_get,
    list_workspaces as ws_list,
    delete_workspace as ws_delete,
    create_project as proj_create,
    list_projects as proj_list,
    delete_project as proj_delete,
)
from db.pool import return_connection

logger = logging.getLogger(__name__)


def _serialize_workspace(ws) -> dict:
    """Serialize a Workspace dataclass to a JSON-safe dict."""
    return {
        "id": ws.id,
        "name": ws.name,
        "user_id": ws.user_id,
        "description": ws.description,
        "created_at": ws.created_at,
        "updated_at": ws.updated_at,
    }


def _serialize_project(proj) -> dict:
    """Serialize a Project dataclass to a JSON-safe dict."""
    return {
        "id": proj.id,
        "workspace_id": proj.workspace_id,
        "name": proj.name,
        "description": proj.description,
        "user_id": proj.user_id,
        "created_at": proj.created_at,
        "updated_at": proj.updated_at,
    }


def init_workspace_routes(app, get_connection):
    """Register workspace blueprint routes on the Flask app."""
    workspace_routes = Blueprint("workspace_routes", __name__)
    from services.rate_limiter import general_limit

    # ---------------------------------------------------------------- #
    # Workspace endpoints
    # ---------------------------------------------------------------- #

    @workspace_routes.route("/workspaces", methods=["POST"])
    @general_limit()
    def create_workspace():
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            data = request.get_json(silent=True)
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "Request body must be JSON",
                }), 400

            name = data.get("name")
            if not name or not str(name).strip():
                return jsonify({
                    "status": "error",
                    "message": "Workspace name is required",
                }), 400

            description = data.get("description", "")

            try:
                ws = ws_create(
                    user_id=user["id"],
                    name=name,
                    description=description,
                    get_connection=get_connection,
                )
            except ValueError as ve:
                return jsonify({"status": "error", "message": str(ve)}), 400

            return jsonify({
                "status": "success",
                "workspace": _serialize_workspace(ws),
            }), 201
        except Exception:
            logger.error("Create workspace error", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "Could not create workspace",
            }), 500

    @workspace_routes.route("/workspaces", methods=["GET"])
    @general_limit()
    def list_workspaces():
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            workspaces = ws_list(
                user_id=user["id"],
                get_connection=get_connection,
            )

            return jsonify({
                "status": "success",
                "workspaces": [_serialize_workspace(ws) for ws in workspaces],
            })
        except Exception:
            logger.error("List workspaces error", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "Could not list workspaces",
            }), 500

    @workspace_routes.route("/workspaces/<int:ws_id>", methods=["GET"])
    @general_limit()
    def get_workspace(ws_id):
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            ws = ws_get(
                ws_id=ws_id,
                user_id=user["id"],
                get_connection=get_connection,
            )

            if not ws:
                return jsonify({
                    "status": "error",
                    "message": "Workspace not found",
                }), 404

            return jsonify({
                "status": "success",
                "workspace": _serialize_workspace(ws),
            })
        except Exception:
            logger.error("Get workspace error", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "Could not retrieve workspace",
            }), 500

    @workspace_routes.route("/workspaces/<int:ws_id>", methods=["DELETE"])
    @general_limit()
    def delete_workspace(ws_id):
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            deleted = ws_delete(
                ws_id=ws_id,
                user_id=user["id"],
                get_connection=get_connection,
            )

            if not deleted:
                return jsonify({
                    "status": "error",
                    "message": "Workspace not found",
                }), 404

            return jsonify({
                "status": "success",
                "message": "Workspace deleted",
            })
        except Exception:
            logger.error("Delete workspace error", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "Could not delete workspace",
            }), 500

    # ---------------------------------------------------------------- #
    # Project endpoints (nested under workspaces)
    # ---------------------------------------------------------------- #

    @workspace_routes.route("/workspaces/<int:ws_id>/projects", methods=["POST"])
    @general_limit()
    def create_project(ws_id):
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            data = request.get_json(silent=True)
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "Request body must be JSON",
                }), 400

            name = data.get("name")
            if not name or not str(name).strip():
                return jsonify({
                    "status": "error",
                    "message": "Project name is required",
                }), 400

            description = data.get("description", "")

            try:
                proj = proj_create(
                    ws_id=ws_id,
                    user_id=user["id"],
                    name=name,
                    description=description,
                    get_connection=get_connection,
                )
            except ValueError as ve:
                return jsonify({"status": "error", "message": str(ve)}), 400

            if proj is None:
                return jsonify({
                    "status": "error",
                    "message": "Workspace not found or not owned by user",
                }), 404

            return jsonify({
                "status": "success",
                "project": _serialize_project(proj),
            }), 201
        except Exception:
            logger.error("Create project error", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "Could not create project",
            }), 500

    @workspace_routes.route("/workspaces/<int:ws_id>/projects", methods=["GET"])
    @general_limit()
    def list_projects(ws_id):
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            projects = proj_list(
                ws_id=ws_id,
                user_id=user["id"],
                get_connection=get_connection,
            )

            return jsonify({
                "status": "success",
                "projects": [_serialize_project(p) for p in projects],
            })
        except Exception:
            logger.error("List projects error", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "Could not list projects",
            }), 500

    @workspace_routes.route(
        "/workspaces/<int:ws_id>/projects/<int:proj_id>", methods=["DELETE"]
    )
    @general_limit()
    def delete_project(ws_id, proj_id):
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            deleted = proj_delete(
                proj_id=proj_id,
                user_id=user["id"],
                get_connection=get_connection,
            )

            if not deleted:
                return jsonify({
                    "status": "error",
                    "message": "Project not found",
                }), 404

            return jsonify({
                "status": "success",
                "message": "Project deleted",
            })
        except Exception:
            logger.error("Delete project error", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "Could not delete project",
            }), 500

    app.register_blueprint(workspace_routes)
