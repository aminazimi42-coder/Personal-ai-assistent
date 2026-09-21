"""
tests/test_auth_service.py
Tests for centralized auth service: token hashing, password, email validation,
token lifecycle, anti-enumeration.
No DB or OpenAI calls.
"""

import hashlib
import pytest
from datetime import datetime, timezone, timedelta

from services.auth_service import (
    generate_raw_token,
    hash_token,
    token_expiry,
    hash_password,
    verify_password,
    validate_email,
    validate_password,
)


# ------------------------------------------------------------------ #
# Token helpers
# ------------------------------------------------------------------ #

def test_generate_raw_token_is_unique():
    t1 = generate_raw_token()
    t2 = generate_raw_token()
    assert t1 != t2
    assert len(t1) >= 32


def test_hash_token_is_sha256():
    raw = "test-token-value"
    expected = hashlib.sha256(raw.encode()).hexdigest()
    assert hash_token(raw) == expected


def test_hash_token_different_inputs():
    assert hash_token("abc") != hash_token("def")


def test_token_expiry_is_future():
    expiry = token_expiry()
    now = datetime.now(timezone.utc)
    assert expiry > now


def test_token_expiry_respects_config():
    from config import settings
    expiry = token_expiry()
    now = datetime.now(timezone.utc)
    delta = (expiry - now).total_seconds()
    assert abs(delta - settings.AUTH_TOKEN_EXPIRY_SECONDS) < 5


# ------------------------------------------------------------------ #
# Password helpers
# ------------------------------------------------------------------ #

def test_hash_password_is_bcrypt():
    hashed = hash_password("mypassword123")
    assert hashed.startswith("$2b$")


def test_verify_password_correct():
    plain = "correctpassword"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_incorrect():
    hashed = hash_password("realpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_verify_password_bad_hash():
    assert verify_password("anything", "not-a-hash") is False


# ------------------------------------------------------------------ #
# Email validation
# ------------------------------------------------------------------ #

def test_validate_email_normalizes():
    assert validate_email("  User@Example.COM  ") == "user@example.com"


def test_validate_email_rejects_empty():
    with pytest.raises(ValueError, match="required"):
        validate_email("")


def test_validate_email_rejects_invalid():
    with pytest.raises(ValueError, match="Invalid email"):
        validate_email("notanemail")


def test_validate_email_rejects_no_at():
    with pytest.raises(ValueError):
        validate_email("missingatdomain.com")


def test_validate_email_rejects_too_long():
    with pytest.raises(ValueError, match="too long"):
        validate_email("a" * 255 + "@example.com")


# ------------------------------------------------------------------ #
# Password validation
# ------------------------------------------------------------------ #

def test_validate_password_accepts_valid():
    result = validate_password("goodpass1")
    assert result == "goodpass1"


def test_validate_password_rejects_short():
    with pytest.raises(ValueError, match="at least 8"):
        validate_password("short")


def test_validate_password_rejects_empty():
    with pytest.raises(ValueError, match="required"):
        validate_password("")


def test_validate_password_rejects_too_long():
    with pytest.raises(ValueError, match="too long"):
        validate_password("x" * 200)
