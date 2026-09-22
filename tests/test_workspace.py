"""
tests/test_workspace.py
Tests for Project Workspace: ownership, isolation, CRUD.
"""

import pytest
from services.workspace import (
    create_workspace, get_workspace, list_workspaces, delete_workspace,
    create_project, list_projects, get_project, reset_workspaces,
)


def test_create_workspace():
    reset_workspaces()
    ws = create_workspace(1, "My Workspace", "Test workspace")
    assert ws.user_id == 1
    assert ws.name == "My Workspace"
    assert ws.id is not None


def test_create_workspace_empty_name():
    with pytest.raises(ValueError):
        create_workspace(1, "")


def test_get_workspace():
    reset_workspaces()
    ws = create_workspace(1, "Test")
    retrieved = get_workspace(ws.id, 1)
    assert retrieved is not None
    assert retrieved.name == "Test"


def test_get_workspace_wrong_user():
    """User cannot access another user's workspace."""
    reset_workspaces()
    ws = create_workspace(1, "User1 WS")
    assert get_workspace(ws.id, 2) is None


def test_list_workspaces():
    reset_workspaces()
    create_workspace(1, "WS1")
    create_workspace(1, "WS2")
    create_workspace(2, "OtherUser WS")
    wss = list_workspaces(1)
    assert len(wss) == 2
    assert all(ws.user_id == 1 for ws in wss)


def test_delete_workspace():
    reset_workspaces()
    ws = create_workspace(1, "ToDelete")
    assert delete_workspace(ws.id, 1) is True
    assert get_workspace(ws.id, 1) is None


def test_delete_workspace_wrong_user():
    reset_workspaces()
    ws = create_workspace(1, "User1")
    assert delete_workspace(ws.id, 2) is False
    assert get_workspace(ws.id, 1) is not None


def test_create_project():
    reset_workspaces()
    ws = create_workspace(1, "WS")
    proj = create_project(ws.id, 1, "My Project", "Test project")
    assert proj is not None
    assert proj.workspace_id == ws.id
    assert proj.user_id == 1


def test_create_project_wrong_user():
    reset_workspaces()
    ws = create_workspace(1, "WS")
    proj = create_project(ws.id, 2, "Hacker Project")
    assert proj is None


def test_create_project_empty_name():
    reset_workspaces()
    ws = create_workspace(1, "WS")
    with pytest.raises(ValueError):
        create_project(ws.id, 1, "")


def test_list_projects():
    reset_workspaces()
    ws = create_workspace(1, "WS")
    create_project(ws.id, 1, "P1")
    create_project(ws.id, 1, "P2")
    projects = list_projects(ws.id, 1)
    assert len(projects) == 2


def test_list_projects_wrong_user():
    reset_workspaces()
    ws = create_workspace(1, "WS")
    create_project(ws.id, 1, "P1")
    assert list_projects(ws.id, 2) == []


def test_get_project():
    reset_workspaces()
    ws = create_workspace(1, "WS")
    proj = create_project(ws.id, 1, "P1")
    retrieved = get_project(proj.id, 1)
    assert retrieved is not None
    assert retrieved.name == "P1"


def test_get_project_wrong_user():
    reset_workspaces()
    ws = create_workspace(1, "WS")
    proj = create_project(ws.id, 1, "P1")
    assert get_project(proj.id, 2) is None


def test_delete_workspace_cascades_projects():
    reset_workspaces()
    ws = create_workspace(1, "WS")
    create_project(ws.id, 1, "P1")
    create_project(ws.id, 1, "P2")
    delete_workspace(ws.id, 1)
    assert list_projects(ws.id, 1) == []


def test_workspace_isolation_between_users():
    reset_workspaces()
    ws1 = create_workspace(1, "User1 WS")
    ws2 = create_workspace(2, "User2 WS")
    assert get_workspace(ws1.id, 2) is None
    assert get_workspace(ws2.id, 1) is None


# ------------------------------------------------------------------ #
# DB-backed tests (mock the connection — no real DB needed)
# ------------------------------------------------------------------ #

from unittest.mock import MagicMock


