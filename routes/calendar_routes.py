"""
routes/calendar_routes.py
Appointment CRUD endpoints. Uses centralized auth_service.
No schema DDL — managed by migrations.
Side-effecting GET /appointments/create removed; POST /appointments is the create endpoint.
"""

import logging

from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor

from services.auth_service import get_current_user
from services.calendar_service import (
    build_appointment_payload,
    parse_appointment_time,
    serialize_appointment,
)
from db.pool import return_connection

logger = logging.getLogger(__name__)


def _insert_appointment(get_connection, title, appointment_time,
                        description="", location="", status="scheduled",
                        user_id=None):
    payload = build_appointment_payload(
        title=title, appointment_time=appointment_time,
        description=description, location=location, status=status,
    )
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO appointments
                (title, description, appointment_time, location, status, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, title, description, appointment_time,
                      location, status, created_at, user_id
        """, (
            payload["title"], payload["description"], payload["appointment_time"],
            payload["location"], payload["status"], user_id,
        ))
        appt = cur.fetchone()
        conn.commit()
    finally:
        cur.close()
        return_connection(conn)
    return serialize_appointment(dict(appt))


def insert_appointment(get_connection, title, appointment_time,
                       description="", location="", status="scheduled",
                       user_id=None):
    """Public API for ai_routes to create appointments."""
    return _insert_appointment(get_connection, title, appointment_time,
                               description, location, status, user_id)


def init_calendar_routes(app, get_connection):
    calendar_routes = Blueprint("calendar_routes", __name__)

    @calendar_routes.route("/appointments", methods=["GET"])
    def get_appointments():
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute("""
                    SELECT id, title, description, appointment_time,
                           location, status, created_at, user_id
                    FROM appointments
                    WHERE user_id = %s
                    ORDER BY appointment_time ASC, id DESC
                """, (user["id"],))
                appointments = cur.fetchall()
            finally:
                cur.close()
                return_connection(conn)

            return jsonify({
                "status": "success",
                "appointments": [serialize_appointment(dict(a)) for a in appointments],
            })
        except Exception:
            logger.error("Get appointments error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not retrieve appointments"}), 500

    @calendar_routes.route("/appointments", methods=["POST"])
    def create_appointment():
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

            try:
                appointment_time = parse_appointment_time(data.get("appointment_time"))
                appt = _insert_appointment(
                    get_connection=get_connection,
                    title=data.get("title"),
                    appointment_time=appointment_time,
                    description=data.get("description", ""),
                    location=data.get("location", ""),
                    status=data.get("status", "scheduled"),
                    user_id=user["id"],
                )
            except ValueError as ve:
                return jsonify({"status": "error", "message": str(ve)}), 400

            return jsonify({"status": "success", "appointment": appt}), 201
        except Exception:
            logger.error("Create appointment error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not create appointment"}), 500

    @calendar_routes.route("/appointments/<int:appointment_id>", methods=["PUT"])
    def update_appointment(appointment_id):
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
                    SELECT id, title, description, appointment_time,
                           location, status, user_id
                    FROM appointments WHERE id = %s AND user_id = %s
                """, (appointment_id, user["id"]))
                existing = cur.fetchone()

                if not existing:
                    return jsonify({"status": "error", "message": "Appointment not found"}), 404

                appt_time_provided = "appointment_time" in data
                appointment_time = (
                    parse_appointment_time(data.get("appointment_time"))
                    if appt_time_provided
                    else existing["appointment_time"]
                )

                try:
                    payload = build_appointment_payload(
                        title=data.get("title") if data.get("title") is not None else existing["title"],
                        appointment_time=appointment_time,
                        description=data.get("description") if data.get("description") is not None else existing["description"],
                        location=data.get("location") if data.get("location") is not None else existing["location"],
                        status=data.get("status") if data.get("status") is not None else existing["status"],
                    )
                except ValueError as ve:
                    return jsonify({"status": "error", "message": str(ve)}), 400

                cur.execute("""
                    UPDATE appointments
                    SET title = %s, description = %s, appointment_time = %s,
                        location = %s, status = %s
                    WHERE id = %s AND user_id = %s
                    RETURNING id, title, description, appointment_time,
                              location, status, created_at, user_id
                """, (
                    payload["title"], payload["description"],
                    payload["appointment_time"], payload["location"],
                    payload["status"], appointment_id, user["id"],
                ))
                updated = cur.fetchone()
                conn.commit()
            finally:
                cur.close()
                return_connection(conn)

            return jsonify({"status": "success", "appointment": serialize_appointment(dict(updated))})
        except Exception:
            logger.error("Update appointment error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not update appointment"}), 500

    @calendar_routes.route("/appointments/<int:appointment_id>", methods=["DELETE"])
    def delete_appointment(appointment_id):
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute("""
                    DELETE FROM appointments WHERE id = %s AND user_id = %s
                    RETURNING id, title, description, appointment_time,
                              location, status, created_at, user_id
                """, (appointment_id, user["id"]))
                deleted = cur.fetchone()
                conn.commit()
            finally:
                cur.close()
                return_connection(conn)

            if not deleted:
                return jsonify({"status": "error", "message": "Appointment not found"}), 404

            return jsonify({
                "status": "success",
                "message": "Appointment deleted",
                "appointment": serialize_appointment(dict(deleted)),
            })
        except Exception:
            logger.error("Delete appointment error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not delete appointment"}), 500

    app.register_blueprint(calendar_routes)
