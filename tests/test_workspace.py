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
