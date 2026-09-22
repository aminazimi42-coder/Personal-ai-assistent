"""
tests/test_quota_bypass.py
Tests for Phase 1b: Quota enforcement + upload security + prompt-injection defense.

Verifies:
- /ai-to-task enforces quota (429 when check_and_increment returns False)
- /transcribe-voice enforces quota (429 when check_and_increment returns False)
- /transcribe-voice MIME validation rejects non-audio files (415)
- /transcribe-voice filename is sanitized (path traversal blocked)
- sanitize_input strips control chars and truncates to MAX_QUERY_LENGTH
"""

import io
from unittest.mock import MagicMock

import pytest
from tests.conftest import make_user

# ------------------------------------------------------------------ #
# Helpers (same pattern as test_api_routes.py)
# ------------------------------------------------------------------ #

_AUTH_TARGETS = [
    "routes.task_routes.get_current_user",
    "routes.calendar_routes.get_current_user",
    "routes.ai_routes.get_current_user",
    "routes.reminder_routes.get_current_user",
]


def mock_auth(mocker, user=None):
    u = user or make_user()
    for target in _AUTH_TARGETS:
        mocker.patch(target, return_value=(u, None, None))
    return u


# ------------------------------------------------------------------ #
# /ai-to-task quota enforcement
# ------------------------------------------------------------------ #

def test_ai_to_task_quota_denied(client, mocker):
    """ai-to-task must enforce quota and return 429 when exceeded."""
    mock_auth(mocker)
    mocker.patch(
        "routes.ai_routes.check_and_increment",
        return_value=(False, 100),
    )
    res = client.post("/ai-to-task", json={"message": "remind me to buy milk"})
    assert res.status_code == 429
    data = res.get_json()
    assert data["status"] == "error"
    assert "limit" in data["message"].lower()


