"""
tests/test_api_routes.py
Integration-style tests for API routes using Flask test client.
All DB and OpenAI calls are mocked — no real infrastructure needed.
"""

import pytest
from unittest.mock import MagicMock, patch
from tests.conftest import make_user


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def auth_headers(token="test-token-123"):
    return {"Authorization": f"Bearer {token}"}


# Route modules bind get_current_user at import time, so we must patch
# each module's local reference — not the source module.
_AUTH_TARGETS = [
    "routes.task_routes.get_current_user",
    "routes.calendar_routes.get_current_user",
    "routes.ai_routes.get_current_user",
    "routes.reminder_routes.get_current_user",
]


def mock_auth(mocker, user=None):
    """Patch get_current_user in every route module that imported it."""
    u = user or make_user()
    for target in _AUTH_TARGETS:
        mocker.patch(target, return_value=(u, None, None))
    return u


# ------------------------------------------------------------------ #
# Health / ready
# ------------------------------------------------------------------ #

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"


def test_app_info(client):
    res = client.get("/app-info")
    assert res.status_code == 200
    data = res.get_json()
    assert data["name"] == "Personal AI Assistant"
    assert "version" in data


# ------------------------------------------------------------------ #
# Auth: signup validation
# ------------------------------------------------------------------ #

def test_signup_missing_body(client):
    res = client.post("/signup")
    assert res.status_code == 400


def test_signup_invalid_email(client):
    res = client.post("/signup",
        json={"email": "not-an-email", "password": "password123"})
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"


def test_signup_short_password(client):
    res = client.post("/signup",
        json={"email": "test@example.com", "password": "short"})
    assert res.status_code == 400
    data = res.get_json()
    assert "8 characters" in data["message"]


# ------------------------------------------------------------------ #
# Auth: login validation
# ------------------------------------------------------------------ #

def test_login_missing_body(client):
    res = client.post("/login")
    assert res.status_code == 400


def test_login_missing_identifier(client):
    """Login must require an identifier (email or username)."""
    res = client.post("/login", json={"password": "password123"})
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"
    assert "required" in data["message"].lower()


def test_login_missing_password(client):
    """Login must require a password."""
    res = client.post("/login", json={"identifier": "test@example.com"})
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"
    assert "password" in data["message"].lower()


def test_login_accepts_username_identifier(mocker, client):
    """Login should accept a username (non-email) as the identifier, not just email."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {
        "id": 1, "name": "testuser", "email": "test@example.com",
        "password": "$2b$12$validhash", "created_at": None,
    }
    mock_conn.cursor.return_value = mock_cur

    mocker.patch("db.pool._pool", MagicMock(getconn=MagicMock(return_value=mock_conn)), create=True)
    mocker.patch("routes.user_routes.verify_password", return_value=True)

    res = client.post("/login", json={
        "identifier": "testuser",
        "password": "password123",
    })

    assert res.status_code == 200, f"Login by username failed: {res.get_json()}"
    data = res.get_json()
    assert data["status"] == "success"
    assert data["user"]["token"]


def test_login_accepts_email_identifier(mocker, client):
    """Login should still accept an email address as the identifier."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {
        "id": 1, "name": "Test", "email": "test@example.com",
        "password": "$2b$12$validhash", "created_at": None,
    }
    mock_conn.cursor.return_value = mock_cur

    mocker.patch("db.pool._pool", MagicMock(getconn=MagicMock(return_value=mock_conn)), create=True)
    mocker.patch("routes.user_routes.verify_password", return_value=True)

    res = client.post("/login", json={
        "identifier": "test@example.com",
        "password": "password123",
    })

    assert res.status_code == 200, f"Login by email failed: {res.get_json()}"
    data = res.get_json()
    assert data["status"] == "success"
    assert data["user"]["token"]


