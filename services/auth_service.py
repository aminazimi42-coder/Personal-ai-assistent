"""
services/auth_service.py
Centralized authentication and authorization service.
All route handlers use these functions — no duplicate auth logic in routes.
"""

import hashlib
import logging
import re
import secrets
from datetime import datetime, timezone, timedelta

import bcrypt
from flask import request
from psycopg2.extras import RealDictCursor

from config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Constants
# ------------------------------------------------------------------ #
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_EMAIL_LENGTH = 254
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ------------------------------------------------------------------ #
# Token helpers
# ------------------------------------------------------------------ #

def generate_raw_token() -> str:
    """Generate a cryptographically secure raw bearer token."""
    return secrets.token_urlsafe(48)


def hash_token(raw_token: str) -> str:
    """
    Hash a raw token for storage.
    Uses SHA-256 — tokens are long random values so HMAC/salt not needed here,
    but we never store the raw token.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def token_expiry() -> datetime:
    """Return the token expiry timestamp based on configured lifetime."""
    return datetime.now(timezone.utc) + timedelta(
        seconds=settings.AUTH_TOKEN_EXPIRY_SECONDS
    )


# ------------------------------------------------------------------ #
# Password helpers
# ------------------------------------------------------------------ #

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ------------------------------------------------------------------ #
# Input validation
# ------------------------------------------------------------------ #

def validate_email(email: str) -> str:
    """Normalize and validate email. Raises ValueError on failure."""
    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("Email is required")
    if len(normalized) > MAX_EMAIL_LENGTH:
        raise ValueError("Email is too long")
    if not EMAIL_RE.match(normalized):
        raise ValueError("Invalid email format")
    return normalized


def validate_password(password: str) -> str:
    """Validate password meets minimum requirements. Raises ValueError on failure."""
    if not password:
        raise ValueError("Password is required")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("Password is too long")
    return password


# ------------------------------------------------------------------ #
# Request token extraction
# ------------------------------------------------------------------ #

def get_bearer_token() -> str | None:
    """Extract the raw bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "").strip()
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):].strip()
    return token or None


# ------------------------------------------------------------------ #
# User lookup by token
# ------------------------------------------------------------------ #

def get_current_user(get_connection):
    """
    Authenticate the current request by bearer token.

    Returns:
        (user_dict, None, None)        — authenticated
        (None, error_body_dict, code)  — not authenticated
    """
    raw_token = get_bearer_token()
    if not raw_token:
        return None, {"status": "error", "message": "Authentication required"}, 401

    token_hash = hash_token(raw_token)
    now = datetime.now(timezone.utc)

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Only match by hashed token — raw tokens are never stored
        cur.execute("""
            SELECT id, name, email, created_at, token_expires_at
            FROM users
            WHERE auth_token_hash = %s
              AND (token_expires_at IS NULL OR token_expires_at > %s)
        """, (token_hash, now))
        user = cur.fetchone()
    finally:
        cur.close()
        from db.pool import return_connection
        return_connection(conn)

    if not user:
        return None, {"status": "error", "message": "Invalid or expired token"}, 401

    return dict(user), None, None


def _lookup_user_by_token(token_hash: str) -> int | None:
    """
    Lightweight token-to-user-id lookup for rate limiting.
    Returns the user ID if a valid (non-expired) token hash matches,
    or None if not found.  Does NOT raise — callers handle None.
    """
    try:
        from db.pool import get_connection, return_connection
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT id FROM users
                WHERE auth_token_hash = %s
                  AND (token_expires_at IS NULL OR token_expires_at > %s)
            """, (token_hash, now))
            row = cur.fetchone()
        finally:
            cur.close()
            return_connection(conn)
        return row[0] if row else None
    except Exception:
        return None


def require_auth(get_connection):
    """
    Decorator-free auth check for use inside route functions.
    Returns (user, None) on success or (None, Response) on failure.
    """
    user, error, code = get_current_user(get_connection)
    return user, error, code
