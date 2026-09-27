"""
tests/test_config.py
Tests for centralized configuration validation.
"""

import os
import pytest


def test_config_loads_required_vars():
    """Config must load when required vars are set."""
    import config.settings as s
    assert s.DATABASE_URL == "postgresql+psycopg2://test:test@localhost/testdb"
    assert s.OPENAI_API_KEY == "sk-test-key"
    assert s.SECRET_KEY == "test-secret-key"


def test_config_default_values():
    """Defaults are applied when optional vars are absent."""
    import config.settings as s
    assert s.AI_MAX_TOKENS == 1024
    assert s.AI_MAX_TOKENS_EXTRACTION == 512
    assert s.AUTH_TOKEN_EXPIRY_SECONDS == 86400
    assert s.VOICE_MAX_UPLOAD_BYTES == 10 * 1024 * 1024
    assert s.DB_POOL_MAX == 10


def test_config_missing_database_url(monkeypatch):
    """EnvironmentError raised when DATABASE_URL is missing."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Must reload the module to trigger the error
    import importlib
    import config.settings
    monkeypatch.setenv("DATABASE_URL", "")
    with pytest.raises(EnvironmentError, match="DATABASE_URL"):
        importlib.reload(config.settings)
    # Restore
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/testdb")
    importlib.reload(config.settings)


def test_config_cors_origins():
    """CORS_ALLOWED_ORIGINS parsed correctly."""
    import config.settings as s
    assert "http://localhost:5000" in s.CORS_ALLOWED_ORIGINS


# ------------------------------------------------------------------ #
# Dialect rewrite tests
# ------------------------------------------------------------------ #

def test_normalize_db_url_rewrites_postgres_scheme():
    """postgres:// must become postgresql+psycopg2://"""
    from config.settings import _normalize_db_url
    result = _normalize_db_url("postgres://user:pass@host/db")
    assert result == "postgresql+psycopg2://user:pass@host/db"


def test_normalize_db_url_rewrites_postgresql_bare():
    """postgresql:// (no driver) must become postgresql+psycopg2://"""
    from config.settings import _normalize_db_url
    result = _normalize_db_url("postgresql://user:pass@host/db")
    assert result == "postgresql+psycopg2://user:pass@host/db"


def test_normalize_db_url_leaves_psycopg2_unchanged():
    """postgresql+psycopg2:// already has the right driver — must not be doubled."""
    from config.settings import _normalize_db_url
    url = "postgresql+psycopg2://user:pass@host/db"
    assert _normalize_db_url(url) == url


def test_database_url_is_normalized_at_load_time():
    """settings.DATABASE_URL must be rewritten even when conftest sets postgresql://"""
    import config.settings as s
    assert s.DATABASE_URL.startswith("postgresql+psycopg2://"), (
        f"DATABASE_URL should use psycopg2 dialect, got: {s.DATABASE_URL}"
    )


def test_psycopg2_dsn_strips_driver_specifier():
    """_psycopg2_dsn must strip +psycopg2 so psycopg2 can parse the URL."""
    from config.settings import _psycopg2_dsn
    assert _psycopg2_dsn("postgresql+psycopg2://u:p@h/db") == "postgresql://u:p@h/db"
    # Idempotent for already-plain URLs
    assert _psycopg2_dsn("postgresql://u:p@h/db") == "postgresql://u:p@h/db"


def test_database_dsn_is_valid_for_psycopg2():
    """settings.DATABASE_DSN must not contain +psycopg2 (psycopg2 cannot parse it)."""
    import config.settings as s
    assert "+psycopg2" not in s.DATABASE_DSN
    assert s.DATABASE_DSN.startswith("postgresql://")
