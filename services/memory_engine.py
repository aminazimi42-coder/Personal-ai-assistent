"""
services/memory_engine.py
Personal AI Memory Engine — layered memory for the assistant.

Layers:
  1. Short-term: current conversation context (transient)
  2. Task memory: notes attached to specific tasks
  3. Long-term preferences: user-level settings/facts
  4. Project memory: notes attached to projects/repositories

All memory is user-scoped — strict isolation between users.
Memory is stored in the database (memories table) with:
  - user_id (FK to users)
  - memory_type (short_term, task, preference, project)
  - key (string identifier)
  - value (text content)
  - created_at, updated_at
  - relevance_score (for ranking)

User controls: set, get, search, delete, list memories.
Privacy boundaries: memories never cross user boundaries.
Retention: short_term expires, others persist until deleted.
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Memory types
# ------------------------------------------------------------------ #
MEMORY_TYPES = frozenset({"short_term", "task", "preference", "project"})

# Retention: short_term memories expire after 24h
SHORT_TERM_TTL_SECONDS = 24 * 60 * 60


@dataclass
class Memory:
    """A memory entry."""
    id: Optional[int] = None
    user_id: int = 0
    memory_type: str = ""
    key: str = ""
    value: str = ""
    relevance_score: float = 1.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ------------------------------------------------------------------ #
# In-memory store (for tests/dev — DB-backed in production)
# ------------------------------------------------------------------ #
_store_lock = None
_store: dict[int, list[Memory]] = {}


def _get_store_lock():
    global _store_lock
    if _store_lock is None:
        import threading
        _store_lock = threading.Lock()
    return _store_lock


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_expired(mem: Memory) -> bool:
    """Check if a short_term memory has expired."""
    if mem.memory_type != "short_term":
        return False
    if not mem.created_at:
        return False
    try:
        created = datetime.fromisoformat(mem.created_at)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - created).total_seconds()
        return age > SHORT_TERM_TTL_SECONDS
    except Exception:
        return False


# ------------------------------------------------------------------ #
# CRUD operations
# ------------------------------------------------------------------ #

def set_memory(
    user_id: int,
    memory_type: str,
    key: str,
    value: str,
    relevance_score: float = 1.0,
    get_connection_fn=None,
) -> Memory:
    """
    Create or update a memory entry.
    Validates memory_type and enforces user isolation.
    """
    if memory_type not in MEMORY_TYPES:
        raise ValueError(f"Invalid memory type: {memory_type}. Must be one of {MEMORY_TYPES}")

    if not key or not key.strip():
        raise ValueError("Memory key is required")

    if not value or not value.strip():
        raise ValueError("Memory value is required")

    if len(value) > 10000:
        raise ValueError("Memory value too long (max 10000 chars)")

    key = key.strip()[:200]
    value = value.strip()

    mem = Memory(
        user_id=user_id,
        memory_type=memory_type,
        key=key,
        value=value,
        relevance_score=relevance_score,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )

    # DB-backed (production)
    if get_connection_fn:
        try:
            return _db_set_memory(mem, get_connection_fn)
        except Exception as exc:
            logger.warning("DB memory set failed, using in-memory: %s", exc)

    # In-memory fallback
    with _get_store_lock():
        user_mems = _store.setdefault(user_id, [])
        # Replace existing with same type+key
        for i, existing in enumerate(user_mems):
            if existing.memory_type == memory_type and existing.key == key:
                mem.id = existing.id
                user_mems[i] = mem
                break
        else:
            mem.id = len(user_mems) + 1
            user_mems.append(mem)

    return mem


def get_memory(
    user_id: int,
    memory_type: str,
    key: str,
    get_connection_fn=None,
) -> Optional[Memory]:
    """Get a specific memory by type and key. Returns None if not found."""
    if memory_type not in MEMORY_TYPES:
        raise ValueError(f"Invalid memory type: {memory_type}")

    if get_connection_fn:
        try:
            return _db_get_memory(user_id, memory_type, key, get_connection_fn)
        except Exception:
            pass

    with _get_store_lock():
        user_mems = _store.get(user_id, [])
        for mem in user_mems:
            if mem.memory_type == memory_type and mem.key == key:
                if _is_expired(mem):
                    return None
                return mem
    return None


def search_memories(
    user_id: int,
    query: str,
    memory_type: Optional[str] = None,
    limit: int = 10,
    get_connection_fn=None,
) -> list[Memory]:
    """
    Search memories by keyword in key and value.
    Returns results sorted by relevance score.
    """
    if memory_type and memory_type not in MEMORY_TYPES:
        raise ValueError(f"Invalid memory type: {memory_type}")

    if not query or not query.strip():
        return []

    query_lower = query.strip().lower()

    if get_connection_fn:
        try:
            return _db_search_memories(user_id, query_lower, memory_type, limit, get_connection_fn)
        except Exception:
            pass

    results = []
    with _get_store_lock():
        user_mems = _store.get(user_id, [])
        for mem in user_mems:
            if _is_expired(mem):
                continue
            if memory_type and mem.memory_type != memory_type:
                continue
            # Simple keyword search
            key_match = query_lower in mem.key.lower()
            value_match = query_lower in mem.value.lower()
            if key_match or value_match:
                results.append(mem)

    results.sort(key=lambda m: m.relevance_score, reverse=True)
    return results[:limit]


def delete_memory(
    user_id: int,
    memory_type: str,
    key: str,
    get_connection_fn=None,
) -> bool:
    """Delete a memory by type and key. Returns True if deleted."""
    if memory_type not in MEMORY_TYPES:
        raise ValueError(f"Invalid memory type: {memory_type}")

    if get_connection_fn:
        try:
            return _db_delete_memory(user_id, memory_type, key, get_connection_fn)
        except Exception:
            pass

    with _get_store_lock():
        user_mems = _store.get(user_id, [])
        for i, mem in enumerate(user_mems):
            if mem.memory_type == memory_type and mem.key == key:
                user_mems.pop(i)
                return True
    return False


def list_memories(
    user_id: int,
    memory_type: Optional[str] = None,
    limit: int = 50,
    get_connection_fn=None,
) -> list[Memory]:
    """List all memories for a user, optionally filtered by type."""
    if memory_type and memory_type not in MEMORY_TYPES:
        raise ValueError(f"Invalid memory type: {memory_type}")

    if get_connection_fn:
        try:
            return _db_list_memories(user_id, memory_type, limit, get_connection_fn)
        except Exception:
            pass

    with _get_store_lock():
        user_mems = _store.get(user_id, [])
        results = [
            mem for mem in user_mems
            if not _is_expired(mem) and (not memory_type or mem.memory_type == memory_type)
        ]
    return results[:limit]


def clear_user_memories(user_id: int, get_connection_fn=None) -> int:
    """Clear all memories for a user. Returns count deleted."""
    if get_connection_fn:
        try:
            return _db_clear_user_memories(user_id, get_connection_fn)
        except Exception:
            pass

    with _get_store_lock():
        count = len(_store.get(user_id, []))
        _store.pop(user_id, None)
        return count


# ------------------------------------------------------------------ #
# DB-backed operations (used in production)
# ------------------------------------------------------------------ #
def _db_set_memory(mem: Memory, get_connection_fn) -> Memory:
    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO memories (user_id, memory_type, key, value, relevance_score, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (user_id, memory_type, key)
            DO UPDATE SET value = EXCLUDED.value, relevance_score = EXCLUDED.relevance_score, updated_at = NOW()
            RETURNING id, created_at, updated_at
        """, (mem.user_id, mem.memory_type, mem.key, mem.value, mem.relevance_score))
        row = cur.fetchone()
        conn.commit()
        mem.id = row["id"] if row else None
        mem.created_at = str(row["created_at"]) if row else None
        mem.updated_at = str(row["updated_at"]) if row else None
    finally:
        cur.close()
        return_connection(conn)
    return mem


