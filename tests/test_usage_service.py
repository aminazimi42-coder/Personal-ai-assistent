"""
tests/test_usage_service.py
Tests for DB-backed and in-memory AI usage accounting.
"""

import pytest
from unittest.mock import MagicMock, patch
from services.usage_service import (
    check_and_increment,
    get_usage,
    reset_usage,
    _mem_store,
)
from config import settings


def test_check_and_increment_unlimited(mocker):
    """When quota is 0, all requests should be allowed."""
    mocker.patch.object(settings, "AI_DAILY_QUOTA_PER_USER", 0)
    reset_usage(1)
    allowed, count = check_and_increment(1)
    assert allowed is True
    assert count == 1
    allowed, count = check_and_increment(1)
    assert allowed is True
    assert count == 2


def test_check_and_increment_quota_exceeded(mocker):
    """When quota is reached, subsequent requests should be denied."""
    mocker.patch.object(settings, "AI_DAILY_QUOTA_PER_USER", 3)
    reset_usage(2)
    for i in range(3):
        allowed, count = check_and_increment(2)
        assert allowed is True
        assert count == i + 1

    allowed, count = check_and_increment(2)
    assert allowed is False


def test_get_usage_no_data(mocker):
    """get_usage returns 0 when no usage data exists."""
    mocker.patch.object(settings, "AI_DAILY_QUOTA_PER_USER", 10)
    reset_usage(999)
    usage = get_usage(999)
    assert usage["ai_calls_today"] == 0
    assert usage["quota"] == 10
    assert usage["quota_exceeded"] is False


def test_get_usage_with_data(mocker):
    """get_usage returns correct count after increments."""
    mocker.patch.object(settings, "AI_DAILY_QUOTA_PER_USER", 10)
    reset_usage(3)
    check_and_increment(3)
    check_and_increment(3)
    usage = get_usage(3)
    assert usage["ai_calls_today"] == 2
    assert usage["quota_exceeded"] is False


def test_get_usage_quota_exceeded(mocker):
    """get_usage shows quota_exceeded when count reaches quota."""
    mocker.patch.object(settings, "AI_DAILY_QUOTA_PER_USER", 2)
    reset_usage(4)
    check_and_increment(4)
    check_and_increment(4)
    usage = get_usage(4)
    assert usage["ai_calls_today"] == 2
    assert usage["quota_exceeded"] is True


def test_reset_usage(mocker):
    """reset_usage clears all data for a user."""
    mocker.patch.object(settings, "AI_DAILY_QUOTA_PER_USER", 10)
    check_and_increment(5)
    reset_usage(5)
    usage = get_usage(5)
    assert usage["ai_calls_today"] == 0


def test_different_users_independent(mocker):
    """Usage counts should be independent per user."""
    mocker.patch.object(settings, "AI_DAILY_QUOTA_PER_USER", 0)
    reset_usage(10)
    reset_usage(11)
    check_and_increment(10)
    check_and_increment(10)
    check_and_increment(11)
    assert get_usage(10)["ai_calls_today"] == 2
    assert get_usage(11)["ai_calls_today"] == 1


def test_db_fallback_on_error(mocker):
    """When DB is not available, in-memory store should be used."""
    mocker.patch.object(settings, "AI_DAILY_QUOTA_PER_USER", 0)

    # Mock _is_db_available to return False
    mocker.patch("services.usage_service._is_db_available", return_value=False)
    reset_usage(20)
    allowed, count = check_and_increment(20)
    assert allowed is True
    assert count == 1
