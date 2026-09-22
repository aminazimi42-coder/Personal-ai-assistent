"""
services/tenant_service.py
Multi-Tenant / Workspace identity, memberships, roles, access control.

Tenant model:
  - Tenant: id, name, slug, owner_user_id, created_at
  - TenantMembership: tenant_id, user_id, role (owner/admin/member)

All operations are user-isolated with ownership/membership checks.
Uses raw psycopg2 with RealDictCursor (matches the rest of the codebase).
A thread-safe in-memory store is used when no DB connection is available
(e.g., unit tests), mirroring the usage_service pattern.
"""

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

VALID_ROLES = ("owner", "admin", "member")
_SLUG_RE = re.compile(r"[^a-z0-9-]")


# ------------------------------------------------------------------ #
# In-memory store (tests only; production uses the DB)
# ------------------------------------------------------------------ #
_lock = threading.Lock()
_mem_tenants: dict[int, dict] = {}
_mem_memberships: dict[int, dict] = {}
_mem_next_tenant_id = 1
_mem_next_membership_id = 1


def _reset_mem_store():
    """Reset in-memory data (for tests)."""
    global _mem_tenants, _mem_memberships, _mem_next_tenant_id, _mem_next_membership_id
    with _lock:
        _mem_tenants.clear()
        _mem_memberships.clear()
        _mem_next_tenant_id = 1
        _mem_next_membership_id = 1


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _slugify(name: str) -> str:
    """Create a URL-safe slug from a name."""
    slug = name.strip().lower()
    slug = _SLUG_RE.sub("-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "tenant"


def _is_db_available(get_connection_fn) -> bool:
    """Check whether the tenants table exists (cached per call)."""
    if get_connection_fn is None:
        return False
    try:
        conn = get_connection_fn()
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'tenants'
            )
        """)
        result = cur.fetchone()
        cur.close()
        from db.pool import return_connection
        return_connection(conn)
        return bool(result[0]) if result else False
    except Exception:
        return False


def _serialize_tenant(row: dict) -> dict:
    """Serialize a tenant row to a plain dict."""
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "owner_user_id": row["owner_user_id"],
        "created_at": (
            row["created_at"].isoformat()
            if row.get("created_at") and hasattr(row["created_at"], "isoformat")
            else row.get("created_at")
        ),
    }


def _serialize_membership(row: dict) -> dict:
    """Serialize a membership row to a plain dict."""
    return {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "user_id": row["user_id"],
        "role": row["role"],
        "created_at": (
            row["created_at"].isoformat()
            if row.get("created_at") and hasattr(row["created_at"], "isoformat")
            else row.get("created_at")
        ),
    }


# ------------------------------------------------------------------ #
# Public API
# ------------------------------------------------------------------ #

def create_tenant(name: str, owner_user_id: int, get_connection_fn=None) -> dict:
    """
    Create a new tenant with the given owner.

    The owner automatically becomes a member with role 'owner'.
    Returns the serialized tenant dict.
    Raises ValueError on invalid input.
    """
    if not name or not name.strip():
        raise ValueError("Tenant name is required")
    name = name.strip()[:200]
    owner_user_id = int(owner_user_id)

    # --- In-memory path (tests) ---
    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        return _mem_create_tenant(name, owner_user_id)

    # --- DB path (production) ---
    slug = _slugify(name)
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Ensure slug uniqueness by appending a suffix if needed
        base_slug = slug
        suffix = 0
        while True:
            cur.execute(
                "SELECT 1 FROM tenants WHERE slug = %s", (slug,)
            )
            if not cur.fetchone():
                break
            suffix += 1
            slug = f"{base_slug}-{suffix}"

        cur.execute("""
            INSERT INTO tenants (name, slug, owner_user_id)
            VALUES (%s, %s, %s)
            RETURNING id, name, slug, owner_user_id, created_at
        """, (name, slug, owner_user_id))
        tenant = cur.fetchone()

        # Auto-create owner membership
        cur.execute("""
            INSERT INTO tenant_memberships (tenant_id, user_id, role)
            VALUES (%s, %s, 'owner')
            RETURNING id, tenant_id, user_id, role, created_at
        """, (tenant["id"], owner_user_id))
        membership = cur.fetchone()

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        from db.pool import return_connection
        return_connection(conn)

    logger.info("Tenant created: id=%s owner=%s", tenant["id"], owner_user_id)
    return _serialize_tenant(dict(tenant))


def _mem_create_tenant(name: str, owner_user_id: int) -> dict:
    """In-memory tenant creation (for tests)."""
    global _mem_next_tenant_id, _mem_next_membership_id
    with _lock:
        slug = _slugify(name)
        # Ensure slug uniqueness in memory
        existing_slugs = {t["slug"] for t in _mem_tenants.values()}
        base_slug = slug
        suffix = 0
        while slug in existing_slugs:
            suffix += 1
            slug = f"{base_slug}-{suffix}"

        tid = _mem_next_tenant_id
        _mem_next_tenant_id += 1
        tenant = {
            "id": tid,
            "name": name,
            "slug": slug,
            "owner_user_id": owner_user_id,
            "created_at": datetime.now(timezone.utc),
        }
        _mem_tenants[tid] = tenant

        mid = _mem_next_membership_id
        _mem_next_membership_id += 1
        _mem_memberships[mid] = {
            "id": mid,
            "tenant_id": tid,
            "user_id": owner_user_id,
            "role": "owner",
            "created_at": datetime.now(timezone.utc),
        }

    return _serialize_tenant(tenant)


def add_member(tenant_id: int, user_id: int, role: str = "member",
               get_connection_fn=None) -> dict:
    """
    Add a user to a tenant with a given role.

    Raises ValueError if the role is invalid or the membership already exists.
    Returns the serialized membership dict.
    """
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}. Must be one of {VALID_ROLES}")

    tenant_id = int(tenant_id)
    user_id = int(user_id)

    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        return _mem_add_member(tenant_id, user_id, role)

    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO tenant_memberships (tenant_id, user_id, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (tenant_id, user_id) DO UPDATE SET role = EXCLUDED.role
            RETURNING id, tenant_id, user_id, role, created_at
        """, (tenant_id, user_id, role))
        membership = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        from db.pool import return_connection
        return_connection(conn)

    return _serialize_membership(dict(membership))


