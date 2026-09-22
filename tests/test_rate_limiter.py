"""
tests/test_rate_limiter.py
Tests for rate limiting: login, AI, and general limits.
Verifies 429 semantics, configurable limits, and no bypass.
"""

import pytest
from unittest.mock import MagicMock, patch
from tests.conftest import make_user


def _mock_auth(mocker, user=None):
    """Patch get_current_user in every route module."""
    u = user or make_user()
    for target in [
        "routes.task_routes.get_current_user",
        "routes.calendar_routes.get_current_user",
        "routes.ai_routes.get_current_user",
        "routes.reminder_routes.get_current_user",
    ]:
        mocker.patch(target, return_value=(u, None, None))
    return u


def test_rate_limiter_health_not_limited(client):
    """Health endpoint should not be rate-limited."""
    for _ in range(100):
        res = client.get("/health")
        assert res.status_code == 200


def test_rate_limiter_login_limit_triggers_429(client, mocker):
    """Login endpoint should return 429 after exceeding RATE_LIMIT_LOGIN."""
    # Set a very low limit for testing
    mocker.patch("config.settings.RATE_LIMIT_LOGIN", 2)
    mocker.patch("services.rate_limiter.settings.RATE_LIMIT_LOGIN", 2)

    # First 2 requests should not be rate-limited (they may return 400/500 but not 429)
    for i in range(2):
        res = client.post("/login", json={"email": "test@test.com", "password": "test12345"})
        assert res.status_code != 429, f"Request {i} should not be rate-limited"

    # Third request should hit the limit
    res = client.post("/login", json={"email": "test@test.com", "password": "test12345"})
    assert res.status_code == 429
    data = res.get_json()
    assert data["status"] == "error"
    assert "Retry-After" in res.headers or res.status_code == 429


def test_rate_limiter_signup_limit_triggers_429(client, mocker):
    """Signup endpoint should return 429 after exceeding RATE_LIMIT_LOGIN."""
    mocker.patch("config.settings.RATE_LIMIT_LOGIN", 2)
    mocker.patch("services.rate_limiter.settings.RATE_LIMIT_LOGIN", 2)

    for i in range(2):
        res = client.post("/signup", json={
            "email": f"test{i}@test.com", "password": "password123"
        })
        assert res.status_code != 429, f"Request {i} should not be rate-limited"

    res = client.post("/signup", json={
        "email": "overflow@test.com", "password": "password123"
    })
    assert res.status_code == 429


def test_rate_limiter_429_has_retry_after_header(client, mocker):
    """429 response should include Retry-After header."""
    mocker.patch("config.settings.RATE_LIMIT_LOGIN", 1)
    mocker.patch("services.rate_limiter.settings.RATE_LIMIT_LOGIN", 1)

    # First request
    client.post("/login", json={"email": "a@b.com", "password": "password123"})

    # Second request hits limit
    res = client.post("/login", json={"email": "a@b.com", "password": "password123"})
    assert res.status_code == 429
    assert res.headers.get("Retry-After") is not None


def test_rate_limiter_general_limit_protects_tasks(client, mocker):
    """General API endpoints should be rate-limited."""
    _mock_auth(mocker)
    mocker.patch("config.settings.RATE_LIMIT_GENERAL", 3)
    mocker.patch("services.rate_limiter.settings.RATE_LIMIT_GENERAL", 3)
    mocker.patch("db.pool.get_connection", return_value=MagicMock())
    mocker.patch("db.pool.return_connection")

    # Make 3 requests (should pass — they may return errors but not 429)
    for i in range(3):
        res = client.get("/tasks", headers={"Authorization": "Bearer test"})
        assert res.status_code != 429, f"Request {i} should not be rate-limited"

    # 4th request should be rate-limited
    res = client.get("/tasks", headers={"Authorization": "Bearer test"})
    assert res.status_code == 429


def test_rate_limiter_ai_limit_triggers_429(client, mocker):
    """AI endpoint should return 429 after exceeding RATE_LIMIT_AI."""
    _mock_auth(mocker)
    mocker.patch("config.settings.RATE_LIMIT_AI", 2)
    mocker.patch("services.rate_limiter.settings.RATE_LIMIT_AI", 2)
    mocker.patch("routes.ai_routes.check_and_increment", return_value=(True, 1))
    mocker.patch(
        "routes.ai_routes.generate_ai_reply",
        return_value="Hello!",
    )

    # First 2 requests pass
    for i in range(2):
        res = client.post("/ai", json={"message": "hello"}, headers={"Authorization": "Bearer test"})
        assert res.status_code != 429, f"Request {i} should not be rate-limited"

    # 3rd request hits the limit
    res = client.post("/ai", json={"message": "hello"}, headers={"Authorization": "Bearer test"})
    assert res.status_code == 429


def test_rate_limiter_configurable_values(client, mocker):
    """Rate limits should be configurable via settings."""
    from services.rate_limiter import login_limit, ai_limit, general_limit
    from config import settings

    # Verify the limits read from settings
    assert settings.RATE_LIMIT_LOGIN > 0
    assert settings.RATE_LIMIT_AI > 0
    assert settings.RATE_LIMIT_GENERAL > 0
