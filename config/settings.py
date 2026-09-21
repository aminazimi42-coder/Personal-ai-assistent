"""
config/settings.py
Centralized, validated environment configuration.
All application code must import from here — never from os.getenv directly.
"""

import os
import logging


def _require(name: str) -> str:
    """Return env var value or raise a clear error at startup."""
    value = os.getenv(name, "").strip()
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            "See .env.example for guidance."
        )
    return value


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        if value <= 0:
            raise ValueError
        return value
    except ValueError:
        logging.warning(
            "Config: invalid integer for %s='%s', using default %d",
            name, raw, default
        )
        return default


# ------------------------------------------------------------------ #
# DATABASE
# ------------------------------------------------------------------ #
DATABASE_URL: str = _require("DATABASE_URL")

# DB connection pool settings (used by psycopg2 pool)
DB_POOL_MIN: int = _get_int("DB_POOL_MIN", 1)
DB_POOL_MAX: int = _get_int("DB_POOL_MAX", 10)

# ------------------------------------------------------------------ #
# OPENAI / AI
# ------------------------------------------------------------------ #
OPENAI_API_KEY: str = _require("OPENAI_API_KEY")
OPENAI_CHAT_MODEL: str = _get("OPENAI_CHAT_MODEL", "gpt-4o-mini")

# Max output tokens per AI response
AI_MAX_TOKENS: int = _get_int("AI_MAX_TOKENS", 1024)
# Max output tokens for classification/extraction
AI_MAX_TOKENS_EXTRACTION: int = _get_int("AI_MAX_TOKENS_EXTRACTION", 512)
# OpenAI request timeout in seconds
AI_REQUEST_TIMEOUT: int = _get_int("AI_REQUEST_TIMEOUT", 30)
# Max input message length in characters
AI_MAX_INPUT_CHARS: int = _get_int("AI_MAX_INPUT_CHARS", 4000)

# ------------------------------------------------------------------ #
# APPLICATION
# ------------------------------------------------------------------ #
SECRET_KEY: str = _get("SECRET_KEY", "dev-insecure-change-in-production")
FLASK_ENV: str = _get("FLASK_ENV", "development")
IS_PRODUCTION: bool = FLASK_ENV == "production"

# ------------------------------------------------------------------ #
# CORS
# ------------------------------------------------------------------ #
_cors_raw = _get("CORS_ALLOWED_ORIGINS", "")
if _cors_raw:
    CORS_ALLOWED_ORIGINS: list[str] = [o.strip() for o in _cors_raw.split(",") if o.strip()]
else:
    # Default: allow localhost only in development; restrictive in production
    CORS_ALLOWED_ORIGINS = [] if IS_PRODUCTION else [
        "http://localhost:5000",
        "http://localhost:8000",
        "http://127.0.0.1:5000",
        "http://127.0.0.1:8000",
    ]

# ------------------------------------------------------------------ #
# AUTH / TOKEN
# ------------------------------------------------------------------ #
AUTH_TOKEN_EXPIRY_SECONDS: int = _get_int("AUTH_TOKEN_EXPIRY_SECONDS", 86400)  # 24h

# ------------------------------------------------------------------ #
# RATE LIMITING (requests per minute)
# ------------------------------------------------------------------ #
RATE_LIMIT_LOGIN: int = _get_int("RATE_LIMIT_LOGIN", 10)
RATE_LIMIT_AI: int = _get_int("RATE_LIMIT_AI", 20)
RATE_LIMIT_GENERAL: int = _get_int("RATE_LIMIT_GENERAL", 60)

# ------------------------------------------------------------------ #
# VOICE / UPLOADS
# ------------------------------------------------------------------ #
VOICE_MAX_UPLOAD_BYTES: int = _get_int("VOICE_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)  # 10 MB
ALLOWED_AUDIO_MIME_TYPES: list[str] = [
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "video/webm",  # Chrome sometimes sends this for audio
]

# ------------------------------------------------------------------ #
# SAAS / QUOTAS
# ------------------------------------------------------------------ #
# Max AI requests per user per day (0 = unlimited)
AI_DAILY_QUOTA_PER_USER: int = _get_int("AI_DAILY_QUOTA_PER_USER", 0)

# ------------------------------------------------------------------ #
# LOGGING
# ------------------------------------------------------------------ #
LOG_LEVEL_NAME: str = _get("LOG_LEVEL", "INFO").upper()
LOG_LEVEL: int = getattr(logging, LOG_LEVEL_NAME, logging.INFO)
