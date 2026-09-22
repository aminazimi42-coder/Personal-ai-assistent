"""
tests/test_privacy_operations.py
Tests for privacy operations: export, delete, safe logging, AI boundary.
"""

import os
import pytest
from unittest.mock import MagicMock

# Set test env before imports
os.environ.setdefault("DATABASE_URL", "postgresql://test:***@localhost/testdb")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5000")

from services.privacy import (
    DataCategory,
    DataClassification,
    export_user_data,
    delete_user_account,
    delete_memory_data,
    privacy_safe_log,
    get_privacy_policy,
    enforce_ai_data_boundary,
    clear_audit_log,
)
from services.memory_engine import set_memory, clear_user_memories
from services.cost_intelligence import (
    reset_cache_stats,
    get_cache_stats,
    record_cache_hit,
    record_cache_miss,
)


# ------------------------------------------------------------------ #
# Export
# ------------------------------------------------------------------ #

def test_export_user_data_structure():
    """Export returns a dict with all expected keys."""
    clear_user_memories(1)
    data = export_user_data(1, None)
    assert isinstance(data, dict)
    assert "user_id" in data
    assert "profile" in data
    assert "tasks" in data
    assert "appointments" in data
    assert "memories" in data
    assert "usage" in data
    assert "agent_runs" in data
    assert "automations" in data
    assert "exported_at" in data


def test_export_user_data_empty():
    """Export for a non-existent user returns empty data."""
    data = export_user_data(99999, None)
    assert data["profile"] is None
    assert data["tasks"] == []
    assert data["appointments"] == []
    assert data["memories"] == []


def test_export_user_data_with_memories():
    """Export includes memories from the in-memory store."""
    clear_user_memories(1)
    set_memory(1, "preference", "theme", "dark")
    data = export_user_data(1, None)
    assert len(data["memories"]) >= 1
    mem = data["memories"][0]
    assert mem["key"] == "theme"
    assert mem["value"] == "dark"


def test_export_user_data_exported_at_is_iso():
    """Exported_at should be an ISO timestamp string."""
    data = export_user_data(1, None)
    assert len(data["exported_at"]) > 0
    # Should contain 'T' (ISO format)
    assert "T" in data["exported_at"]


def test_export_with_mock_connection():
    """Export with a mock connection fetches from DB."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "created_at": None,
    }
    mock_cur.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cur

    mock_get_conn = MagicMock(return_value=mock_conn)

    data = export_user_data(1, mock_get_conn)
    assert data["profile"] is not None
    assert data["profile"]["name"] == "Test User"


# ------------------------------------------------------------------ #
# Delete account
# ------------------------------------------------------------------ #

def test_delete_account_requires_confirm():
    """Delete account without confirm should return False."""
    result = delete_user_account(1, None, confirm=False)
    assert result is False


def test_delete_account_no_connection():
    """Delete account without a DB connection should return False."""
    result = delete_user_account(1, None, confirm=True)
    assert result is False


def test_delete_account_with_mock():
    """Delete account with a mock DB connection."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.rowcount = 1  # 1 row deleted
    mock_conn.cursor.return_value = mock_cur
    mock_get_conn = MagicMock(return_value=mock_conn)

    result = delete_user_account(1, mock_get_conn, confirm=True)
    assert result is True
    # Verify DELETE was called
    # Check that cur.execute was called with DELETE FROM users
    calls = [str(c) for c in mock_cur.execute.call_args_list]
    assert any("DELETE FROM users" in c for c in calls)


