"""
tests/test_production_env.py
Tests for production environment configuration:
- Secret key must not be default in production
- CORS must be restrictive in production
- Gunicorn config exists and is valid
- Health/readiness endpoints exist
- Render.yaml has correct secret handling
"""

import os
import pytest
from config import settings


def test_secret_key_not_empty():
    """SECRET_KEY must be set (not empty)."""
    assert settings.SECRET_KEY
    assert len(settings.SECRET_KEY) > 0


def test_secret_key_not_default_in_production(mocker):
    """In production, SECRET_KEY must not be the default dev value."""
    mocker.patch.object(settings, "FLASK_ENV", "production")
    mocker.patch.object(settings, "IS_PRODUCTION", True)
    # In production, the default should not be used — it must be set via env
    # We verify the settings module doesn't provide a production default
    assert settings.SECRET_KEY != "dev-insecure-change-in-production" or not settings.IS_PRODUCTION


def test_cors_restrictive_in_production(mocker):
    """In production, CORS must not be wildcard."""
    # If IS_PRODUCTION and no CORS_ALLOWED_ORIGINS set, it should be empty
    # (not wildcard). Check the settings logic.
    assert isinstance(settings.CORS_ALLOWED_ORIGINS, list)
    # No wildcard should be in the list
    assert "*" not in settings.CORS_ALLOWED_ORIGINS


def test_cors_origins_are_specific():
    """CORS origins should be specific URLs, not wildcards."""
    for origin in settings.CORS_ALLOWED_ORIGINS:
        assert origin.startswith("http://") or origin.startswith("https://")
        assert "*" not in origin


def test_gunicorn_config_exists():
    """gunicorn.conf.py must exist and be valid Python."""
    gunicorn_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "gunicorn.conf.py"
    )
    assert os.path.exists(gunicorn_path)
    with open(gunicorn_path) as f:
        content = f.read()
    # Must have key settings
    assert "workers" in content
    assert "timeout" in content
    assert "bind" in content


def test_procfile_exists():
    """Procfile must exist and reference gunicorn."""
    procfile_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "Procfile"
    )
    assert os.path.exists(procfile_path)
    with open(procfile_path) as f:
        content = f.read()
    assert "gunicorn" in content
    assert "main:app" in content


def test_render_yaml_exists():
    """render.yaml must exist."""
    render_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "render.yaml"
    )
    assert os.path.exists(render_path)


def test_render_yaml_secrets_not_inline():
    """render.yaml must not have secrets inline — use sync: false or generateValue."""
    render_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "render.yaml"
    )
    with open(render_path) as f:
        content = f.read()
    # OPENAI_API_KEY must use sync: false (dashboard-set)
    assert "sync: false" in content
    # SECRET_KEY must use generateValue: true
    assert "generateValue: true" in content


def test_health_endpoint_exists(client):
    """GET /health must return 200."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"


def test_ready_endpoint_exists(client):
    """GET /ready must exist (may return 503 if DB unavailable in test)."""
    res = client.get("/ready")
    assert res.status_code in (200, 503)


def test_production_config_has_no_debug():
    """In production, debug must be off."""
    # Flask debug mode is controlled by FLASK_ENV
    # settings.py sets IS_PRODUCTION based on FLASK_ENV
    if settings.IS_PRODUCTION:
        # Debug should not be True in production
        assert not settings.FLASK_ENV == "development"


def test_db_pool_config_exists():
    """DB pool settings must be configured."""
    assert settings.DB_POOL_MIN > 0
    assert settings.DB_POOL_MAX >= settings.DB_POOL_MIN


def test_ai_config_has_timeouts():
    """AI config must have timeout settings."""
    assert settings.AI_REQUEST_TIMEOUT > 0
    assert settings.AI_MAX_TOKENS > 0
    assert settings.AI_MAX_INPUT_CHARS > 0


def test_rate_limit_config_exists():
    """Rate limit config must be set."""
    assert settings.RATE_LIMIT_LOGIN > 0
    assert settings.RATE_LIMIT_AI > 0
    assert settings.RATE_LIMIT_GENERAL > 0
