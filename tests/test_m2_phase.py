"""
tests/test_m2_phase.py
Tests for Phase M2: auth session, voice MIME, file upload API, quota display.

M2.1 — Auth: 401 without token, 200 with token on list tasks.
M2.2 — Voice: iOS Safari MIME types accepted; server errors surfaced.
M2.3 — File upload API: CRUD, MIME allowlist, size cap, owner isolation.
M2.5 — Quota: GET /api/v1/account/quota returns plan + remaining.
"""

import io
import json
import pytest
from unittest.mock import MagicMock
from tests.conftest import make_user


# ------------------------------------------------------------------ #
# Helpers (same pattern as test_api_routes.py / test_api_v1.py)
# ------------------------------------------------------------------ #

_AUTH_TARGETS = [
    "routes.task_routes.get_current_user",
    "routes.calendar_routes.get_current_user",
    "routes.ai_routes.get_current_user",
    "routes.reminder_routes.get_current_user",
]

_V1_AUTH_TARGET = "routes.api_v1.get_current_user"


def _mock_auth(mocker, user=None):
    """Patch get_current_user in every route module."""
    u = user or make_user()
    for target in _AUTH_TARGETS:
        mocker.patch(target, return_value=(u, None, None))
    mocker.patch(_V1_AUTH_TARGET, return_value=(u, None, None))
    return u


def _mock_db(mocker):
    """Configure mock pool so _is_db_available returns False (in-memory)."""
    import db.pool as pool_module
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None
    mock_cur.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cur
    pool_module._pool.getconn.return_value = mock_conn
    return mock_conn, mock_cur


# ------------------------------------------------------------------ #
# M2.1 — Auth session on mobile web
# ------------------------------------------------------------------ #

def test_tasks_401_without_token(client, mocker):
    """No token → 401, not a crash or empty 200."""
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.get("/tasks")
    assert res.status_code == 401
    data = res.get_json()
    assert data["status"] == "error"


def test_tasks_200_with_token(client, mocker):
    """Valid token → 200 with task list."""
    _mock_auth(mocker)
    mock_conn, mock_cur = _mock_db(mocker)
    # Return some tasks
    mock_cur.fetchall.return_value = [
        {"id": 1, "title": "Test task", "description": "", "status": "pending",
         "priority": "medium", "due_date": None, "created_at": None, "user_id": 1},
    ]
    mocker.patch("db.pool.get_connection", return_value=mock_conn)
    mocker.patch("db.pool.return_connection")
    res = client.get("/tasks")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert isinstance(data["tasks"], list)


def test_appointments_401_without_token(client, mocker):
    """No token → 401 on appointments."""
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.get("/appointments")
    assert res.status_code == 401


def test_ai_401_without_token(client, mocker):
    """No token → 401 on AI chat."""
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.post("/ai", json={"message": "hello"})
    assert res.status_code == 401


# ------------------------------------------------------------------ #
# M2.2 — Voice MIME types (iOS Safari)
# ------------------------------------------------------------------ #

def test_voice_accepts_mp4_mime(client, mocker):
    """iOS Safari audio/mp4 MIME should pass the settings allowlist."""
    import config.settings as s
    assert "audio/mp4" in s.ALLOWED_AUDIO_MIME_TYPES
    assert "video/mp4" in s.ALLOWED_AUDIO_MIME_TYPES


def test_voice_accepts_m4a_mime(client, mocker):
    """audio/m4a MIME should pass the settings allowlist."""
    import config.settings as s
    assert "audio/m4a" in s.ALLOWED_AUDIO_MIME_TYPES


def test_transcribe_voice_401_without_token(client, mocker):
    """No token → 401 on transcribe-voice (not silent reset)."""
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.post("/transcribe-voice", data={"audio": (io.BytesIO(b"x"), "voice.mp4")})
    assert res.status_code == 401


# ------------------------------------------------------------------ #
# M2.3 — File upload API
# ------------------------------------------------------------------ #

@pytest.fixture(autouse=True)
def _reset_file_store():
    from services.file_service import _reset_mem_store
    _reset_mem_store()
    yield
    _reset_mem_store()


def _upload(client, mocker, data=b"hello", filename="test.txt",
            content_type="text/plain", user=None):
    """Helper: upload a file as an authenticated user."""
    _mock_auth(mocker, user)
    _mock_db(mocker)
    res = client.post(
        "/api/v1/files",
        data={"file": (io.BytesIO(data), filename, content_type)},
        content_type="multipart/form-data",
    )
    return res