def _mock_conn(fetchone=None, fetchall=None):
    """Create a mock psycopg2 connection with RealDictCursor-like results."""
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = fetchone
    cur.fetchall.return_value = fetchall or []
    conn.cursor.return_value = cur
    return conn, cur


def _patch_pool(mocker, conn):
    """Patch db.pool.return_connection so it's a no-op."""
    mocker.patch("db.pool.return_connection")
    return conn


def test_db_create_workspace(mocker):
    """DB-backed create_workspace inserts and returns the row."""
    from services.workspace import create_workspace
    conn, cur = _mock_conn(
        fetchone={"id": 1, "name": "DB WS", "user_id": 5,
                  "description": "desc", "created_at": "2026-01-01T00:00:00+00:00",
                  "updated_at": "2026-01-01T00:00:00+00:00"},
    )
    _patch_pool(mocker, conn)
    ws = create_workspace(5, "DB WS", "desc", get_connection=lambda: conn)
    assert ws.id == 1
    assert ws.name == "DB WS"
    assert ws.user_id == 5
    assert ws.description == "desc"
    assert ws.created_at is not None


def test_db_create_workspace_empty_name(mocker):
    """DB-backed create_workspace raises ValueError on empty name."""
    from services.workspace import create_workspace
    conn = MagicMock()
    _patch_pool(mocker, conn)
    with pytest.raises(ValueError):
        create_workspace(5, "", "desc", get_connection=lambda: conn)


def test_db_get_workspace(mocker):
    """DB-backed get_workspace returns workspace for owner."""
    from services.workspace import get_workspace
    conn, cur = _mock_conn(
        fetchone={"id": 7, "name": "Found", "user_id": 3,
                  "description": "", "created_at": None, "updated_at": None},
    )
    _patch_pool(mocker, conn)
    ws = get_workspace(7, 3, get_connection=lambda: conn)
    assert ws is not None
    assert ws.id == 7
    assert ws.name == "Found"


def test_db_get_workspace_wrong_user(mocker):
    """DB-backed get_workspace returns None for non-owner."""
    from services.workspace import get_workspace
    conn, cur = _mock_conn(fetchone=None)
    _patch_pool(mocker, conn)
    ws = get_workspace(7, 99, get_connection=lambda: conn)
    assert ws is None


def test_db_list_workspaces(mocker):
    """DB-backed list_workspaces returns only user's workspaces."""
    from services.workspace import list_workspaces
    rows = [
        {"id": 1, "name": "A", "user_id": 5, "description": "",
         "created_at": None, "updated_at": None},
        {"id": 2, "name": "B", "user_id": 5, "description": "",
         "created_at": None, "updated_at": None},
    ]
    conn, cur = _mock_conn(fetchall=rows)
    _patch_pool(mocker, conn)
    wss = list_workspaces(5, get_connection=lambda: conn)
    assert len(wss) == 2
    assert all(ws.user_id == 5 for ws in wss)


def test_db_delete_workspace(mocker):
    """DB-backed delete_workspace returns True when row is deleted."""
    from services.workspace import delete_workspace
    conn, cur = _mock_conn(fetchone={"id": 1})
    _patch_pool(mocker, conn)
    assert delete_workspace(1, 5, get_connection=lambda: conn) is True


def test_db_delete_workspace_wrong_user(mocker):
    """DB-backed delete_workspace returns False when not found."""
    from services.workspace import delete_workspace
    conn, cur = _mock_conn(fetchone=None)
    _patch_pool(mocker, conn)
    assert delete_workspace(1, 99, get_connection=lambda: conn) is False


