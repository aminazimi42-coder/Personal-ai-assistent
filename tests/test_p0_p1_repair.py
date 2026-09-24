"""
tests/test_p0_p1_repair.py
Tests for P0/P1 repair batch (from docs/PROJECT_AUDIT.md):

R1 — Session that survives iPhone (P0-1):
  - Login twice without invalidating the first token (two-slot design)
  - get_current_user checks both token slots
  - Logout deletes only the presented token's slot

R2 — Voice becomes text (P0-2):
  - Non-webm MIME is accepted by the validator
  - Quota not incremented when provider is missing (transcribe-voice)
  - Quota not incremented when provider is missing (voice-to-task)

R4 — OpenAPI plan enum:
  - Subscription + SubscriptionCreate schemas include pro_plus
"""

import io
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
from tests.conftest import make_user


# ------------------------------------------------------------------ #
# R1 — Multi-session: login does not wipe the first token
# ------------------------------------------------------------------ #

def test_login_second_session_keeps_first_token(mocker, client):
    """Login on a second device must not overwrite the first device's token.

    The login route should:
    1. Check if the primary slot is still valid.
    2. If yes, use the secondary slot instead of overwriting the primary.
    """
    from services.auth_service import hash_token

    mock_conn = MagicMock()
    mock_cur = MagicMock()

    # First fetchone: SELECT user by email/name → user row
    # Second fetchone: SELECT auth_token_hash, token_expires_at → existing valid hash
    existing_hash = hash_token("first-device-token")
    future = datetime.now(timezone.utc) + timedelta(hours=23)
    mock_cur.fetchone.side_effect = [
        {
            "id": 1,
            "name": "Test",
            "email": "test@example.com",
            "password": "$2b$12$validhash",
            "created_at": None,
        },
        {
            "auth_token_hash": existing_hash,
            "token_expires_at": future,
        },
    ]
    mock_conn.cursor.return_value = mock_cur

    mocker.patch("db.pool._pool", MagicMock(getconn=MagicMock(return_value=mock_conn)), create=True)
    mocker.patch("routes.user_routes.verify_password", return_value=True)

    res = client.post("/login", json={
        "email": "test@example.com",
        "password": "password123",
    })

    assert res.status_code == 200, f"Login failed: {res.get_json()}"

    # Find all UPDATE calls
    update_calls = [
        call for call in mock_cur.execute.call_args_list
        if "UPDATE" in str(call).upper()
    ]
    assert len(update_calls) >= 1, "No UPDATE was executed during login"

    update_sql = str(update_calls[0]).upper()
    # When primary is still valid, the UPDATE must set auth_token_hash_2
    # (the secondary slot), NOT overwrite auth_token_hash.
    assert "AUTH_TOKEN_HASH_2" in update_sql, (
        "Second login should use the secondary slot, not overwrite the primary"
    )


def test_login_first_session_reuses_primary_when_expired(mocker, client):
    """When the primary slot is expired or empty, login reuses it (not secondary)."""
    from services.auth_service import hash_token

    mock_conn = MagicMock()
    mock_cur = MagicMock()

    # First fetchone: SELECT user → user row
    # Second fetchone: SELECT auth_token_hash, token_expires_at → expired
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    mock_cur.fetchone.side_effect = [
        {
            "id": 1,
            "name": "Test",
            "email": "test@example.com",
            "password": "$2b$12$validhash",
            "created_at": None,
        },
        {
            "auth_token_hash": hash_token("old-token"),
            "token_expires_at": past,
        },
    ]
    mock_conn.cursor.return_value = mock_cur

    mocker.patch("db.pool._pool", MagicMock(getconn=MagicMock(return_value=mock_conn)), create=True)
    mocker.patch("routes.user_routes.verify_password", return_value=True)

    res = client.post("/login", json={
        "email": "test@example.com",
        "password": "password123",
    })

    assert res.status_code == 200, f"Login failed: {res.get_json()}"

    update_calls = [
        call for call in mock_cur.execute.call_args_list
        if "UPDATE" in str(call).upper()
    ]
    assert len(update_calls) >= 1, "No UPDATE was executed during login"

    update_sql = str(update_calls[0]).upper()
    # When primary is expired, the UPDATE should set auth_token_hash (primary)
    # and also clear the secondary slot.
    assert "AUTH_TOKEN_HASH " in update_sql or "AUTH_TOKEN_HASH =" in update_sql, (
        "Expired primary should be reused (set auth_token_hash)"
    )
    # Must also clear the secondary slot
    assert "AUTH_TOKEN_HASH_2" in update_sql, (
        "Login should clear the secondary slot when reusing primary"
    )


def test_get_current_user_checks_secondary_slot():
    """get_current_user should find a user via auth_token_hash_2."""
    from services.auth_service import get_current_user

    raw_token = "secondary-device-token"
    expected_hash = hash_token(raw_token) if False else None  # just for clarity

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur

    # First execute (primary) returns None, second (secondary) returns a user
    cur.fetchone.side_effect = [
        None,  # primary slot miss
        {"id": 1, "name": "Test", "email": "t@e.com", "created_at": None, "token_expires_at_2": None},
    ]

    with patch("services.auth_service.get_bearer_token", return_value=raw_token):
        with patch("db.pool.return_connection"):
            user, error, code = get_current_user(lambda: conn)

    assert user is not None, "Should find user in secondary slot"
    assert error is None
    assert user["id"] == 1
    # Two queries should have been made (primary + secondary)
    assert cur.execute.call_count >= 2


