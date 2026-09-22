"""
tests/test_security_hardening.py
Regression tests proving raw auth_token is no longer stored or accepted.

Verifies:
  1. get_current_user() query uses ONLY auth_token_hash (no raw auth_token)
  2. signup INSERT does NOT include raw auth_token column
  3. login UPDATE does NOT store raw auth_token
  4. logout UPDATE does NOT clear raw auth_token, only auth_token_hash

These tests inspect the actual SQL passed to the mock cursor to ensure the
legacy raw-token compatibility path is fully removed.
"""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from services.auth_service import hash_token, get_current_user


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _mock_pool_with_conn(mock_conn):
    """Create a mock pool whose getconn() returns mock_conn."""
    pool = MagicMock()
    pool.getconn.return_value = mock_conn
    return pool


# ------------------------------------------------------------------ #
# 1. get_current_user does NOT accept raw tokens
# ------------------------------------------------------------------ #

def test_get_current_user_query_only_uses_auth_token_hash():
    """
    The SQL query in get_current_user must NOT contain 'OR auth_token'.
    It should only match by auth_token_hash.
    """
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur

    with patch("services.auth_service.get_bearer_token", return_value="raw-token-123"):
        with patch("db.pool.return_connection"):
            get_current_user(lambda: conn)

    executed_sql = cur.execute.call_args[0][0].lower()
    assert "or auth_token" not in executed_sql, (
        "get_current_user still accepts raw auth_token via OR clause"
    )
    assert "auth_token_hash" in executed_sql

    params = cur.execute.call_args[0][1]
    assert len(params) == 2, (
        f"Expected 2 params (token_hash, now), got {len(params)}: {params}"
    )


def test_get_current_user_does_not_pass_raw_token_to_query():
    """
    The first parameter to the query must be the hashed token, not the raw.
    """
    raw_token = "my-secret-raw-token"
    expected_hash = hash_token(raw_token)
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur

    with patch("services.auth_service.get_bearer_token", return_value=raw_token):
        with patch("db.pool.return_connection"):
            get_current_user(lambda: conn)

    params = cur.execute.call_args[0][1]
    assert params[0] == expected_hash
    assert params[0] != raw_token


# ------------------------------------------------------------------ #
# 2. Signup INSERT does NOT store raw auth_token
# ------------------------------------------------------------------ #

def test_signup_insert_excludes_raw_auth_token(mocker, client):
    """
    The signup INSERT must not include 'auth_token' (raw) in the column list.
    Only auth_token_hash should be stored.
    """
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    # fetchone side_effect: SELECT existing check (None), INSERT RETURNING (user row)
    mock_cur.fetchone.side_effect = [
        None,
        {"id": 1, "name": "Test", "email": "test@example.com", "created_at": None},
    ]
    mock_conn.cursor.return_value = mock_cur

    mocker.patch("db.pool._pool", _mock_pool_with_conn(mock_conn), create=True)

    res = client.post("/signup", json={
        "email": "test@example.com",
        "password": "password123",
        "name": "Test",
    })

    assert res.status_code == 201, f"Signup failed: {res.get_json()}"

    insert_calls = [
        call for call in mock_cur.execute.call_args_list
        if "INSERT" in str(call).upper()
    ]
    assert len(insert_calls) >= 1, "No INSERT was executed during signup"

    insert_sql = str(insert_calls[0]).upper()
    assert "AUTH_TOKEN_HASH" in insert_sql
    cleaned = insert_sql.replace("AUTH_TOKEN_HASH", "")
    assert "AUTH_TOKEN" not in cleaned, (
        "INSERT must NOT include raw auth_token column"
    )


def test_signup_insert_params_exclude_raw_token(mocker, client):
    """
    The INSERT params must have 5 values (name, email, password, hash, expires)
    not 6 (which would include the raw token).
    """
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.side_effect = [
        None,
        {"id": 1, "name": "Test", "email": "test@example.com", "created_at": None},
    ]
    mock_conn.cursor.return_value = mock_cur

    mocker.patch("db.pool._pool", _mock_pool_with_conn(mock_conn), create=True)

    res = client.post("/signup", json={
        "email": "test@example.com",
        "password": "password123",
        "name": "Test",
    })

    assert res.status_code == 201, f"Signup failed: {res.get_json()}"

    insert_calls = [
        call for call in mock_cur.execute.call_args_list
        if "INSERT" in str(call).upper()
    ]
    params = insert_calls[0][0][1]
    assert len(params) == 5, (
        f"INSERT should have 5 params (no raw token), got {len(params)}: {params}"
    )


# ------------------------------------------------------------------ #
# 3. Login UPDATE does NOT store raw auth_token
# ------------------------------------------------------------------ #

def test_login_update_excludes_raw_auth_token(mocker, client):
    """
    The login UPDATE must not set auth_token (raw), only auth_token_hash.
    """
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    # fetchone for the SELECT user by email query
    mock_cur.fetchone.return_value = {
        "id": 1, "name": "Test", "email": "test@example.com",
        "password": "$2b$12$validhash", "created_at": None,
    }
    mock_conn.cursor.return_value = mock_cur

    mocker.patch("db.pool._pool", _mock_pool_with_conn(mock_conn), create=True)
    # Mock password verification at the route module's binding
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
    assert "AUTH_TOKEN_HASH" in update_sql
    cleaned = update_sql.replace("AUTH_TOKEN_HASH", "")
    assert "AUTH_TOKEN" not in cleaned, (
        "UPDATE must NOT set raw auth_token column"
    )

    params = update_calls[0][0][1]
    assert len(params) == 3, (
        f"UPDATE should have 3 params (hash, expires, id), got {len(params)}: {params}"
    )


# ------------------------------------------------------------------ #
# 4. Logout only clears auth_token_hash
# ------------------------------------------------------------------ #

def test_logout_only_clears_auth_token_hash(mocker, client):
    """
    The logout UPDATE must only clear auth_token_hash, not raw auth_token.
    The WHERE clause must match only by auth_token_hash, not OR auth_token.
    """
    raw_token = "logout-test-token"

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    # fetchone for UPDATE...RETURNING returns a row (revoked)
    mock_cur.fetchone.return_value = {"id": 1}
    mock_conn.cursor.return_value = mock_cur

    mocker.patch("db.pool._pool", _mock_pool_with_conn(mock_conn), create=True)
    mocker.patch("routes.user_routes.get_bearer_token", return_value=raw_token)

    res = client.post("/logout", headers={"Authorization": f"Bearer {raw_token}"})

    assert res.status_code == 200, f"Logout failed: {res.get_json()}"

    update_calls = [
        call for call in mock_cur.execute.call_args_list
        if "UPDATE" in str(call).upper()
    ]
    assert len(update_calls) >= 1, "No UPDATE was executed during logout"

    logout_sql = str(update_calls[0]).upper()
    assert "AUTH_TOKEN_HASH" in logout_sql
    assert "OR AUTH_TOKEN" not in logout_sql, (
        "Logout WHERE clause must not match by raw auth_token"
    )
    cleaned = logout_sql.replace("AUTH_TOKEN_HASH", "")
    assert "AUTH_TOKEN" not in cleaned, (
        "Logout must NOT clear raw auth_token column"
    )

    params = update_calls[0][0][1]
    assert len(params) == 1, (
        f"Logout UPDATE should have 1 param (token_hash), got {len(params)}: {params}"
    )