def _db_get_memory(user_id, memory_type, key, get_connection_fn) -> Optional[Memory]:
    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, user_id, memory_type, key, value, relevance_score, created_at, updated_at
            FROM memories
            WHERE user_id = %s AND memory_type = %s AND key = %s
        """, (user_id, memory_type, key))
        row = cur.fetchone()
    finally:
        cur.close()
        return_connection(conn)
    if not row:
        return None
    return Memory(
        id=row["id"], user_id=row["user_id"], memory_type=row["memory_type"],
        key=row["key"], value=row["value"], relevance_score=float(row["relevance_score"]),
        created_at=str(row["created_at"]), updated_at=str(row["updated_at"]),
    )


def _db_search_memories(user_id, query, memory_type, limit, get_connection_fn) -> list[Memory]:
    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if memory_type:
            cur.execute("""
                SELECT id, user_id, memory_type, key, value, relevance_score, created_at, updated_at
                FROM memories
                WHERE user_id = %s AND memory_type = %s
                  AND (key ILIKE %s OR value ILIKE %s)
                ORDER BY relevance_score DESC
                LIMIT %s
            """, (user_id, memory_type, f"%{query}%", f"%{query}%", limit))
        else:
            cur.execute("""
                SELECT id, user_id, memory_type, key, value, relevance_score, created_at, updated_at
                FROM memories
                WHERE user_id = %s
                  AND (key ILIKE %s OR value ILIKE %s)
                ORDER BY relevance_score DESC
                LIMIT %s
            """, (user_id, f"%{query}%", f"%{query}%", limit))
        rows = cur.fetchall()
    finally:
        cur.close()
        return_connection(conn)
    return [Memory(
        id=r["id"], user_id=r["user_id"], memory_type=r["memory_type"],
        key=r["key"], value=r["value"], relevance_score=float(r["relevance_score"]),
        created_at=str(r["created_at"]), updated_at=str(r["updated_at"]),
    ) for r in rows]


def _db_delete_memory(user_id, memory_type, key, get_connection_fn) -> bool:
    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            DELETE FROM memories
            WHERE user_id = %s AND memory_type = %s AND key = %s
            RETURNING id
        """, (user_id, memory_type, key))
        row = cur.fetchone()
        conn.commit()
    finally:
        cur.close()
        return_connection(conn)
    return row is not None


