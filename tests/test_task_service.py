"""
tests/test_task_service.py
Tests for task service: validation, normalization, serialization.
No DB or OpenAI calls.
"""

import pytest
from datetime import datetime, timezone

from services.task_service import (
    build_task_payload,
    parse_due_date,
    serialize_task,
    normalize_task_priority,
    normalize_task_status,
    validate_task_title,
)


# ------------------------------------------------------------------ #
# build_task_payload
# ------------------------------------------------------------------ #

def test_build_task_payload_valid():
    payload = build_task_payload(
        title="Buy groceries",
        description="Milk and eggs",
        status="pending",
        priority="high",
        user_id=1,
    )
    assert payload["title"] == "Buy groceries"
    assert payload["priority"] == "high"
    assert payload["status"] == "pending"
    assert payload["user_id"] == 1


def test_build_task_payload_requires_title():
    with pytest.raises(ValueError, match="Title is required"):
        build_task_payload(title="", user_id=1)


def test_build_task_payload_requires_user_id():
    with pytest.raises(ValueError, match="user_id is required"):
        build_task_payload(title="Test", user_id=None)


def test_build_task_payload_invalid_user_id():
    with pytest.raises(ValueError, match="user_id must be"):
        build_task_payload(title="Test", user_id=0)


def test_build_task_payload_normalizes_priority():
    payload = build_task_payload(title="T", priority="INVALID", user_id=1)
    assert payload["priority"] == "medium"


def test_build_task_payload_normalizes_status():
    payload = build_task_payload(title="T", status="DONE", user_id=1)
    assert payload["status"] == "done"


# ------------------------------------------------------------------ #
# parse_due_date
# ------------------------------------------------------------------ #

def test_parse_due_date_none():
    assert parse_due_date(None) is None


def test_parse_due_date_empty():
    assert parse_due_date("") is None


def test_parse_due_date_iso():
    dt = parse_due_date("2026-12-31T10:00:00")
    assert isinstance(dt, datetime)
    assert dt.year == 2026


def test_parse_due_date_with_z():
    dt = parse_due_date("2026-12-31T10:00:00Z")
    assert dt is not None


def test_parse_due_date_invalid():
    with pytest.raises(Exception):
        parse_due_date("not-a-date")


# ------------------------------------------------------------------ #
# serialize_task
# ------------------------------------------------------------------ #

def test_serialize_task_converts_datetimes():
    task = {
        "id": 1,
        "title": "Test",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "due_date": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "user_id": 2,
    }
    result = serialize_task(task)
    assert isinstance(result["created_at"], str)
    assert isinstance(result["due_date"], str)


def test_serialize_task_none_due_date():
    task = {"id": 1, "title": "T", "created_at": None, "due_date": None, "user_id": 1}
    result = serialize_task(task)
    assert result["due_date"] is None


# ------------------------------------------------------------------ #
# Normalizers
# ------------------------------------------------------------------ #

def test_normalize_priority_valid():
    assert normalize_task_priority("high") == "high"
    assert normalize_task_priority("LOW") == "low"


def test_normalize_priority_invalid():
    assert normalize_task_priority("extreme") == "medium"


def test_normalize_status_valid():
    assert normalize_task_status("done") == "done"
    assert normalize_task_status("PENDING") == "pending"


def test_normalize_status_invalid():
    assert normalize_task_status("archived") == "pending"
