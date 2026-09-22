"""
tests/test_workspace_routes.py
Integration tests for workspace API routes using Flask test client.
All DB calls are mocked — no real infrastructure needed.
"""

import pytest
from unittest.mock import MagicMock
from tests.conftest import make_user
from services.workspace import Workspace, Project, reset_workspaces


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def auth_headers(token="test-token-123"):
    return {"Authorization": f"Bearer {token}"}


# Route modules bind get_current_user at import time, so we must patch
# each module's local reference — not the source module.
_AUTH_TARGETS = [
    "routes.workspace_routes.get_current_user",
]


def mock_auth(mocker, user=None):
    """Patch get_current_user in the workspace route module."""
    u = user or make_user()
    for target in _AUTH_TARGETS:
        mocker.patch(target, return_value=(u, None, None))
    return u


def _mock_ws(**kwargs):
    """Create a mock Workspace dict-like object for route responses."""
    defaults = {
        "id": 1, "name": "WS", "user_id": 1, "description": "",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    defaults.update(kwargs)
    return Workspace(**defaults)


def _mock_proj(**kwargs):
    """Create a mock Project object for route responses."""
    defaults = {
        "id": 10, "workspace_id": 1, "user_id": 1, "name": "Proj",
        "description": "", "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    defaults.update(kwargs)
    return Project(**defaults)


# ------------------------------------------------------------------ #
# Unauthenticated — all endpoints require auth
# ------------------------------------------------------------------ #

def test_create_workspace_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.post("/workspaces", json={"name": "WS"})
    assert res.status_code == 401


def test_list_workspaces_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.get("/workspaces")
    assert res.status_code == 401


def test_get_workspace_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.get("/workspaces/1")
    assert res.status_code == 401


def test_delete_workspace_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.delete("/workspaces/1")
    assert res.status_code == 401


def test_create_project_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.post("/workspaces/1/projects", json={"name": "P"})
    assert res.status_code == 401


def test_list_projects_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.get("/workspaces/1/projects")
    assert res.status_code == 401


def test_delete_project_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.delete("/workspaces/1/projects/10")
    assert res.status_code == 401


# ------------------------------------------------------------------ #
# Workspace endpoints — validation (auth mocked, service mocked)
# ------------------------------------------------------------------ #

def test_create_workspace_no_body(client, mocker):
    mock_auth(mocker)
    mocker.patch("db.pool.get_connection", return_value=MagicMock())
    mocker.patch("db.pool.return_connection")
    res = client.post("/workspaces")
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"


def test_create_workspace_empty_name(client, mocker):
    mock_auth(mocker)
    mocker.patch("db.pool.get_connection", return_value=MagicMock())
    mocker.patch("db.pool.return_connection")
    res = client.post("/workspaces", json={"name": ""})
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"


# ------------------------------------------------------------------ #
# Workspace endpoints — happy path (service functions mocked at route level)
# ------------------------------------------------------------------ #

def test_create_workspace_success(client, mocker):
    user = mock_auth(mocker)
    mocker.patch(
        "routes.workspace_routes.ws_create",
        return_value=_mock_ws(name="My WS", user_id=user["id"], id=1),
    )
    res = client.post("/workspaces", json={
        "name": "My WS",
        "description": "Test workspace",
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["status"] == "success"
    assert data["workspace"]["name"] == "My WS"
    assert data["workspace"]["user_id"] == user["id"]


def test_list_workspaces_success(client, mocker):
    user = mock_auth(mocker)
    mocker.patch(
        "routes.workspace_routes.ws_list",
        return_value=[
            _mock_ws(name="A", user_id=user["id"], id=1),
            _mock_ws(name="B", user_id=user["id"], id=2),
        ],
    )
    res = client.get("/workspaces")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["workspaces"]) == 2
    assert all(ws["user_id"] == user["id"] for ws in data["workspaces"])


def test_get_workspace_success(client, mocker):
    user = mock_auth(mocker)
    mocker.patch(
        "routes.workspace_routes.ws_get",
        return_value=_mock_ws(name="Found", user_id=user["id"], id=5),
    )
    res = client.get("/workspaces/5")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["workspace"]["name"] == "Found"


def test_get_workspace_not_found(client, mocker):
    mock_auth(mocker)
    mocker.patch("routes.workspace_routes.ws_get", return_value=None)
    res = client.get("/workspaces/99999")
    assert res.status_code == 404
    data = res.get_json()
    assert data["status"] == "error"
    assert "not found" in data["message"]


def test_get_workspace_wrong_user(client, mocker):
    """Workspace owned by another user returns 404 (user isolation)."""
    mock_auth(mocker, make_user(uid=1))
    mocker.patch("routes.workspace_routes.ws_get", return_value=None)
    res = client.get("/workspaces/5")
    assert res.status_code == 404


def test_delete_workspace_success(client, mocker):
    user = mock_auth(mocker)
    mocker.patch("routes.workspace_routes.ws_delete", return_value=True)
    res = client.delete("/workspaces/5")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"


def test_delete_workspace_not_found(client, mocker):
    mock_auth(mocker)
    mocker.patch("routes.workspace_routes.ws_delete", return_value=False)
    res = client.delete("/workspaces/99999")
    assert res.status_code == 404


# ------------------------------------------------------------------ #
# Project endpoints — validation + happy path
# ------------------------------------------------------------------ #

def test_create_project_no_body(client, mocker):
    mock_auth(mocker)
    mocker.patch("db.pool.get_connection", return_value=MagicMock())
    mocker.patch("db.pool.return_connection")
    res = client.post("/workspaces/1/projects")
    assert res.status_code == 400


def test_create_project_empty_name(client, mocker):
    mock_auth(mocker)
    mocker.patch("db.pool.get_connection", return_value=MagicMock())
    mocker.patch("db.pool.return_connection")
    res = client.post("/workspaces/1/projects", json={"name": ""})
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"


def test_create_project_success(client, mocker):
    user = mock_auth(mocker)
    mocker.patch(
        "routes.workspace_routes.proj_create",
        return_value=_mock_proj(name="My Project", user_id=user["id"],
                                 workspace_id=1, id=10),
    )
    res = client.post("/workspaces/1/projects", json={
        "name": "My Project",
        "description": "Test project",
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["status"] == "success"
    assert data["project"]["name"] == "My Project"
    assert data["project"]["workspace_id"] == 1


def test_create_project_wrong_workspace(client, mocker):
    """Creating project in non-owned workspace returns 404."""
    mock_auth(mocker)
    mocker.patch("routes.workspace_routes.proj_create", return_value=None)
    res = client.post("/workspaces/9999/projects", json={"name": "P"})
    assert res.status_code == 404


def test_create_project_value_error(client, mocker):
    """ValueError from service returns 400."""
    mock_auth(mocker)
    mocker.patch(
        "routes.workspace_routes.proj_create",
        side_effect=ValueError("Project name is required"),
    )
    res = client.post("/workspaces/1/projects", json={"name": "P"})
    assert res.status_code == 400


def test_list_projects_success(client, mocker):
    user = mock_auth(mocker)
    mocker.patch(
        "routes.workspace_routes.proj_list",
        return_value=[
            _mock_proj(name="P1", workspace_id=1, user_id=user["id"], id=10),
            _mock_proj(name="P2", workspace_id=1, user_id=user["id"], id=11),
        ],
    )
    res = client.get("/workspaces/1/projects")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["projects"]) == 2
    assert all(p["workspace_id"] == 1 for p in data["projects"])


def test_list_projects_empty(client, mocker):
    mock_auth(mocker)
    mocker.patch("routes.workspace_routes.proj_list", return_value=[])
    res = client.get("/workspaces/1/projects")
    assert res.status_code == 200
    data = res.get_json()
    assert data["projects"] == []


def test_delete_project_success(client, mocker):
    mock_auth(mocker)
    mocker.patch("routes.workspace_routes.proj_delete", return_value=True)
    res = client.delete("/workspaces/1/projects/10")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"


def test_delete_project_not_found(client, mocker):
    mock_auth(mocker)
    mocker.patch("routes.workspace_routes.proj_delete", return_value=False)
    res = client.delete("/workspaces/1/projects/99999")
    assert res.status_code == 404
    data = res.get_json()
    assert data["status"] == "error"
    assert "not found" in data["message"]
