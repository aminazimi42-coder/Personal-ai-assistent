"""
services/rate_limiter.py
Centralized rate limiting using Flask-Limiter.

Three configurable rate-limit tiers:
  - RATE_LIMIT_LOGIN:  per-IP, protects /signup and /login
  - RATE_LIMIT_AI:      per-user, protects AI endpoints
  - RATE_LIMIT_GENERAL: per-IP, default for all other API routes

Uses an in-memory storage backend by default.  For multi-worker
production, set REDIS_URL and the limiter will switch automatically.
All limits are expressed as "N per minute".
"""

import logging
import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Storage backend — Redis if configured, else in-memory
# ------------------------------------------------------------------ #
_storage_uri = os.getenv("REDIS_URL", "memory://")


def _key_func_ip() -> str:
    """Client identity by remote address (safe — no user data)."""
    return get_remote_address()


def _key_func_user() -> str:
    """
    Client identity by authenticated user_id, falling back to IP.

    Used for AI endpoints where the user may already be authenticated.
    Falls back to IP so that unauthenticated requests are still
    rate-limited (the auth check happens after the limiter).
    """
    from flask import g
    uid = g.get("user_id")
    if uid is not None:
        return f"user:{uid}"
    return f"ip:{get_remote_address()}"


# ------------------------------------------------------------------ #
# Limiter instance — created once, attached to app in create_app()
# ------------------------------------------------------------------ #
limiter = Limiter(
    key_func=_key_func_ip,
    default_limits=[],  # no global default — we apply per-endpoint
    storage_uri=_storage_uri,
    headers_enabled=True,  # X-RateLimit-* response headers
)


def init_limiter(app):
    """Initialize the limiter on the Flask app."""
    limiter.init_app(app)
    logger.info(
        "Rate limiter initialized (storage=%s, login=%d/min, ai=%d/min, general=%d/min)",
        _storage_uri,
        settings.RATE_LIMIT_LOGIN,
        settings.RATE_LIMIT_AI,
        settings.RATE_LIMIT_GENERAL,
    )


# ------------------------------------------------------------------ #
# Dynamic limit providers — read from settings at request time
# ------------------------------------------------------------------ #
def _login_limit_provider() -> str:
    return f"{settings.RATE_LIMIT_LOGIN}/minute"


def _ai_limit_provider() -> str:
    return f"{settings.RATE_LIMIT_AI}/minute"


def _general_limit_provider() -> str:
    return f"{settings.RATE_LIMIT_GENERAL}/minute"


# ------------------------------------------------------------------ #
# Decorator shortcuts — use these on individual endpoints
# ------------------------------------------------------------------ #
def login_limit():
    """Rate limit for login/signup endpoints (per IP)."""
    return limiter.limit(
        _login_limit_provider,
        key_func=_key_func_ip,
        methods=["POST"],
    )


def ai_limit():
    """Rate limit for AI endpoints (per user, falls back to IP)."""
    return limiter.limit(
        _ai_limit_provider,
        key_func=_key_func_user,
        methods=["POST"],
    )


def general_limit():
    """Rate limit for general API endpoints (per IP)."""
    return limiter.limit(
        _general_limit_provider,
        key_func=_key_func_ip,
    )
