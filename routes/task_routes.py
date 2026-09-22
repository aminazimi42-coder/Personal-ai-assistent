"""
routes/task_routes.py
Task CRUD endpoints. Uses centralized auth_service.
No schema DDL here — managed by migrations.
"""

import logging

from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor

from services.auth_service import get_current_user
from services.task_service import (
    build_task_payload,
    parse_due_date,
    serialize_task,
)
from db.pool import return_connection

logger = logging.getLogger(__name__)


def _insert_task(get_connection, title, description="", status="pending",
                 priority="medium", due_date=None, user_id=None):
    """Internal helper to insert a task and return the serialized record."""
    payload = build_task_payload(
        title=title, description=description, status=status,
        priority=priority, due_date=due_date, user_id=user_id
    )
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO tasks (title, description, status, priority, due_date, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, title, description, status, priority, due_date, created_at, user_id
        """, (
            payload["title"], payload["description"], payload["status"],
            payload["priority"], payload["due_date"], payload["user_id"],
        ))
        task = cur.fetchone()
        conn.commit()
    finally:
        cur.close()
        return_connection(conn)
    return serialize_task(dict(task))


def insert_task(get_connection, title, description="", status="pending",
                priority="medium", due_date=None, user_id=None):
    """Public API for other modules (ai_routes) to create tasks."""
    return _insert_task(get_connection, title, description, status,
                        priority, due_date, user_id)


def init_task_routes(app, get_connection):
    task_routes = Blueprint("task_routes", __name__)
    from services.rate_limiter import general_limit

    @task_routes.route("/tasks", methods=["GET"])
    @general_limit()
    def get_tasks():
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute("""
                    SELECT id, title, description, status, priority,
                           due_date, created_at, user_id
                    FROM tasks
                    WHERE user_id = %s
                    ORDER BY id DESC
                """, (user["id"],))
                tasks = cur.fetchall()
            finally:
                cur.close()
                return_connection(conn)

            return jsonify({
                "status": "success",
                "tasks": [serialize_task(dict(t)) for t in tasks],
            })
        except Exception:
            logger.error("Get tasks error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not retrieve tasks"}), 500

    @task_routes.route("/tasks", methods=["POST"])
    @general_limit()
    def create_task():
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

            try:
                due_date = parse_due_date(data.get("due_date"))
                task = _insert_task(
                    get_connection=get_connection,
                    title=data.get("title"),
                    description=data.get("description", ""),
                    status=data.get("status", "pending"),
                    priority=data.get("priority", "medium"),
                    due_date=due_date,
                    user_id=user["id"],
                )
            except ValueError as ve:
                return jsonify({"status": "error", "message": str(ve)}), 400

            return jsonify({"status": "success", "task": task}), 201
        except Exception:
            logger.error("Create task error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not create task"}), 500

    @task_routes.route("/tasks/<int:task_id>", methods=["PUT"])
    @general_limit()
    def update_task(task_id):
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute("""
                    SELECT id, title, description, status, priority, due_date, user_id
                    FROM tasks WHERE id = %s AND user_id = %s
                """, (task_id, user["id"]))
                existing = cur.fetchone()

                if not existing:
                    return jsonify({"status": "error", "message": "Task not found"}), 404

                due_date_provided = "due_date" in data
                due_date = (
                    parse_due_date(data.get("due_date")) if due_date_provided
                    else existing["due_date"]
                )

                try:
                    payload = build_task_payload(
                        title=data.get("title") if data.get("title") is not None else existing["title"],
                        description=data.get("description") if data.get("description") is not None else existing["description"],
                        status=data.get("status") if data.get("status") is not None else existing["status"],
                        priority=data.get("priority") if data.get("priority") is not None else existing["priority"],
                        due_date=due_date,
                        user_id=existing["user_id"],
                    )
                except ValueError as ve:
                    return jsonify({"status": "error", "message": str(ve)}), 400

                cur.execute("""
                    UPDATE tasks
                    SET title = %s, description = %s, status = %s,
                        priority = %s, due_date = %s
                    WHERE id = %s AND user_id = %s
                    RETURNING id, title, description, status, priority,
                              due_date, created_at, user_id
                """, (
                    payload["title"], payload["description"], payload["status"],
                    payload["priority"], payload["due_date"],
                    task_id, user["id"],
                ))
                updated = cur.fetchone()
                conn.commit()
            finally:
                cur.close()
                return_connection(conn)

            return jsonify({"status": "success", "task": serialize_task(dict(updated))})
        except Exception:
            logger.error("Update task error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not update task"}), 500

    @task_routes.route("/tasks/<int:task_id>", methods=["DELETE"])
    @general_limit()
    def delete_task(task_id):
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute("""
                    DELETE FROM tasks WHERE id = %s AND user_id = %s
                    RETURNING id, title, description, status, priority,
                              due_date, created_at, user_id
                """, (task_id, user["id"]))
                deleted = cur.fetchone()
                conn.commit()
            finally:
                cur.close()
                return_connection(conn)

            if not deleted:
                return jsonify({"status": "error", "message": "Task not found"}), 404

            return jsonify({
                "status": "success",
                "message": "Task deleted",
                "task": serialize_task(dict(deleted)),
            })
        except Exception:
            logger.error("Delete task error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not delete task"}), 500

    app.register_blueprint(task_routes)
