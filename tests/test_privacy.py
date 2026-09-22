"""
tests/test_privacy.py
Tests for privacy-first architecture: data classification, policies, audit.
"""

import pytest
from services.privacy import (
    DataCategory, DataClassification,
    get_data_policy, classify_data, is_ai_training_eligible,
    is_user_deletable, is_local_processing_available,
    log_data_access, get_audit_log, clear_audit_log,
    anonymize_value, hash_for_audit,
)


def test_data_classification_exists():
    assert DataClassification.PUBLIC.value == "public"
    assert DataClassification.RESTRICTED.value == "restricted"

def test_data_categories_exist():
    assert DataCategory.USER_PROFILE.value == "user_profile"
    assert DataCategory.AUTH_TOKENS.value == "auth_tokens"
    assert DataCategory.MEMORY.value == "memory"

def test_get_data_policy():
    policy = get_data_policy(DataCategory.USER_PROFILE)
    assert policy.category == DataCategory.USER_PROFILE
    assert policy.classification == DataClassification.CONFIDENTIAL

def test_classify_data():
    assert classify_data(DataCategory.AUTH_TOKENS) == DataClassification.RESTRICTED
    assert classify_data(DataCategory.TASK_DATA) == DataClassification.INTERNAL

def test_auth_tokens_not_ai_training_eligible():
    assert is_ai_training_eligible(DataCategory.AUTH_TOKENS) is False

def test_no_data_is_ai_training_eligible():
    """No data category should be AI training eligible by default."""
    for cat in DataCategory:
        assert is_ai_training_eligible(cat) is False

def test_user_deletable():
    assert is_user_deletable(DataCategory.USER_PROFILE) is True
    assert is_user_deletable(DataCategory.USAGE_DATA) is False

def test_local_processing_not_available():
    """Local processing should NOT be available — not implemented."""
    assert is_local_processing_available() is False

def test_audit_log():
    clear_audit_log()
    log_data_access(1, DataCategory.MEMORY, "read", True, "test read")
    log = get_audit_log(1)
    assert len(log) == 1
    assert log[0]["user_id"] == 1
    assert log[0]["action"] == "read"

def test_audit_log_user_isolation():
    clear_audit_log()
    log_data_access(1, DataCategory.MEMORY, "read")
    log_data_access(2, DataCategory.MEMORY, "read")
    log1 = get_audit_log(1)
    log2 = get_audit_log(2)
    assert all(e["user_id"] == 1 for e in log1)
    assert all(e["user_id"] == 2 for e in log2)

def test_anonymize_value():
    anon = anonymize_value("secretpassword123")
    assert "secretpassword123" not in anon
    assert "*" in anon

def test_anonymize_value_short():
    anon = anonymize_value("ab")
    assert "*" in anon
    assert "ab" not in anon

def test_anonymize_value_empty():
    assert anonymize_value("") == ""

def test_hash_for_audit():
    h = hash_for_audit("sensitive data")
    assert len(h) == 16
    assert h != "sensitive data"

def test_hash_for_audit_different_inputs():
    h1 = hash_for_audit("data1")
    h2 = hash_for_audit("data2")
    assert h1 != h2

def test_voice_recordings_restricted():
    """Voice recordings should be classified as restricted."""
    policy = get_data_policy(DataCategory.VOICE_RECORDINGS)
    assert policy.classification == DataClassification.RESTRICTED
    assert policy.retention_days == 1  # Deleted immediately after transcription
