"""
routes/reminder_routes.py
Reminder aggregation endpoint.
No schema DDL — managed by migrations.
"""

import logging

from flask import Blueprint, jsonify

from services.auth_service import get_current_user
from services.reminder_service import build_reminder_window, build_reminders_payload
from db.pool import return_connection

logger = logging.getLogger(__name__)


def init_reminder_routes(app, get_connection):
    reminder_routes = Blueprint("reminder_routes", __name__)
    from services.rate_limiter import general_limit

    @reminder_routes.route("/reminders", methods=["GET"])
    @general_limit()
    def get_reminders():
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            reminder_window = build_reminder_window(hours=1)
            current_time = reminder_window["current_time"]
            end_time = reminder_window["end_time"]

            conn = get_connection()
            cur = conn.cursor()
            try:
                cur.execute("""
                    SELECT id, title, due_date, status
                    FROM tasks
                    WHERE user_id = %s
                      AND due_date IS NOT NULL
                      AND due_date >= %s
                      AND due_date <= %s
                      AND status = 'pending'
                    ORDER BY due_date ASC
                """, (current_user["id"], current_time, end_time))
                task_rows = cur.fetchall()

                cur.execute("""
                    SELECT id, title, appointment_time, status
                    FROM appointments
                    WHERE user_id = %s
                      AND appointment_time >= %s
                      AND appointment_time <= %s
                      AND status = 'scheduled'
                    ORDER BY appointment_time ASC
                """, (current_user["id"], current_time, end_time))
                appointment_rows = cur.fetchall()
            finally:
                cur.close()
                return_connection(conn)

            tasks = [
                {"id": r[0], "title": r[1], "due_date": r[2], "status": r[3]}
                for r in task_rows
            ]
            appointments = [
                {"id": r[0], "title": r[1], "appointment_time": r[2], "status": r[3]}
                for r in appointment_rows
            ]

            return jsonify(build_reminders_payload(tasks, appointments))
        except Exception:
            logger.error("Get reminders error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not retrieve reminders"}), 500

    app.register_blueprint(reminder_routes)
