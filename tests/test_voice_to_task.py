"""
tests/test_voice_to_task.py
Tests for voice-to-task pipeline: MIME validation, task extraction,
confirmation flow, quota enforcement.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from services import voice_to_task as v2t


# ------------------------------------------------------------------ #
# MIME validation
# ------------------------------------------------------------------ #

def test_validate_mime_valid():
    v2t._validate_mime("audio/webm")  # should not raise


def test_validate_mime_invalid():
    with pytest.raises(ValueError, match="Unsupported"):
        v2t._validate_mime("image/png")


def test_validate_mime_empty():
    with pytest.raises(ValueError, match="Content-Type is required"):
        v2t._validate_mime("")


# ------------------------------------------------------------------ #
# Size validation
# ------------------------------------------------------------------ #

def test_validate_size_valid():
    v2t._validate_size(b"\x00" * 100)  # should not raise


def test_validate_size_empty():
    with pytest.raises(ValueError, match="empty"):
        v2t._validate_size(b"")


def test_validate_size_too_large():
    # Patch the max bytes to a small value for testing
    original = v2t._MAX_UPLOAD_BYTES
    v2t._MAX_UPLOAD_BYTES = 100
    try:
        with pytest.raises(ValueError, match="too large"):
            v2t._validate_size(b"\x00" * 200)
    finally:
        v2t._MAX_UPLOAD_BYTES = original


# ------------------------------------------------------------------ #
# process_voice_to_task — full flow with mocks
# ------------------------------------------------------------------ #

def test_process_voice_to_task_success():
    mock_conn = MagicMock()
    # Quota check returns (allowed=True, count=1)
    with patch("services.voice_to_task.check_and_increment", return_value=(True, 1)):
        with patch("services.voice_to_task._transcribe_audio", return_value="Buy milk tomorrow"):
            with patch("services.voice_to_task._extract_task_from_transcript", return_value={
                "title": "Buy milk",
                "description": "Buy milk from store",
                "priority": "high",
                "status": "pending",
                "due_date": "2026-09-23",
            }):
                result = v2t.process_voice_to_task(
                    user_id=1,
                    audio_data=b"\x00" * 100,
                    content_type="audio/webm",
                    get_connection=lambda: mock_conn,
                )

    assert result["status"] == "success"
    assert result["needs_confirmation"] is True
    assert result["task"]["title"] == "Buy milk"
    assert result["task"]["priority"] == "high"
    assert result["transcript_length"] == len("Buy milk tomorrow")


def test_process_voice_to_task_invalid_mime():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="Unsupported"):
        v2t.process_voice_to_task(
            user_id=1,
            audio_data=b"\x00" * 100,
            content_type="image/png",
            get_connection=lambda: mock_conn,
        )


def test_process_voice_to_task_empty_audio():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="empty"):
        v2t.process_voice_to_task(
            user_id=1,
            audio_data=b"",
            content_type="audio/webm",
            get_connection=lambda: mock_conn,
        )


def test_process_voice_to_task_quota_exceeded():
    mock_conn = MagicMock()
    with patch("services.voice_to_task.check_and_increment", return_value=(False, 100)):
        with pytest.raises(ValueError, match="Daily AI request limit reached"):
            v2t.process_voice_to_task(
                user_id=1,
                audio_data=b"\x00" * 100,
                content_type="audio/webm",
                get_connection=lambda: mock_conn,
            )


def test_process_voice_to_task_empty_transcript():
    mock_conn = MagicMock()
    with patch("services.voice_to_task.check_and_increment", return_value=(True, 1)):
        with patch("services.voice_to_task._transcribe_audio", return_value=""):
            with pytest.raises(ValueError, match="empty text"):
                v2t.process_voice_to_task(
                    user_id=1,
                    audio_data=b"\x00" * 100,
                    content_type="audio/webm",
                    get_connection=lambda: mock_conn,
                )


def test_process_voice_to_task_does_not_log_transcript():
    """Ensure the transcript content is not logged — only length is exposed."""
    mock_conn = MagicMock()
    with patch("services.voice_to_task.check_and_increment", return_value=(True, 1)):
        with patch("services.voice_to_task._transcribe_audio", return_value="secret content"):
            with patch("services.voice_to_task._extract_task_from_transcript", return_value={
                "title": "Test", "description": "", "priority": "medium",
                "status": "pending", "due_date": None,
            }):
                with patch("services.voice_to_task.logger") as mock_logger:
                    result = v2t.process_voice_to_task(
                        user_id=1,
                        audio_data=b"\x00" * 100,
                        content_type="audio/webm",
                        get_connection=lambda: mock_conn,
                    )
                    # Verify no log call contains the transcript
                    for call in mock_logger.info.call_args_list + mock_logger.debug.call_args_list:
                        assert "secret content" not in str(call)
                    # Result should not contain the transcript text
                    assert "secret content" not in str(result)
                    assert result["transcript_length"] == len("secret content")


# ------------------------------------------------------------------ #
# confirm_and_create_task
# ------------------------------------------------------------------ #

def test_confirm_and_create_task_success():
    mock_conn = MagicMock()
    mock_task = {"id": 1, "title": "Buy milk", "status": "pending"}
    with patch("routes.task_routes.insert_task", return_value=mock_task):
        result = v2t.confirm_and_create_task(
            user_id=1,
            task_data={"title": "Buy milk", "priority": "high", "due_date": None},
            get_connection=lambda: mock_conn,
        )
    assert result == mock_task


def test_confirm_and_create_task_no_title():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="title is required"):
        v2t.confirm_and_create_task(
            user_id=1,
            task_data={"description": "no title here"},
            get_connection=lambda: mock_conn,
        )


def test_confirm_and_create_task_empty():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="title is required"):
        v2t.confirm_and_create_task(
            user_id=1,
            task_data={},
            get_connection=lambda: mock_conn,
        )


# ------------------------------------------------------------------ #
# Quota accounting — verify check_and_increment is called
# ------------------------------------------------------------------ #

def test_quota_check_is_called():
    mock_conn = MagicMock()
    with patch("services.voice_to_task.check_and_increment", return_value=(True, 1)) as mock_check:
        with patch("services.voice_to_task._transcribe_audio", return_value="test"):
            with patch("services.voice_to_task._extract_task_from_transcript", return_value={
                "title": "T", "description": "", "priority": "medium",
                "status": "pending", "due_date": None,
            }):
                v2t.process_voice_to_task(
                    user_id=42,
                    audio_data=b"\x00" * 10,
                    content_type="audio/webm",
                    get_connection=lambda: mock_conn,
                )
                assert mock_check.called
                args = mock_check.call_args
                assert args[0][0] == 42 or args[1].get("user_id") == 42
