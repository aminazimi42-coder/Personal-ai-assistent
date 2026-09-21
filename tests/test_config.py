"""
tests/test_config.py
Tests for centralized configuration validation.
"""

import os
import pytest


def test_config_loads_required_vars():
    """Config must load when required vars are set."""
    import config.settings as s
    assert s.DATABASE_URL == "postgresql://test:test@localhost/testdb"
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
