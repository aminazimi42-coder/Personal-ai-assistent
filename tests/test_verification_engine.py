"""
tests/test_verification_engine.py
Tests for AI reliability / verification engine.
"""

import os
import tempfile
import pytest
from services.verification_engine import (
    verify_file_exists, verify_file_content, verify_callable,
    VerificationStatus, VerificationResult, no_fabricated_success,
)


def test_verify_file_exists_true():
    with tempfile.NamedTemporaryFile() as f:
        result = verify_file_exists(f.name)
        assert result.status == VerificationStatus.VERIFIED
        assert result.checks_passed == 1

def test_verify_file_exists_false():
    result = verify_file_exists("/nonexistent/path/12345")
    assert result.status == VerificationStatus.FAILED
    assert "not found" in result.error.lower()

def test_verify_file_content_found():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def hello(): pass\n")
        f.flush()
        path = f.name
    try:
        result = verify_file_content(path, "def hello")
        assert result.status == VerificationStatus.VERIFIED
    finally:
        os.unlink(path)

def test_verify_file_content_not_found():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("nothing here\n")
        path = f.name
    try:
        result = verify_file_content(path, "nonexistent_text")
        assert result.status == VerificationStatus.FAILED
    finally:
        os.unlink(path)

def test_verify_callable_success():
    def add(a, b):
        return a + b
    result = verify_callable(add, args=(1, 2), expected_result=3)
    assert result.status == VerificationStatus.VERIFIED
    assert result.checks_passed == 1

def test_verify_callable_failure():
    def fail():
        raise ValueError("test error")
    result = verify_callable(fail)
    assert result.status == VerificationStatus.FAILED
    assert "test error" in result.error

def test_verify_callable_partial():
    def returns_wrong():
        return "wrong"
    result = verify_callable(returns_wrong, expected_result="right")
    assert result.status == VerificationStatus.PARTIAL

def test_no_fabricated_success_verified():
    result = VerificationResult(
        action="test", status=VerificationStatus.VERIFIED,
        evidence=["ok"], checks_passed=1, checks_total=1,
    )
    assert no_fabricated_success(result) is True

def test_no_fabricated_success_verified_no_evidence():
    """A verified result without evidence should not pass the check."""
    result = VerificationResult(
        action="test", status=VerificationStatus.VERIFIED,
        evidence=[], checks_passed=0, checks_total=1,
    )
    assert no_fabricated_success(result) is False

def test_verification_status_values():
    assert VerificationStatus.PENDING.value == "pending"
    assert VerificationStatus.VERIFIED.value == "verified"
    assert VerificationStatus.PARTIAL.value == "partial"
    assert VerificationStatus.FAILED.value == "failed"

def test_verification_result_to_dict():
    result = VerificationResult(action="test", status=VerificationStatus.VERIFIED)
    d = result.to_dict()
    assert "action" in d
    assert "status" in d
    assert d["status"] == "verified"