def test_delete_account_mock_no_rows():
    """Delete account for non-existent user returns False."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.rowcount = 0
    mock_conn.cursor.return_value = mock_cur
    mock_get_conn = MagicMock(return_value=mock_conn)

    result = delete_user_account(99999, mock_get_conn, confirm=True)
    assert result is False


# ------------------------------------------------------------------ #
# Delete memory
# ------------------------------------------------------------------ #

def test_delete_memory_data():
    """Delete all memories for a user."""
    clear_user_memories(1)
    set_memory(1, "preference", "key1", "val1")
    set_memory(1, "preference", "key2", "val2")
    result = delete_memory_data(1, None)
    assert result is True


def test_delete_memory_data_empty():
    """Delete memories for user with no memories returns False."""
    clear_user_memories(999)
    result = delete_memory_data(999, None)
    assert result is False


# ------------------------------------------------------------------ #
# Privacy-safe logging
# ------------------------------------------------------------------ #

def test_privacy_safe_log_masks_password():
    """Sensitive keys should be masked."""
    result = privacy_safe_log("User login", password="mysecret123")
    assert "mysecret123" not in result
    assert "****" in result


def test_privacy_safe_log_masks_token():
    result = privacy_safe_log("Auth", token="sk-abc123def456")
    assert "sk-abc123def456" not in result
    assert "****" in result


def test_privacy_safe_log_masks_api_key():
    result = privacy_safe_log("API call", api_key="secret-key-xyz")
    assert "secret-key-xyz" not in result


def test_privacy_safe_log_preserves_safe_keys():
    """Non-sensitive keys should be preserved."""
    result = privacy_safe_log("Request", user_id=42, method="GET")
    assert "42" in result
    assert "GET" in result


def test_privacy_safe_log_masks_email():
    """Email values should be masked."""
    result = privacy_safe_log("Send", to="user@example.com")
    assert "user@example.com" not in result
    # Should contain the domain
    assert "example.com" in result


def test_privacy_safe_log_returns_string():
    result = privacy_safe_log("Test message", foo="bar")
    assert isinstance(result, str)
    assert "Test message" in result


def test_privacy_safe_log_empty_kwargs():
    result = privacy_safe_log("Just a message")
    assert result == "Just a message"


def test_privacy_safe_log_authorization_header():
    result = privacy_safe_log("Request", authorization="Bearer abc123")
    assert "abc123" not in result


# ------------------------------------------------------------------ #
# AI data boundary
# ------------------------------------------------------------------ #

def test_ai_boundary_auth_tokens_forbidden():
    """Auth tokens should not be allowed in AI context."""
    assert enforce_ai_data_boundary(DataCategory.AUTH_TOKENS) is False


def test_ai_boundary_voice_recordings_forbidden():
    assert enforce_ai_data_boundary(DataCategory.VOICE_RECORDINGS) is False


def test_ai_boundary_usage_data_forbidden():
    assert enforce_ai_data_boundary(DataCategory.USAGE_DATA) is False


def test_ai_boundary_user_profile_allowed():
    assert enforce_ai_data_boundary(DataCategory.USER_PROFILE) is True


def test_ai_boundary_task_data_allowed():
    assert enforce_ai_data_boundary(DataCategory.TASK_DATA) is True


def test_ai_boundary_ai_conversation_allowed():
    assert enforce_ai_data_boundary(DataCategory.AI_CONVERSATION) is True


def test_ai_boundary_memory_allowed():
    assert enforce_ai_data_boundary(DataCategory.MEMORY) is True


def test_ai_boundary_returns_bool():
    result = enforce_ai_data_boundary(DataCategory.USER_PROFILE)
    assert isinstance(result, bool)


# ------------------------------------------------------------------ #
# Privacy policy
# ------------------------------------------------------------------ #

def test_privacy_policy_structure():
    policy = get_privacy_policy()
    assert isinstance(policy, dict)
    assert "version" in policy
    assert "title" in policy
    assert "description" in policy
    assert "data_categories" in policy
    assert "principles" in policy
    assert "user_rights" in policy


def test_privacy_policy_has_categories():
    policy = get_privacy_policy()
    categories = policy["data_categories"]
    assert len(categories) > 0
    for cat in categories:
        assert "category" in cat
        assert "classification" in cat
        assert "retention_days" in cat


def test_privacy_policy_local_processing():
    policy = get_privacy_policy()
    assert "local_processing" in policy
    assert policy["local_processing"]["available"] is False


def test_privacy_policy_user_rights():
    policy = get_privacy_policy()
    rights = policy["user_rights"]
    assert "export" in rights
    assert "delete_account" in rights