def _db_list_memories(user_id, memory_type, limit, get_connection_fn) -> list[Memory]:
    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if memory_type:
            cur.execute("""
                SELECT id, user_id, memory_type, key, value, relevance_score, created_at, updated_at
                FROM memories
                WHERE user_id = %s AND memory_type = %s
                ORDER BY relevance_score DESC, updated_at DESC
                LIMIT %s
            """, (user_id, memory_type, limit))
        else:
            cur.execute("""
                SELECT id, user_id, memory_type, key, value, relevance_score, created_at, updated_at
                FROM memories
                WHERE user_id = %s
                ORDER BY relevance_score DESC, updated_at DESC
                LIMIT %s
            """, (user_id, limit))
        rows = cur.fetchall()
    finally:
        cur.close()
        return_connection(conn)
    return [Memory(
        id=r["id"], user_id=r["user_id"], memory_type=r["memory_type"],
        key=r["key"], value=r["value"], relevance_score=float(r["relevance_score"]),
        created_at=str(r["created_at"]), updated_at=str(r["updated_at"]),
    ) for r in rows]


def _db_clear_user_memories(user_id, get_connection_fn) -> int:
    from psycopg2.extras import RealDictCursor
    from db.pool import return_connection
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("DELETE FROM memories WHERE user_id = %s RETURNING id", (user_id,))
        rows = cur.fetchall()
        conn.commit()
    finally:
        cur.close()
        return_connection(conn)
    return len(rows)
