"""
main.py
Flask application factory and entry point.
"""

import logging
import os
import time
import uuid

from flask import Flask, jsonify, g, request

from config import settings
from db.models import db
from db.pool import init_pool, close_pool, get_connection
from services.rate_limiter import init_limiter, limiter


def create_app() -> Flask:
    """Application factory — creates and configures the Flask app."""

    # ------------------------------------------------------------------ #
    # Logging (must be first)
    # ------------------------------------------------------------------ #
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------ #
    # Flask app
    # ------------------------------------------------------------------ #
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Disable SQLAlchemy connection pool (we manage our own psycopg2 pool)
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

    # ------------------------------------------------------------------ #
    # SQLAlchemy / Flask-Migrate (schema management only)
    # ------------------------------------------------------------------ #
    db.init_app(app)
    from flask_migrate import Migrate
    Migrate(app, db)

    # ------------------------------------------------------------------ #
    # psycopg2 connection pool (runtime queries)
    # ------------------------------------------------------------------ #
    try:
        init_pool()
    except Exception:
        logger.warning("DB pool init deferred — DATABASE_URL may not be reachable yet")

    # ------------------------------------------------------------------ #
    # Rate limiter
    # ------------------------------------------------------------------ #
    try:
        init_limiter(app)
    except Exception:
        logger.warning("Rate limiter init deferred")

    @app.teardown_appcontext
    def _return_db_conn(exc):
        conn = g.pop("db_conn", None)
        if conn is not None:
            from db.pool import return_connection
            return_connection(conn, discard=(exc is not None))

    # ------------------------------------------------------------------ #
    # CORS — restrictive, configured origins only
    # ------------------------------------------------------------------ #
    @app.after_request
    def _cors_headers(response):
        origin = request.headers.get("Origin", "")
        allowed = settings.CORS_ALLOWED_ORIGINS

        # Always allow same-origin (no Origin header) and configured origins
        if not origin or origin in allowed:
            if origin:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Authorization"
            )
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
        return response

    # ------------------------------------------------------------------ #
    # Request ID + latency tracking
    # ------------------------------------------------------------------ #
    @app.before_request
    def _start_request():
        g.request_id = str(uuid.uuid4())[:8]
        g.request_start = time.monotonic()

    @app.after_request
    def _log_request(response):
        duration_ms = round((time.monotonic() - g.get("request_start", time.monotonic())) * 1000)
        request_id = g.get("request_id", "-")
        # Structured access log — never logs body/tokens/keys
        logger.info(
            "request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        response.headers["X-Request-Id"] = request_id
        return response

    @app.before_request
    def _handle_options():
        if request.method == "OPTIONS":
            response = app.make_default_options_response()
            return _cors_headers(response)

    # ------------------------------------------------------------------ #
    # Security headers
    # ------------------------------------------------------------------ #
    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    # ------------------------------------------------------------------ #
    # Global error handlers — never expose raw exceptions
    # ------------------------------------------------------------------ #
    @app.errorhandler(400)
    def _bad_request(e):
        return jsonify({"status": "error", "message": "Bad request"}), 400

    @app.errorhandler(401)
    def _unauthorized(e):
        return jsonify({"status": "error", "message": "Authentication required"}), 401

    @app.errorhandler(403)
    def _forbidden(e):
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    @app.errorhandler(404)
    def _not_found(e):
        return jsonify({"status": "error", "message": "Not found"}), 404

    @app.errorhandler(405)
    def _method_not_allowed(e):
        return jsonify({"status": "error", "message": "Method not allowed"}), 405

    @app.errorhandler(429)
    def _too_many_requests(e):
        logger.warning("Rate limit exceeded: %s", e)
        resp = jsonify({"status": "error", "message": "Too many requests. Please slow down."})
        resp.status_code = 429
        resp.headers["Retry-After"] = "60"
        return resp

    @app.errorhandler(500)
    def _internal_error(e):
        logger.error("Unhandled exception: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error"}), 500

    # ------------------------------------------------------------------ #
    # Routes
    # ------------------------------------------------------------------ #
    from flask import render_template
    from services.external_api import fetch_exchange_rates, ExternalAPIError

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/health")
    def health():
        """Lightweight liveness probe."""
        return jsonify({"status": "ok"})

    @app.route("/ready")
    def ready():
        """Readiness probe — checks DB connectivity."""
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            from db.pool import return_connection
            return_connection(conn)
            return jsonify({"status": "ready", "database": "connected"})
        except Exception as exc:
            logger.error("Readiness check failed: %s", exc)
            return jsonify({"status": "not_ready", "database": "unavailable"}), 503

    @app.route("/app-info")
    def app_info():
        return jsonify({
            "name": "Personal AI Assistant",
            "version": "1.0.0",
            "author": "Amin Azimi",
            "description": (
                "A smart productivity assistant for tasks, appointments, "
                "reminders, voice interaction, and AI-powered help."
            ),
        })

    @app.route("/exchange-rates")
    def exchange_rates():
        try:
            data = fetch_exchange_rates()
            return jsonify({
                "status": "success",
                "base": data["base"],
                "date": data["date"],
                "rates": data["rates"],
            })
        except ExternalAPIError:
            return jsonify({
                "status": "error",
                "message": "Exchange rate provider unavailable",
            }), 502
        except Exception:
            logger.warning("Exchange rates fetch failed", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "Could not load exchange rates",
            }), 502

    @app.route("/db-check")
    def db_check():
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            result = cur.fetchone()
            cur.close()
            from db.pool import return_connection
            return_connection(conn)
            return jsonify({
                "status": "success",
                "database": "connected",
                "result": result[0],
            })
        except Exception:
            logger.error("DB check failed", exc_info=True)
            return jsonify({"status": "error", "message": "Database unavailable"}), 503

    # ------------------------------------------------------------------ #
    # Register route blueprints
    # ------------------------------------------------------------------ #
    from routes.user_routes import init_user_routes
    from routes.task_routes import init_task_routes
    from routes.calendar_routes import init_calendar_routes
    from routes.reminder_routes import init_reminder_routes
    from routes.ai_routes import init_ai_routes

    init_user_routes(app, get_connection)
    init_task_routes(app, get_connection)
    init_calendar_routes(app, get_connection)
    init_reminder_routes(app, get_connection)
    init_ai_routes(app, get_connection)

    logger.info("Flask application created (env=%s)", settings.FLASK_ENV)
    return app


# ------------------------------------------------------------------ #
# Entry point
# ------------------------------------------------------------------ #
app = create_app()