def test_upload_file_success(client, mocker):
    """Authenticated user can upload a valid file."""
    res = _upload(client, mocker, data=b"hello world", filename="doc.txt",
                   content_type="text/plain")
    assert res.status_code == 201
    data = res.get_json()
    # Filename is sanitized with a UUID prefix for uniqueness
    assert data["filename"].endswith("doc.txt")
    assert data["content_type"] == "text/plain"
    assert data["size_bytes"] == 11
    assert "id" in data
    assert "created_at" in data


def test_upload_file_unauthenticated(client, mocker):
    """No token → 401 on file upload."""
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.post("/api/v1/files",
                      data={"file": (io.BytesIO(b"x"), "t.txt")},
                      content_type="multipart/form-data")
    assert res.status_code == 401


def test_upload_file_no_file(client, mocker):
    """Missing file field → 400."""
    _mock_auth(mocker)
    _mock_db(mocker)
    res = client.post("/api/v1/files", content_type="multipart/form-data")
    assert res.status_code == 400


def test_upload_file_invalid_mime(client, mocker):
    """Unsupported MIME → 400."""
    res = _upload(client, mocker, data=b"x", filename="bad.exe",
                   content_type="application/octet-stream")
    assert res.status_code == 400
    data = res.get_json()
    assert "Unsupported" in data["message"]


def test_upload_file_empty(client, mocker):
    """Empty file → 400."""
    res = _upload(client, mocker, data=b"", filename="empty.txt",
                   content_type="text/plain")
    assert res.status_code == 400


def test_upload_file_path_traversal_sanitized(client, mocker):
    """Path traversal in filename is stripped to basename."""
    res = _upload(client, mocker, data=b"data", filename="../../etc/passwd",
                   content_type="text/plain")
    assert res.status_code == 201
    data = res.get_json()
    # filename should be the sanitized basename — no path separators
    assert "/" not in data["filename"]
    assert ".." not in data["filename"]
    # Should contain the original base name
    assert "passwd" in data["filename"]


