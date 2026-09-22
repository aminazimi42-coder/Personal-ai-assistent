"""
services/verification_engine.py
AI Reliability / Verification Engine — never claim success without evidence.

Flow: ACTION → EXECUTION → VERIFICATION → EVIDENCE → RESULT

Supports structured result states, failure/partial-success reporting,
and no fabricated success.
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class VerificationStatus(Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    PARTIAL = "partial"
    FAILED = "failed"
    UNVERIFIED = "unverified"


@dataclass
class VerificationResult:
    """Result of an AI action with verification."""
    action: str
    status: VerificationStatus
    evidence: list[str] = field(default_factory=list)
    result: Any = None
    error: Optional[str] = None
    checks_passed: int = 0
    checks_total: int = 0

    @property
    def all_passed(self) -> bool:
        return self.status == VerificationStatus.VERIFIED

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "status": self.status.value,
            "evidence": self.evidence,
            "error": self.error,
            "checks_passed": self.checks_passed,
            "checks_total": self.checks_total,
        }


def verify_file_exists(path: str) -> VerificationResult:
    """Verify that a file exists at the given path."""
    result = VerificationResult(
        action="file_exists",
        status=VerificationStatus.PENDING,
        checks_total=1,
    )
    if os.path.exists(path):
        result.status = VerificationStatus.VERIFIED
        result.checks_passed = 1
        result.evidence.append(f"File exists: {path}")
    else:
        result.status = VerificationStatus.FAILED
        result.error = f"File not found: {path}"
    return result


def verify_file_content(path: str, expected_substring: str) -> VerificationResult:
    """Verify that a file contains expected content."""
    result = VerificationResult(
        action="file_content",
        status=VerificationStatus.PENDING,
        checks_total=1,
    )
    try:
        with open(path, "r") as f:
            content = f.read()
        if expected_substring in content:
            result.status = VerificationStatus.VERIFIED
            result.checks_passed = 1
            result.evidence.append(f"Content match found in {path}")
        else:
            result.status = VerificationStatus.FAILED
            result.error = f"Expected content not found in {path}"
    except Exception as exc:
        result.status = VerificationStatus.FAILED
        result.error = str(exc)
    return result


def verify_callable(
    fn: Callable,
    args: tuple = (),
    kwargs: dict = None,
    expected_result: Any = None,
) -> VerificationResult:
    """Verify that a callable returns the expected result."""
    result = VerificationResult(
        action="callable_execution",
        status=VerificationStatus.PENDING,
        checks_total=1,
    )
    try:
        actual = fn(*args, **(kwargs or {}))
        if expected_result is not None and actual == expected_result:
            result.status = VerificationStatus.VERIFIED
            result.checks_passed = 1
            result.evidence.append(f"Callable returned expected result: {expected_result}")
        elif expected_result is None:
            result.status = VerificationStatus.VERIFIED
            result.checks_passed = 1
            result.evidence.append("Callable executed successfully")
            result.result = actual
        else:
            result.status = VerificationStatus.PARTIAL
            result.error = f"Expected {expected_result}, got {actual}"
    except Exception as exc:
        result.status = VerificationStatus.FAILED
        result.error = str(exc)
    return result


def verify_db_row_exists(
    table: str,
    conditions: dict,
    get_connection_fn: Optional[Callable] = None,
) -> VerificationResult:
    """Verify that a row exists in the database matching conditions."""
    result = VerificationResult(
        action="db_row_exists",
        status=VerificationStatus.PENDING,
        checks_total=1,
    )
    if get_connection_fn is None:
        result.status = VerificationStatus.UNVERIFIED
        result.error = "No DB connection available for verification"
        return result
    try:
        from db.pool import return_connection
        conn = get_connection_fn()
        cur = conn.cursor()
        where_clause = " AND ".join(f"{k} = %s" for k in conditions)
        cur.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {where_clause}",
            tuple(conditions.values()),
        )
        count = cur.fetchone()[0]
        cur.close()
        return_connection(conn)
        if count > 0:
            result.status = VerificationStatus.VERIFIED
            result.checks_passed = 1
            result.evidence.append(f"Found {count} rows in {table}")
        else:
            result.status = VerificationStatus.FAILED
            result.error = f"No rows found in {table}"
    except Exception as exc:
        result.status = VerificationStatus.FAILED
        result.error = str(exc)
    return result


def no_fabricated_success(result: VerificationResult) -> bool:
    """
    Ensure that a verification result has not fabricated success.
    A verified result must have at least one piece of evidence and
    at least one passed check.
    """
    if result.status == VerificationStatus.VERIFIED:
        return len(result.evidence) > 0 and result.checks_passed > 0
    if result.status == VerificationStatus.PARTIAL:
        return result.error is not None
    return True
