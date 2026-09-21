"""
tests/test_ai_service.py
Tests for AI service orchestration.
All OpenAI API calls are mocked — no real tokens spent.
"""

import pytest
from unittest.mock import MagicMock, patch
from services.ai_service import (
    _normalize_priority,
    _normalize_status,
    _normalize_due_date,
    _clean_text,
    _extract_json,
)


# ------------------------------------------------------------------ #
# Normalizers
# ------------------------------------------------------------------ #

def test_normalize_priority_valid():
    assert _normalize_priority("high") == "high"
    assert _normalize_priority("LOW") == "low"
    assert _normalize_priority("medium") == "medium"


def test_normalize_priority_invalid():
    assert _normalize_priority("extreme") == "medium"
    assert _normalize_priority(None) == "medium"
    assert _normalize_priority("") == "medium"


def test_normalize_status_valid():
    assert _normalize_status("pending") == "pending"
    assert _normalize_status("done") == "done"
    assert _normalize_status("DONE") == "done"


def test_normalize_status_invalid():
    assert _normalize_status("active") == "pending"
    assert _normalize_status(None) == "pending"


def test_normalize_due_date_none():
    assert _normalize_due_date(None) is None
    assert _normalize_due_date("") is None
    assert _normalize_due_date("null") is None


def test_normalize_due_date_string():
    result = _normalize_due_date("2026-12-31T10:00:00Z")
    assert result == "2026-12-31T10:00:00Z"


def test_normalize_due_date_whitespace():
    assert _normalize_due_date("  ") is None


# ------------------------------------------------------------------ #
# _clean_text
# ------------------------------------------------------------------ #

def test_clean_text_normal():
    assert _clean_text("Hello world") == "Hello world"


def test_clean_text_none():
    result = _clean_text(None)
    assert "sorry" in result.lower() or len(result) > 0


def test_clean_text_escaped_newlines():
    result = _clean_text("line1\\nline2")
    assert "\n" in result


# ------------------------------------------------------------------ #
# _extract_json
# ------------------------------------------------------------------ #

def test_extract_json_valid():
    result = _extract_json('{"action": "reply", "reply": "hello"}')
    assert result["action"] == "reply"


def test_extract_json_embedded():
    result = _extract_json('some text before {"key": "value"} after')
    assert result["key"] == "value"


def test_extract_json_none():
    assert _extract_json(None) is None
    assert _extract_json("") is None
    assert _extract_json("no json here") is None


def test_extract_json_nested():
    result = _extract_json('{"a": {"b": 1}}')
    assert result["a"]["b"] == 1


# ------------------------------------------------------------------ #
# generate_ai_reply — mocked
# ------------------------------------------------------------------ #

def test_generate_ai_reply_success(mocker):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello, I can help you!"
    mock_client.chat.completions.create.return_value = mock_response
    mocker.patch("services.ai_service.get_openai_client", return_value=mock_client)

    from services.ai_service import generate_ai_reply
    result = generate_ai_reply("Hello")
    assert "Hello" in result or len(result) > 0
    # Verify token budget was passed
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert "max_tokens" in call_kwargs


def test_generate_ai_reply_api_failure(mocker):
    mocker.patch(
        "services.ai_service.get_openai_client",
        side_effect=Exception("API down"),
    )
    from services.ai_service import generate_ai_reply
    result = generate_ai_reply("Hello")
    # Should return fallback, not raise
    assert isinstance(result, str)
    assert len(result) > 0


# ------------------------------------------------------------------ #
# decide_smart_action — single call, mocked
# ------------------------------------------------------------------ #

def test_decide_smart_action_task(mocker):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        '{"action":"task","title":"Buy milk","description":"Get milk from store",'
        '"priority":"medium","status":"pending","due_date":null,"reply":""}'
    )
    mock_client.chat.completions.create.return_value = mock_response
    mocker.patch("services.ai_service.get_openai_client", return_value=mock_client)

    from services.ai_service import decide_smart_action
    result = decide_smart_action("I need to buy milk")
    assert result["action"] == "task"
    assert result["title"] == "Buy milk"
    # Must be SINGLE call — not double
    assert mock_client.chat.completions.create.call_count == 1


def test_decide_smart_action_reply(mocker):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        '{"action":"reply","title":"","description":"","priority":"medium",'
        '"status":"pending","due_date":null,"reply":"The weather is nice today."}'
    )
    mock_client.chat.completions.create.return_value = mock_response
    mocker.patch("services.ai_service.get_openai_client", return_value=mock_client)

    from services.ai_service import decide_smart_action
    result = decide_smart_action("What is the weather?")
    assert result["action"] == "reply"
    assert "weather" in result["reply"].lower()
    # Still single call
    assert mock_client.chat.completions.create.call_count == 1


def test_decide_smart_action_api_failure(mocker):
    mocker.patch(
        "services.ai_service.get_openai_client",
        side_effect=Exception("timeout"),
    )
    from services.ai_service import decide_smart_action
    result = decide_smart_action("anything")
    # Must return fallback reply, not raise
    assert result["action"] == "reply"
    assert isinstance(result["reply"], str)
