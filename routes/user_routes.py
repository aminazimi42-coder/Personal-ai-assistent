"""
routes/user_routes.py
Authentication endpoints: signup, login, logout, /me.
Uses centralized auth_service — no duplicate logic.
"""

import logging

from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor

from services.auth_service import (
    validate_email,
    validate_password,
    hash_password,
    verify_password,
    generate_raw_token,
    hash_token,
    token_expiry,
    get_current_user,
    get_bearer_token,
)
from services.usage_service import get_usage
from db.pool import return_connection
from services.rate_limiter import general_limit

logger = logging.getLogger(__name__)


def init_user_routes(app, get_connection):
    user_routes = Blueprint("user_routes", __name__)
    from services.rate_limiter import login_limit

    @user_routes.route("/signup", methods=["POST"])
    @login_limit()
    def signup():
        try:
            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

            # Validate inputs
            try:
                email = validate_email(str(data.get("email", "")))
                password = validate_password(str(data.get("password", "")))
            except ValueError as ve:
                return jsonify({"status": "error", "message": str(ve)}), 400

            name = str(data.get("name", "")).strip()[:200]

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Check existing user
                cur.execute(
                    "SELECT id FROM users WHERE email = %s", (email,)
                )
                if cur.fetchone():
                    return jsonify({
                        "status": "error",
                        "message": "An account with this email already exists",
                    }), 409

                hashed_pw = hash_password(password)
                raw_token = generate_raw_token()
                token_hash = hash_token(raw_token)
                expires_at = token_expiry()

                cur.execute("""
                    INSERT INTO users
                        (name, email, password, auth_token_hash, auth_token, token_expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, name, email, created_at
                """, (name, email, hashed_pw, token_hash, raw_token, expires_at))
                user = cur.fetchone()
                conn.commit()
            finally:
                cur.close()
                return_connection(conn)

            logger.info("New user registered: id=%d", user["id"])
            return jsonify({
                "status": "success",
                "message": "Signup successful",
                "user": {
                    "id": user["id"],
                    "name": user["name"],
                    "email": user["email"],
                    "token": raw_token,
                    "created_at": user["created_at"].isoformat() if user["created_at"] else None,
                },
            }), 201

        except Exception:
            logger.error("Signup error", exc_info=True)
            return jsonify({"status": "error", "message": "Signup failed"}), 500

    @user_routes.route("/login", methods=["POST"])
    @login_limit()
    def login():
        try:
            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

            try:
                email = validate_email(str(data.get("email", "")))
            except ValueError as ve:
                return jsonify({"status": "error", "message": str(ve)}), 400

            password = str(data.get("password", ""))
            if not password:
                return jsonify({"status": "error", "message": "Password is required"}), 400

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(
                    "SELECT id, name, email, password, created_at FROM users WHERE email = %s",
                    (email,),
                )
                user = cur.fetchone()

                # Anti-enumeration: same response for "not found" and "wrong password"
                if not user or not verify_password(password, user["password"]):
                    return jsonify({
                        "status": "error",
                        "message": "Invalid email or password",
                    }), 401

                raw_token = generate_raw_token()
                token_hash = hash_token(raw_token)
                expires_at = token_expiry()

                cur.execute("""
                    UPDATE users
                    SET auth_token_hash = %s,
                        auth_token = %s,
                        token_expires_at = %s
                    WHERE id = %s
                """, (token_hash, raw_token, expires_at, user["id"]))
                conn.commit()
            finally:
                cur.close()
                return_connection(conn)

            logger.info("User logged in: id=%d", user["id"])
            return jsonify({
                "status": "success",
                "message": "Login successful",
                "user": {
                    "id": user["id"],
                    "name": user["name"],
                    "email": user["email"],
                    "token": raw_token,
                    "created_at": user["created_at"].isoformat() if user["created_at"] else None,
                },
            })

        except Exception:
            logger.error("Login error", exc_info=True)
            return jsonify({"status": "error", "message": "Login failed"}), 500

    @user_routes.route("/logout", methods=["POST"])
    @general_limit()
    def logout():
        try:
            raw_token = get_bearer_token()
            if not raw_token:
                return jsonify({"status": "error", "message": "Authentication required"}), 401

            token_hash = hash_token(raw_token)
            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute("""
                    UPDATE users
                    SET auth_token_hash = NULL,
                        auth_token = NULL,
                        token_expires_at = NULL
                    WHERE auth_token_hash = %s OR auth_token = %s
                    RETURNING id
                """, (token_hash, raw_token))
                revoked = cur.fetchone()
                conn.commit()
            finally:
                cur.close()
                return_connection(conn)

            if not revoked:
                return jsonify({"status": "error", "message": "Invalid token"}), 401

            return jsonify({"status": "success", "message": "Logout successful"})

        except Exception:
            logger.error("Logout error", exc_info=True)
            return jsonify({"status": "error", "message": "Logout failed"}), 500

    @user_routes.route("/me", methods=["GET"])
    @general_limit()
    def me():
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            return jsonify({
                "status": "success",
                "user": {
                    "id": user["id"],
                    "name": user.get("name"),
                    "email": user["email"],
                    "created_at": (
                        user["created_at"].isoformat()
                        if user.get("created_at") else None
                    ),
                },
            })

        except Exception:
            logger.error("Me endpoint error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not retrieve user"}), 500

    @user_routes.route("/me/usage", methods=["GET"])
    @general_limit()
    def me_usage():
        """Return the authenticated user's AI usage for today."""
        try:
            user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            usage = get_usage(user["id"])
            return jsonify({"status": "success", "usage": usage})

        except Exception:
            logger.error("Usage endpoint error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not retrieve usage"}), 500

    app.register_blueprint(user_routes)