def test_logout_clears_secondary_slot(mocker, client):
    """Logout should clear the matching token's slot, whether primary or secondary."""
    from services.auth_service import hash_token

    raw_token = "my-secondary-token"

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    # The rate limiter's before_request hook calls _lookup_user_by_token
    # which consumes one fetchone() call before the route runs.
    # Then the route's primary UPDATE...RETURNING fetchone → None,
    # and the secondary UPDATE...RETURNING fetchone → {"id": 1}.
    mock_cur.fetchone.side_effect = [
        None,        # rate limiter _lookup_user_by_token primary SELECT → miss
        None,        # rate limiter _lookup_user_by_token secondary SELECT → miss
        None,        # primary slot UPDATE...RETURNING → no row
        {"id": 1},   # secondary slot UPDATE...RETURNING → revoked
    ]
    mock_conn.cursor.return_value = mock_cur

    pool_mock = MagicMock()
    pool_mock.getconn.return_value = mock_conn
    mocker.patch("db.pool._pool", pool_mock, create=True)
    mocker.patch("routes.user_routes.get_bearer_token", return_value=raw_token)

    res = client.post("/logout", headers={"Authorization": f"Bearer {raw_token}"})

    assert res.status_code == 200, f"Logout failed: {res.get_json()}"

    update_calls = [
        call for call in mock_cur.execute.call_args_list
        if "UPDATE" in str(call).upper()
    ]
    assert len(update_calls) >= 2, "Should try primary then secondary slot"

    # The second UPDATE should reference auth_token_hash_2
    second_update = str(update_calls[1]).upper()
    assert "AUTH_TOKEN_HASH_2" in second_update, (
        "Logout should clear the secondary slot when primary doesn't match"
    )


# ------------------------------------------------------------------ #
# R2 — Voice: non-webm MIME accepted; quota not incremented when
#      provider is missing
# ------------------------------------------------------------------ #

def test_voice_mime_accepts_mp4():
    """audio/mp4 MIME should be in the allowlist (already true — verify)."""
    import config.settings as s
    assert "audio/mp4" in s.ALLOWED_AUDIO_MIME_TYPES
    assert "video/mp4" in s.ALLOWED_AUDIO_MIME_TYPES


def test_transcribe_voice_provider_missing_no_quota(client, mocker):
    """When the AI provider is not configured, the 503 must be returned
    BEFORE quota is incremented — no quota consumed."""
    u = make_user()
    mocker.patch("routes.ai_routes.get_current_user", return_value=(u, None, None))
    mocker.patch("routes.ai_routes.assert_entitlement", return_value=True)
    mocker.patch("routes.ai_routes._ai_provider_configured", return_value=False)
    mock_check = mocker.patch(
        "routes.ai_routes.check_and_increment",
        return_value=(True, 1),
    )

    audio_bytes = b"\x00" * 100
    res = client.post(
        "/transcribe-voice",
        data={"audio": (io.BytesIO(audio_bytes), "test.webm", "audio/webm")},
        content_type="multipart/form-data",
    )

    assert res.status_code == 503
    data = res.get_json()
    assert data["status"] == "error"
    assert "not configured" in data["message"].lower()
    # Quota must NOT have been incremented
    mock_check.assert_not_called()


def test_voice_to_task_provider_missing_no_quota(client, mocker):
    """voice-to-task: 503 before quota when provider is missing."""
    u = make_user()
    mocker.patch("routes.ai_routes.get_current_user", return_value=(u, None, None))
    mocker.patch("routes.ai_routes.assert_entitlement", return_value=True)
    mocker.patch("routes.ai_routes._ai_provider_configured", return_value=False)
    mock_check = mocker.patch(
        "routes.ai_routes.check_and_increment",
        return_value=(True, 1),
    )

    audio_bytes = b"\x00" * 100
    res = client.post(
        "/voice-to-task",
        data={"audio": (io.BytesIO(audio_bytes), "test.mp4", "audio/mp4")},
        content_type="multipart/form-data",
    )

    assert res.status_code == 503
    data = res.get_json()
    assert data["status"] == "error"
    assert "not configured" in data["message"].lower()
    mock_check.assert_not_called()


# ------------------------------------------------------------------ #
# R4 — OpenAPI Subscription enum includes pro_plus
# ------------------------------------------------------------------ #

def test_openapi_subscription_enum_has_pro_plus(client):
    """OpenAPI Subscription schema must list pro_plus in the plan enum."""
    res = client.get("/api/v1/openapi.json")
    assert res.status_code == 200
    spec = res.get_json()
    sub_schema = spec["components"]["schemas"]["Subscription"]
    plan_enum = sub_schema["properties"]["plan"]["enum"]
    assert "pro_plus" in plan_enum, (
        f"Subscription enum should include pro_plus, got: {plan_enum}"
    )
    assert "free" in plan_enum
    assert "pro" in plan_enum


def test_openapi_subscription_create_enum_has_pro_plus(client):
    """OpenAPI SubscriptionCreate schema must list pro_plus in the plan enum."""
    res = client.get("/api/v1/openapi.json")
    assert res.status_code == 200
    spec = res.get_json()
    sub_create = spec["components"]["schemas"]["SubscriptionCreate"]
    plan_enum = sub_create["properties"]["plan"]["enum"]
    assert "pro_plus" in plan_enum, (
        f"SubscriptionCreate enum should include pro_plus, got: {plan_enum}"
    )