def test_list_files(client, mocker):
    """List files returns only the user's files."""
    _mock_auth(mocker)
    _mock_db(mocker)
    # Upload two files
    client.post("/api/v1/files",
                data={"file": (io.BytesIO(b"a"), "a.txt", "text/plain")},
                content_type="multipart/form-data")
    client.post("/api/v1/files",
                data={"file": (io.BytesIO(b"bb"), "b.txt", "text/plain")},
                content_type="multipart/form-data")
    res = client.get("/api/v1/files")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_get_file_success(client, mocker):
    """Get a file by ID returns the record."""
    _mock_auth(mocker)
    _mock_db(mocker)
    upload_res = client.post(
        "/api/v1/files",
        data={"file": (io.BytesIO(b"data"), "file.txt", "text/plain")},
        content_type="multipart/form-data",
    )
    fid = upload_res.get_json()["id"]
    res = client.get(f"/api/v1/files/{fid}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["id"] == fid
    assert data["filename"].endswith("file.txt")


def test_get_file_not_found(client, mocker):
    """Non-existent file ID → 404."""
    _mock_auth(mocker)
    _mock_db(mocker)
    res = client.get("/api/v1/files/99999")
    assert res.status_code == 404


def test_delete_file_success(client, mocker):
    """Delete a file by ID."""
    _mock_auth(mocker)
    _mock_db(mocker)
    upload_res = client.post(
        "/api/v1/files",
        data={"file": (io.BytesIO(b"data"), "del.txt", "text/plain")},
        content_type="multipart/form-data",
    )
    fid = upload_res.get_json()["id"]
    res = client.delete(f"/api/v1/files/{fid}")
    assert res.status_code == 200
    # Verify it's gone
    res2 = client.get(f"/api/v1/files/{fid}")
    assert res2.status_code == 404


def test_delete_file_not_found(client, mocker):
    """Delete non-existent → 404."""
    _mock_auth(mocker)
    _mock_db(mocker)
    res = client.delete("/api/v1/files/99999")
    assert res.status_code == 404


def test_file_isolation_user_b_cannot_get_user_a(client, mocker):
    """User B cannot GET a file owned by user A."""
    # User A uploads
    user_a = make_user(uid=1)
    _mock_auth(mocker, user_a)
    _mock_db(mocker)
    upload_res = client.post(
        "/api/v1/files",
        data={"file": (io.BytesIO(b"secret"), "secret.txt", "text/plain")},
        content_type="multipart/form-data",
    )
    assert upload_res.status_code == 201
    file_id = upload_res.get_json()["id"]

    # User B tries to GET it
    from services.file_service import _reset_mem_store
    # Do NOT reset — the in-memory store should still have user A's file
    user_b = make_user(uid=2)
    _mock_auth(mocker, user_b)
    res = client.get(f"/api/v1/files/{file_id}")
    assert res.status_code == 404


def test_file_isolation_user_b_cannot_delete_user_a(client, mocker):
    """User B cannot DELETE a file owned by user A."""
    user_a = make_user(uid=1)
    _mock_auth(mocker, user_a)
    _mock_db(mocker)
    upload_res = client.post(
        "/api/v1/files",
        data={"file": (io.BytesIO(b"secret"), "secret2.txt", "text/plain")},
        content_type="multipart/form-data",
    )
    file_id = upload_res.get_json()["id"]

    user_b = make_user(uid=2)
    _mock_auth(mocker, user_b)
    res = client.delete(f"/api/v1/files/{file_id}")
    assert res.status_code == 404


def test_file_isolation_list_only_own(client, mocker):
    """List files only returns the current user's files, not other users'."""
    # User A uploads
    user_a = make_user(uid=1)
    _mock_auth(mocker, user_a)
    _mock_db(mocker)
    client.post("/api/v1/files",
                data={"file": (io.BytesIO(b"a"), "a_file.txt", "text/plain")},
                content_type="multipart/form-data")

    # User B uploads
    user_b = make_user(uid=2)
    _mock_auth(mocker, user_b)
    client.post("/api/v1/files",
                data={"file": (io.BytesIO(b"b"), "b_file.txt", "text/plain")},
                content_type="multipart/form-data")

    # User A lists — should only see their file
    _mock_auth(mocker, user_a)
    res = client.get("/api/v1/files")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 1
    assert data["items"][0]["filename"].endswith("a_file.txt")


def test_upload_file_jpeg(client, mocker):
    """JPEG image upload succeeds."""
    res = _upload(client, mocker, data=b"\xff\xd8\xff\xe0", filename="photo.jpg",
                   content_type="image/jpeg")
    assert res.status_code == 201


def test_upload_file_png(client, mocker):
    """PNG image upload succeeds."""
    res = _upload(client, mocker, data=b"\x89PNG\r\n", filename="photo.png",
                   content_type="image/png")
    assert res.status_code == 201


def test_upload_file_webp(client, mocker):
    """WebP image upload succeeds."""
    res = _upload(client, mocker, data=b"RIFF...", filename="img.webp",
                   content_type="image/webp")
    assert res.status_code == 201


def test_upload_file_pdf(client, mocker):
    """PDF upload succeeds."""
    res = _upload(client, mocker, data=b"%PDF-1.4", filename="doc.pdf",
                   content_type="application/pdf")
    assert res.status_code == 201


def test_upload_file_markdown(client, mocker):
    """Markdown upload succeeds."""
    res = _upload(client, mocker, data=b"# Title", filename="readme.md",
                   content_type="text/markdown")
    assert res.status_code == 201


# ------------------------------------------------------------------ #
# M2.3 — OpenAPI spec includes file endpoints
# ------------------------------------------------------------------ #

def test_openapi_has_files_endpoint(client):
    """OpenAPI spec includes /files and /files/{file_id}."""
    res = client.get("/api/v1/openapi.json")
    spec = res.get_json()
    assert "/files" in spec["paths"]
    assert "/files/{file_id}" in spec["paths"]
    assert "post" in spec["paths"]["/files"]
    assert "get" in spec["paths"]["/files"]
    assert "delete" in spec["paths"]["/files/{file_id}"]


def test_openapi_has_userfile_schema(client):
    """OpenAPI spec includes the UserFile schema."""
    res = client.get("/api/v1/openapi.json")
    spec = res.get_json()
    assert "UserFile" in spec["components"]["schemas"]


# ------------------------------------------------------------------ #
# M2.5 — Quota visible
# ------------------------------------------------------------------ #

def test_account_quota_unauthenticated(client, mocker):
    """No token → 401 on quota endpoint."""
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.get("/api/v1/account/quota")
    assert res.status_code == 401


def test_account_quota_authenticated(client, mocker):
    """Authenticated user gets plan + remaining quota."""
    _mock_auth(mocker)
    _mock_db(mocker)
    res = client.get("/api/v1/account/quota")
    assert res.status_code == 200
    data = res.get_json()
    assert "plan" in data
    assert "plan_name" in data
    assert "ai_daily_limit" in data
    assert "ai_calls_today" in data
    assert "remaining" in data
    assert "quota_exceeded" in data