def _mem_add_member(tenant_id: int, user_id: int, role: str) -> dict:
    """In-memory add member (for tests)."""
    global _mem_next_membership_id
    with _lock:
        # Check if membership already exists
        for m in _mem_memberships.values():
            if m["tenant_id"] == tenant_id and m["user_id"] == user_id:
                m["role"] = role
                return _serialize_membership(m)

        mid = _mem_next_membership_id
        _mem_next_membership_id += 1
        membership = {
            "id": mid,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": role,
            "created_at": datetime.now(timezone.utc),
        }
        _mem_memberships[mid] = membership
    return _serialize_membership(membership)


def list_members(tenant_id: int, requesting_user_id: int,
                 get_connection_fn=None) -> list:
    """
    List members of a tenant.

    The requesting user must be a member of the tenant.
    Returns a list of serialized membership dicts.
    Raises PermissionError if the requesting user is not a member.
    """
    tenant_id = int(tenant_id)
    requesting_user_id = int(requesting_user_id)

    if not check_tenant_access(tenant_id, requesting_user_id, get_connection_fn):
        raise PermissionError(
            "User does not have access to this tenant"
        )

    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        return _mem_list_members(tenant_id)

    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, tenant_id, user_id, role, created_at
            FROM tenant_memberships
            WHERE tenant_id = %s
            ORDER BY id
        """, (tenant_id,))
        rows = cur.fetchall()
    finally:
        cur.close()
        from db.pool import return_connection
        return_connection(conn)

    return [_serialize_membership(dict(r)) for r in rows]


def _mem_list_members(tenant_id: int) -> list:
    """In-memory list members (for tests)."""
    with _lock:
        rows = [dict(m) for m in _mem_memberships.values()
                if m["tenant_id"] == tenant_id]
    return [_serialize_membership(r) for r in rows]


def get_user_tenants(user_id: int, get_connection_fn=None) -> list:
    """
    List all tenants the user is a member of.
    Returns a list of serialized tenant dicts.
    """
    user_id = int(user_id)

    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        return _mem_get_user_tenants(user_id)

    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT t.id, t.name, t.slug, t.owner_user_id, t.created_at,
                   tm.role
            FROM tenants t
            INNER JOIN tenant_memberships tm
                ON tm.tenant_id = t.id AND tm.user_id = %s
            ORDER BY t.id
        """, (user_id,))
        rows = cur.fetchall()
    finally:
        cur.close()
        from db.pool import return_connection
        return_connection(conn)

    return [_serialize_tenant(dict(r)) for r in rows]


def _mem_get_user_tenants(user_id: int) -> list:
    """In-memory get user tenants (for tests)."""
    with _lock:
        tenant_ids = {m["tenant_id"] for m in _mem_memberships.values()
                      if m["user_id"] == user_id}
        result = [_serialize_tenant(dict(_mem_tenants[tid]))
                  for tid in tenant_ids if tid in _mem_tenants]
    return result


def check_tenant_access(tenant_id: int, user_id: int,
                        get_connection_fn=None) -> bool:
    """
    Check whether a user has access to a tenant (is a member).
    Returns True if the user is a member, False otherwise.
    """
    tenant_id = int(tenant_id)
    user_id = int(user_id)

    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        return _mem_check_tenant_access(tenant_id, user_id)

    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT 1 FROM tenant_memberships
            WHERE tenant_id = %s AND user_id = %s
        """, (tenant_id, user_id))
        return cur.fetchone() is not None
    finally:
        cur.close()
        from db.pool import return_connection
        return_connection(conn)


def _mem_check_tenant_access(tenant_id: int, user_id: int) -> bool:
    """In-memory check tenant access (for tests)."""
    with _lock:
        return any(
            m["tenant_id"] == tenant_id and m["user_id"] == user_id
            for m in _mem_memberships.values()
        )


def get_tenant(tenant_id: int, get_connection_fn=None) -> Optional[dict]:
    """
    Get a tenant by ID.
    Returns the serialized tenant dict or None if not found.
    """
    tenant_id = int(tenant_id)

    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        with _lock:
            t = _mem_tenants.get(tenant_id)
            return _serialize_tenant(dict(t)) if t else None

    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, name, slug, owner_user_id, created_at
            FROM tenants WHERE id = %s
        """, (tenant_id,))
        row = cur.fetchone()
    finally:
        cur.close()
        from db.pool import return_connection
        return_connection(conn)

    return _serialize_tenant(dict(row)) if row else None