def test_login_invalid_credentials_returns_401(mocker, client):
    """Login with wrong password should return 401 with a server message."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {
        "id": 1, "name": "testuser", "email": "test@example.com",
        "password": "$2b$12$validhash", "created_at": None,
    }
    mock_conn.cursor.return_value = mock_cur

    mocker.patch("db.pool._pool", MagicMock(getconn=MagicMock(return_value=mock_conn)), create=True)
    mocker.patch("routes.user_routes.verify_password", return_value=False)

    res = client.post("/login", json={
        "identifier": "testuser",
        "password": "wrongpassword",
    })

    assert res.status_code == 401
    data = res.get_json()
    assert data["status"] == "error"
    assert data["message"]  # must have a real server message, not empty


def test_login_no_password_logs_no_password(mocker, client, caplog):
    """Login route must never log the password value."""
    import logging
    caplog.set_level(logging.DEBUG)
    res = client.post("/login", json={
        "identifier": "test@example.com",
        "password": "secretpass123",
    })
    # This will be 401/500 (DB mocked), but the password must never appear in logs
    for record in caplog.records:
        assert "secretpass123" not in record.getMessage(), (
            "Password was logged — security violation"
        )


# ------------------------------------------------------------------ #
# Task endpoints — unauthenticated
# ------------------------------------------------------------------ #

def test_get_tasks_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.get("/tasks")
    assert res.status_code == 401
    data = res.get_json()
    assert data["status"] == "error"


def test_create_task_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.post("/tasks", json={"title": "Test task"})
    assert res.status_code == 401


def test_create_task_no_body(client, mocker):
    mock_auth(mocker)
    mocker.patch("db.pool.get_connection", return_value=MagicMock())
    mocker.patch("db.pool.return_connection")
    res = client.post("/tasks")  # no Content-Type, no JSON
    assert res.status_code == 400


def test_create_task_empty_title(client, mocker):
    mock_auth(mocker)
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None
    mock_conn.cursor.return_value = mock_cur
    mocker.patch("db.pool.get_connection", return_value=mock_conn)
    mocker.patch("db.pool.return_connection")
    res = client.post("/tasks", json={"title": ""})
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"


# ------------------------------------------------------------------ #
# Appointment endpoints — unauthenticated
# ------------------------------------------------------------------ #

def test_get_appointments_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.get("/appointments")
    assert res.status_code == 401


def test_create_appointment_missing_time(client, mocker):
    mock_auth(mocker)
    mocker.patch("db.pool.get_connection", return_value=MagicMock())
    mocker.patch("db.pool.return_connection")
    res = client.post("/appointments", json={"title": "Meeting"})
    # appointment_time is missing → should be 400
    assert res.status_code == 400


# ------------------------------------------------------------------ #
# AI endpoints — unauthenticated
# ------------------------------------------------------------------ #

def test_ai_chat_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.post("/ai", json={"message": "hello"})
    assert res.status_code == 401


def test_smart_ai_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.post("/smart-ai", json={"message": "hello"})
    assert res.status_code == 401


def test_ai_message_too_long(client, mocker):
    mock_auth(mocker)
    long_msg = "x" * 5000
    res = client.post("/ai", json={"message": long_msg})
    assert res.status_code == 400
    data = res.get_json()
    assert "too long" in data["message"]


def test_smart_ai_empty_message(client, mocker):
    mock_auth(mocker)
    res = client.post("/smart-ai", json={"message": ""})
    assert res.status_code == 400


# ------------------------------------------------------------------ #
# AI endpoints — mocked OpenAI (no cost)
# ------------------------------------------------------------------ #

def test_ai_chat_mocked_reply(client, mocker):
    mock_auth(mocker)
    # Patch at the route module level (local import binding)
    mocker.patch(
        "routes.ai_routes.generate_ai_reply",
        return_value="Hello! How can I help you?",
    )
    res = client.post("/ai", json={"message": "Hello AI"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "Hello" in data["reply"]


def test_smart_ai_mocked_reply(client, mocker):
    mock_auth(mocker)
    # Patch at the route module level (local import binding)
    mocker.patch(
        "routes.ai_routes.decide_smart_action",
        return_value={
            "action": "reply",
            "reply": "Sounds like a great plan!",
            "title": "", "description": "", "priority": "medium",
            "status": "pending", "due_date": None,
        },
    )
    res = client.post("/smart-ai", json={"message": "Tell me a joke"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["action"] == "reply"
    assert "Sounds" in data["reply"]


# ------------------------------------------------------------------ #
# Voice upload validation
# ------------------------------------------------------------------ #

def test_transcribe_voice_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.post("/transcribe-voice")
    assert res.status_code == 401


def test_transcribe_voice_no_file(client, mocker):
    mock_auth(mocker)
    res = client.post("/transcribe-voice")
    assert res.status_code == 400
    assert "Audio file is required" in res.get_json()["message"]


# ------------------------------------------------------------------ #
# CORS headers
# ------------------------------------------------------------------ #

def test_cors_disallows_unknown_origin(client):
    res = client.get("/health", headers={"Origin": "https://evil.com"})
    assert "Access-Control-Allow-Origin" not in res.headers or \
           res.headers.get("Access-Control-Allow-Origin") != "https://evil.com"


def test_cors_allows_configured_origin(client):
    res = client.get("/health", headers={"Origin": "http://localhost:5000"})
    assert res.headers.get("Access-Control-Allow-Origin") == "http://localhost:5000"


# ------------------------------------------------------------------ #
# Security headers
# ------------------------------------------------------------------ #

def test_security_headers_present(client):
    res = client.get("/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"


# ------------------------------------------------------------------ #
# Error handlers
# ------------------------------------------------------------------ #

def test_404_returns_json(client):
    res = client.get("/this-route-does-not-exist")
    assert res.status_code == 404
    data = res.get_json()
    assert data["status"] == "error"
    assert data["message"] == "Not found"