def test_db_create_project(mocker):
    """DB-backed create_project inserts and returns the project."""
    from services.workspace import create_project
    # Mock get_workspace to return a valid workspace
    ws_row = {"id": 1, "name": "WS", "user_id": 5, "description": "",
              "created_at": None, "updated_at": None}
    proj_row = {"id": 10, "workspace_id": 1, "user_id": 5,
                "name": "Proj", "description": "desc",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00"}

    conn = MagicMock()
    cur = MagicMock()
    # First call: get_workspace SELECT (returns ws_row)
    # Second call: create_project INSERT (returns proj_row)
    cur.fetchone.side_effect = [ws_row, proj_row]
    cur.fetchall.return_value = []
    conn.cursor.return_value = cur
    _patch_pool(mocker, conn)

    proj = create_project(1, 5, "Proj", "desc", get_connection=lambda: conn)
    assert proj is not None
    assert proj.id == 10
    assert proj.workspace_id == 1
    assert proj.user_id == 5


def test_db_create_project_wrong_user(mocker):
    """DB-backed create_project returns None when workspace not owned."""
    from services.workspace import create_project
    conn, cur = _mock_conn(fetchone=None)
    _patch_pool(mocker, conn)
    proj = create_project(1, 99, "Proj", "desc", get_connection=lambda: conn)
    assert proj is None


def test_db_create_project_empty_name(mocker):
    """DB-backed create_project raises ValueError on empty name."""
    from services.workspace import create_project
    conn = MagicMock()
    _patch_pool(mocker, conn)
    with pytest.raises(ValueError):
        create_project(1, 5, "", "desc", get_connection=lambda: conn)


def test_db_list_projects(mocker):
    """DB-backed list_projects returns projects for owned workspace."""
    from services.workspace import list_projects
    ws_row = {"id": 1, "name": "WS", "user_id": 5, "description": "",
              "created_at": None, "updated_at": None}
    proj_rows = [
        {"id": 10, "workspace_id": 1, "user_id": 5, "name": "P1",
         "description": "", "created_at": None, "updated_at": None},
        {"id": 11, "workspace_id": 1, "user_id": 5, "name": "P2",
         "description": "", "created_at": None, "updated_at": None},
    ]
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = ws_row
    cur.fetchall.return_value = proj_rows
    conn.cursor.return_value = cur
    _patch_pool(mocker, conn)
    projects = list_projects(1, 5, get_connection=lambda: conn)
    assert len(projects) == 2
    assert all(p.workspace_id == 1 for p in projects)


def test_db_list_projects_wrong_user(mocker):
    """DB-backed list_projects returns [] when workspace not owned."""
    from services.workspace import list_projects
    conn, cur = _mock_conn(fetchone=None, fetchall=[])
    _patch_pool(mocker, conn)
    assert list_projects(1, 99, get_connection=lambda: conn) == []


def test_db_get_project(mocker):
    """DB-backed get_project returns project for owner."""
    from services.workspace import get_project
    proj_row = {"id": 10, "workspace_id": 1, "user_id": 5,
                "name": "P", "description": "",
                "created_at": None, "updated_at": None}
    conn, cur = _mock_conn(fetchone=proj_row)
    _patch_pool(mocker, conn)
    proj = get_project(10, 5, get_connection=lambda: conn)
    assert proj is not None
    assert proj.id == 10
    assert proj.name == "P"


def test_db_get_project_wrong_user(mocker):
    """DB-backed get_project returns None for non-owner."""
    from services.workspace import get_project
    conn, cur = _mock_conn(fetchone=None)
    _patch_pool(mocker, conn)
    assert get_project(10, 99, get_connection=lambda: conn) is None


def test_db_delete_project(mocker):
    """DB-backed delete_project returns True when row is deleted."""
    from services.workspace import delete_project
    conn, cur = _mock_conn(fetchone={"id": 10})
    _patch_pool(mocker, conn)
    assert delete_project(10, 5, get_connection=lambda: conn) is True


def test_db_delete_project_wrong_user(mocker):
    """DB-backed delete_project returns False when not found."""
    from services.workspace import delete_project
    conn, cur = _mock_conn(fetchone=None)
    _patch_pool(mocker, conn)
    assert delete_project(10, 99, get_connection=lambda: conn) is False


def test_mem_delete_project():
    """In-memory delete_project works."""
    reset_workspaces()
    ws = create_workspace(1, "WS")
    proj = create_project(ws.id, 1, "P1")
    from services.workspace import delete_project
    assert delete_project(proj.id, 1) is True
    assert get_project(proj.id, 1) is None


def test_mem_delete_project_wrong_user():
    """In-memory delete_project returns False for non-owner."""
    reset_workspaces()
    ws = create_workspace(1, "WS")
    proj = create_project(ws.id, 1, "P1")
    from services.workspace import delete_project
    assert delete_project(proj.id, 2) is False
    assert get_project(proj.id, 1) is not None
