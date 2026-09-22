"""
services/workspace.py
Project Workspace — structured workspaces with ownership and isolation.

Workspace → Projects / Files / Code / Documents / Tasks / Conversations /
Memories / AI Context

Features:
- Ownership: each workspace belongs to a user
- Isolation: users can only access their own workspaces
- Access control: user-scoped queries
- DB-backed in production; in-memory fallback when get_connection is None
- Durable: state persists across restarts when DB is available
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class Workspace:
    """A user workspace."""
    id: Optional[int] = None
    name: str = ""
    user_id: int = 0
    description: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    projects: list = field(default_factory=list)


@dataclass
class Project:
    """A project within a workspace."""
    id: Optional[int] = None
    workspace_id: int = 0
    name: str = ""
    description: str = ""
    user_id: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ------------------------------------------------------------------ #
# In-memory fallback (used when get_connection is None — unit tests)
# ------------------------------------------------------------------ #
_workspaces: dict[int, Workspace] = {}
_projects: dict[int, Project] = {}
_next_ws_id = 1
_next_proj_id = 1


def _ws_to_dict(ws: Workspace) -> dict:
    return {
        "id": ws.id,
        "name": ws.name,
        "user_id": ws.user_id,
        "description": ws.description,
        "created_at": ws.created_at,
        "updated_at": ws.updated_at,
    }


def _proj_to_dict(proj: Project) -> dict:
    return {
        "id": proj.id,
        "workspace_id": proj.workspace_id,
        "name": proj.name,
        "description": proj.description,
        "user_id": proj.user_id,
        "created_at": proj.created_at,
        "updated_at": proj.updated_at,
    }


def _dict_to_ws(row: dict) -> Workspace:
    return Workspace(
        id=row.get("id"),
        name=row.get("name", ""),
        user_id=row.get("user_id", 0),
        description=row.get("description", ""),
        created_at=str(row["created_at"]) if row.get("created_at") else None,
        updated_at=str(row["updated_at"]) if row.get("updated_at") else None,
    )


def _dict_to_proj(row: dict) -> Project:
    return Project(
        id=row.get("id"),
        workspace_id=row.get("workspace_id", 0),
        name=row.get("name", ""),
        description=row.get("description", ""),
        user_id=row.get("user_id", 0),
        created_at=str(row["created_at"]) if row.get("created_at") else None,
        updated_at=str(row["updated_at"]) if row.get("updated_at") else None,
    )


# ------------------------------------------------------------------ #
# Workspace CRUD
# ------------------------------------------------------------------ #

def create_workspace(user_id: int, name: str, description: str = "",
                     get_connection: Optional[Callable] = None) -> Workspace:
    """Create a new workspace for a user.

    When get_connection is provided, persists to DB.
    Otherwise, uses in-memory fallback (for unit tests without DB).
    """
    if not name or not name.strip():
        raise ValueError("Workspace name is required")

    clean_name = name.strip()[:200]
    clean_desc = description.strip()[:1000]

    if get_connection is None:
        return _create_workspace_mem(user_id, clean_name, clean_desc)

    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO workspaces (name, user_id, description)
            VALUES (%s, %s, %s)
            RETURNING id, name, user_id, description, created_at, updated_at
        """, (clean_name, user_id, clean_desc))
        row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        return_connection(conn)

    return _dict_to_ws(dict(row))


def _create_workspace_mem(user_id: int, name: str, description: str) -> Workspace:
    global _next_ws_id
    now = datetime.now(timezone.utc).isoformat()
    ws = Workspace(
        id=_next_ws_id,
        name=name,
        user_id=user_id,
        description=description,
        created_at=now,
        updated_at=now,
    )
    _workspaces[_next_ws_id] = ws
    _next_ws_id += 1
    return ws


def get_workspace(ws_id: int, user_id: int,
                  get_connection: Optional[Callable] = None) -> Optional[Workspace]:
    """Get a workspace if it belongs to the user."""
    if get_connection is None:
        ws = _workspaces.get(ws_id)
        if ws and ws.user_id == user_id:
            return ws
        return None

    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, name, user_id, description, created_at, updated_at
            FROM workspaces
            WHERE id = %s AND user_id = %s
        """, (ws_id, user_id))
        row = cur.fetchone()
    finally:
        cur.close()
        return_connection(conn)

    if not row:
        return None
    return _dict_to_ws(dict(row))


def list_workspaces(user_id: int,
                    get_connection: Optional[Callable] = None) -> list:
    """List all workspaces for a user."""
    if get_connection is None:
        return [ws for ws in _workspaces.values() if ws.user_id == user_id]

    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, name, user_id, description, created_at, updated_at
            FROM workspaces
            WHERE user_id = %s
            ORDER BY id DESC
        """, (user_id,))
        rows = cur.fetchall()
    finally:
        cur.close()
        return_connection(conn)

    return [_dict_to_ws(dict(r)) for r in rows]


