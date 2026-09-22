"""
services/workspace.py
Project Workspace — structured workspaces with ownership and isolation.

Workspace → Projects / Files / Code / Documents / Tasks / Conversations /
Memories / AI Context

Features:
- Ownership: each workspace belongs to a user
- Isolation: users can only access their own workspaces
- Access control: user-scoped queries
- Scalable model: workspaces contain projects, projects contain items
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Workspace:
    """A user workspace."""
    id: Optional[int] = None
    name: str = ""
    user_id: int = 0
    description: str = ""
    projects: list = field(default_factory=list)


@dataclass
class Project:
    """A project within a workspace."""
    id: Optional[int] = None
    workspace_id: int = 0
    name: str = ""
    description: str = ""
    user_id: int = 0


# In-memory store (DB-backed in production)
_workspaces: dict[int, Workspace] = {}
_projects: dict[int, Project] = {}
_next_ws_id = 1
_next_proj_id = 1


def create_workspace(user_id: int, name: str, description: str = "") -> Workspace:
    """Create a new workspace for a user."""
    global _next_ws_id
    if not name or not name.strip():
        raise ValueError("Workspace name is required")
    ws = Workspace(
        id=_next_ws_id,
        name=name.strip()[:200],
        user_id=user_id,
        description=description.strip()[:1000],
    )
    _workspaces[_next_ws_id] = ws
    _next_ws_id += 1
    return ws


def get_workspace(ws_id: int, user_id: int) -> Optional[Workspace]:
    """Get a workspace if it belongs to the user."""
    ws = _workspaces.get(ws_id)
    if ws and ws.user_id == user_id:
        return ws
    return None


def list_workspaces(user_id: int) -> list[Workspace]:
    """List all workspaces for a user."""
    return [ws for ws in _workspaces.values() if ws.user_id == user_id]


def delete_workspace(ws_id: int, user_id: int) -> bool:
    """Delete a workspace if it belongs to the user."""
    ws = _workspaces.get(ws_id)
    if ws and ws.user_id == user_id:
        del _workspaces[ws_id]
        # Delete associated projects
        to_del = [pid for pid, p in _projects.items() if p.workspace_id == ws_id]
        for pid in to_del:
            del _projects[pid]
        return True
    return False


def create_project(ws_id: int, user_id: int, name: str, description: str = "") -> Optional[Project]:
    """Create a project in a workspace (if user owns it)."""
    global _next_proj_id
    ws = get_workspace(ws_id, user_id)
    if not ws:
        return None
    if not name or not name.strip():
        raise ValueError("Project name is required")
    proj = Project(
        id=_next_proj_id,
        workspace_id=ws_id,
        name=name.strip()[:200],
        description=description.strip()[:1000],
        user_id=user_id,
    )
    _projects[_next_proj_id] = proj
    _next_proj_id += 1
    return proj


def list_projects(ws_id: int, user_id: int) -> list[Project]:
    """List projects in a workspace (if user owns it)."""
    ws = get_workspace(ws_id, user_id)
    if not ws:
        return []
    return [p for p in _projects.values() if p.workspace_id == ws_id]


def get_project(proj_id: int, user_id: int) -> Optional[Project]:
    """Get a project if it belongs to the user."""
    proj = _projects.get(proj_id)
    if proj and proj.user_id == user_id:
        return proj
    return None


def reset_workspaces():
    """Reset all workspace data (for tests)."""
    global _workspaces, _projects, _next_ws_id, _next_proj_id
    _workspaces.clear()
    _projects.clear()
    _next_ws_id = 1
    _next_proj_id = 1