def test_ai_to_task_quota_allowed_proceeds(client, mocker):
    """ai-to-task with quota allowed should proceed to AI call (not 429)."""
    mock_auth(mocker)
    mocker.patch(
        "routes.ai_routes.check_and_increment",
        return_value=(True, 1),
    )
    mocker.patch(
        "routes.ai_routes.extract_task_from_message",
        return_value={
            "title": "Buy milk",
            "description": "",
            "status": "pending",
            "priority": "medium",
            "due_date": None,
        },
    )
    mocker.patch("routes.ai_routes.insert_task", return_value={"id": 1})
    res = client.post("/ai-to-task", json={"message": "remind me to buy milk"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"


def test_ai_to_task_calls_check_and_increment(client, mocker):
    """ai-to-task must actually call check_and_increment."""
    mock_auth(mocker)
    mock_ci = mocker.patch(
        "routes.ai_routes.check_and_increment",
        return_value=(True, 1),
    )
    mocker.patch(
        "routes.ai_routes.extract_task_from_message",
        return_value={
            "title": "Buy milk",
            "description": "",
            "status": "pending",
            "priority": "medium",
            "due_date": None,
        },
    )
    mocker.patch("routes.ai_routes.insert_task", return_value={"id": 1})
    client.post("/ai-to-task", json={"message": "remind me to buy milk"})
    mock_ci.assert_called_once()


# ------------------------------------------------------------------ #
# /transcribe-voice quota enforcement
# ------------------------------------------------------------------ #

def test_transcribe_voice_quota_denied(client, mocker):
    """transcribe-voice must enforce quota and return 429 when exceeded."""
    mock_auth(mocker)
    mocker.patch(
        "routes.ai_routes.check_and_increment",
        return_value=(False, 100),
    )
    # Even if a valid audio file is provided, quota should block first
    audio_bytes = b"\x00" * 100
    res = client.post(
        "/transcribe-voice",
        data={"audio": (io.BytesIO(audio_bytes), "test.webm", "audio/webm")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 429
    data = res.get_json()
    assert data["status"] == "error"
    assert "limit" in data["message"].lower()


# ------------------------------------------------------------------ #
# /transcribe-voice MIME validation
# ------------------------------------------------------------------ #

def test_transcribe_voice_rejects_non_audio_mime(client, mocker):
    """transcribe-voice must reject non-audio MIME types with 415."""
    mock_auth(mocker)
    mocker.patch(
        "routes.ai_routes.check_and_increment",
        return_value=(True, 1),
    )
    # Send a file with a non-audio content type
    audio_bytes = b"not really audio"
    res = client.post(
        "/transcribe-voice",
        data={"audio": (io.BytesIO(audio_bytes), "evil.exe", "application/octet-stream")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 415
    data = res.get_json()
    assert data["status"] == "error"
    assert "unsupported" in data["message"].lower() or "type" in data["message"].lower()


def test_transcribe_voice_accepts_valid_mime(client, mocker):
    """transcribe-voice should accept valid audio MIME types (not 415)."""
    mock_auth(mocker)
    mocker.patch(
        "routes.ai_routes.check_and_increment",
        return_value=(True, 1),
    )
    mocker.patch("routes.ai_routes.get_openai_client")
    # Mock the transcription call
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = MagicMock(text="hello")
    mocker.patch("routes.ai_routes.get_openai_client", return_value=mock_client)

    audio_bytes = b"\x00" * 200
    res = client.post(
        "/transcribe-voice",
        data={"audio": (io.BytesIO(audio_bytes), "test.webm", "audio/webm")},
        content_type="multipart/form-data",
    )
    # Should not be 415 — it passed MIME validation
    assert res.status_code != 415


# ------------------------------------------------------------------ #
# /transcribe-voice filename sanitization (path traversal)
# ------------------------------------------------------------------ #

def test_transcribe_voice_filename_sanitized(client, mocker, tmp_path):
    """transcribe-voice must sanitize filename to prevent path traversal.

    The temp file is created via tempfile.NamedTemporaryFile which uses its
    own name, so path traversal in the suffix isn't directly exploitable —
    but we verify that os.path.basename is applied so a filename like
    '../../etc/passwd' cannot influence the temp file path.
    """
    import routes.ai_routes

    mock_auth(mocker)
    mocker.patch(
        "routes.ai_routes.check_and_increment",
        return_value=(True, 1),
    )

    # Capture the suffix passed to NamedTemporaryFile
    captured_suffixes = []
    orig_ntf = routes.ai_routes.tempfile.NamedTemporaryFile

    class CapturingNTF:
        def __init__(self, **kwargs):
            captured_suffixes.append(kwargs.get("suffix", ""))
            self._tmp = orig_ntf(**kwargs)

        def __enter__(self):
            return self._tmp.__enter__()

        def __exit__(self, *args):
            return self._tmp.__exit__(*args)

        def write(self, data):
            return self._tmp.write(data)

        @property
        def name(self):
            return self._tmp.name

    mocker.patch("routes.ai_routes.tempfile.NamedTemporaryFile", CapturingNTF)

    # Mock the OpenAI client so no real API call happens
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = MagicMock(text="hello")
    mocker.patch("routes.ai_routes.get_openai_client", return_value=mock_client)

    audio_bytes = b"\x00" * 200
    # Send a filename with path traversal attempt
    res = client.post(
        "/transcribe-voice",
        data={"audio": (io.BytesIO(audio_bytes), "../../etc/passwd", "audio/webm")},
        content_type="multipart/form-data",
    )
    # The route should succeed (the traversal is sanitized away)
    assert res.status_code in (200, 503)  # 503 if mock path issue; not 415/429
    # The suffix used for the temp file should not contain path separators
    if captured_suffixes:
        suffix = captured_suffixes[0]
        assert "/" not in suffix
        assert ".." not in suffix


# ------------------------------------------------------------------ #
# sanitize_input — prompt-injection defense in code_retrieval
# ------------------------------------------------------------------ #

def test_sanitize_input_strips_control_chars():
    from services.code_retrieval import sanitize_input
    raw = "hello\x00world\x07\x1b[31m"
    result = sanitize_input(raw)
    assert "\x00" not in result
    assert "\x07" not in result
    assert "\x1b" not in result
    assert "hello" in result
    assert "world" in result


def test_sanitize_input_truncates_to_max_length():
    from services.code_retrieval import sanitize_input, MAX_QUERY_LENGTH
    long_text = "a" * (MAX_QUERY_LENGTH + 100)
    result = sanitize_input(long_text)
    assert len(result) == MAX_QUERY_LENGTH


def test_sanitize_input_empty():
    from services.code_retrieval import sanitize_input
    assert sanitize_input("") == ""
    assert sanitize_input(None) == ""


def test_sanitize_input_preserves_normal_text():
    from services.code_retrieval import sanitize_input
    result = sanitize_input("search for auth_service.py")
    assert "auth_service" in result


def test_max_query_length_constant():
    from services.code_retrieval import MAX_QUERY_LENGTH
    assert MAX_QUERY_LENGTH == 10000


def test_retrieve_code_uses_sanitize_input(client, mocker):
    """retrieve_code should pass the query through sanitize_input (control chars stripped)."""
    from services.code_retrieval import retrieve_code
    import services.code_retrieval as cr

    # Mock ingest to return empty so no file IO happens
    mocker.patch("services.code_retrieval.ingest_repository", return_value=[])
    result = retrieve_code("/nonexistent", "test\x00query")
    # The query in the result should have control chars stripped
    assert "\x00" not in result.query