def delete_workspace(ws_id: int, user_id: int,
                     get_connection: Optional[Callable] = None) -> bool:
    """Delete a workspace if it belongs to the user. Cascades to projects."""
    if get_connection is None:
        return _delete_workspace_mem(ws_id, user_id)

    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # CASCADE on FK handles projects automatically
        cur.execute("""
            DELETE FROM workspaces
            WHERE id = %s AND user_id = %s
            RETURNING id
        """, (ws_id, user_id))
        row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        return_connection(conn)

    return row is not None


def _delete_workspace_mem(ws_id: int, user_id: int) -> bool:
    ws = _workspaces.get(ws_id)
    if ws and ws.user_id == user_id:
        del _workspaces[ws_id]
        # Cascade delete associated projects
        to_del = [pid for pid, p in _projects.items() if p.workspace_id == ws_id]
        for pid in to_del:
            del _projects[pid]
        return True
    return False


# ------------------------------------------------------------------ #
# Project CRUD
# ------------------------------------------------------------------ #

def create_project(ws_id: int, user_id: int, name: str, description: str = "",
                    get_connection: Optional[Callable] = None) -> Optional[Project]:
    """Create a project in a workspace (if user owns it)."""
    if not name or not name.strip():
        raise ValueError("Project name is required")

    clean_name = name.strip()[:200]
    clean_desc = description.strip()[:1000]

    if get_connection is None:
        return _create_project_mem(ws_id, user_id, clean_name, clean_desc)

    # Verify workspace ownership
    ws = get_workspace(ws_id, user_id, get_connection)
    if not ws:
        return None

    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO projects (workspace_id, user_id, name, description)
            VALUES (%s, %s, %s, %s)
            RETURNING id, workspace_id, user_id, name, description,
                      created_at, updated_at
        """, (ws_id, user_id, clean_name, clean_desc))
        row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        return_connection(conn)

    return _dict_to_proj(dict(row))


def _create_project_mem(ws_id: int, user_id: int, name: str,
                         description: str) -> Optional[Project]:
    global _next_proj_id
    ws = _workspaces.get(ws_id)
    if not ws or ws.user_id != user_id:
        return None
    now = datetime.now(timezone.utc).isoformat()
    proj = Project(
        id=_next_proj_id,
        workspace_id=ws_id,
        name=name,
        description=description,
        user_id=user_id,
        created_at=now,
        updated_at=now,
    )
    _projects[_next_proj_id] = proj
    _next_proj_id += 1
    return proj


def list_projects(ws_id: int, user_id: int,
                  get_connection: Optional[Callable] = None) -> list:
    """List projects in a workspace (if user owns it)."""
    if get_connection is None:
        ws = _workspaces.get(ws_id)
        if not ws or ws.user_id != user_id:
            return []
        return [p for p in _projects.values() if p.workspace_id == ws_id]

    # Verify workspace ownership
    ws = get_workspace(ws_id, user_id, get_connection)
    if not ws:
        return []

    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, workspace_id, user_id, name, description,
                   created_at, updated_at
            FROM projects
            WHERE workspace_id = %s AND user_id = %s
            ORDER BY id DESC
        """, (ws_id, user_id))
        rows = cur.fetchall()
    finally:
        cur.close()
        return_connection(conn)

    return [_dict_to_proj(dict(r)) for r in rows]


def get_project(proj_id: int, user_id: int,
                get_connection: Optional[Callable] = None) -> Optional[Project]:
    """Get a project if it belongs to the user."""
    if get_connection is None:
        proj = _projects.get(proj_id)
        if proj and proj.user_id == user_id:
            return proj
        return None

    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, workspace_id, user_id, name, description,
                   created_at, updated_at
            FROM projects
            WHERE id = %s AND user_id = %s
        """, (proj_id, user_id))
        row = cur.fetchone()
    finally:
        cur.close()
        return_connection(conn)

    if not row:
        return None
    return _dict_to_proj(dict(row))


def delete_project(proj_id: int, user_id: int,
                    get_connection: Optional[Callable] = None) -> bool:
    """Delete a project if it belongs to the user."""
    if get_connection is None:
        proj = _projects.get(proj_id)
        if proj and proj.user_id == user_id:
            del _projects[proj_id]
            return True
        return False

    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            DELETE FROM projects
            WHERE id = %s AND user_id = %s
            RETURNING id
        """, (proj_id, user_id))
        row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        return_connection(conn)

    return row is not None


# ------------------------------------------------------------------ #
# Test utilities
# ------------------------------------------------------------------ #

def reset_workspaces():
    """Reset all in-memory workspace data (for tests)."""
    global _workspaces, _projects, _next_ws_id, _next_proj_id
    _workspaces.clear()
    _projects.clear()
    _next_ws_id = 1
    _next_proj_id = 1
