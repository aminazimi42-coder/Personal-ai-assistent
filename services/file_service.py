"""
services/file_service.py — User-scoped file upload, storage, and retrieval.

Security:
  - Size cap (FILE_MAX_UPLOAD_BYTES)
  - MIME allowlist (FILE_ALLOWED_MIME_TYPES)
  - Filename sanitized (basename only, no path traversal)
  - Stored outside the git repo (FILE_STORAGE_DIR)
  - Owner user_id only — users can only GET/DELETE their own files
  - Never logs file bytes or document text

Table: user_files
  (id, user_id, filename, content_type, size_bytes, stored_path, created_at)
"""

import logging
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from psycopg2.extras import RealDictCursor

from config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# DB availability check (cached — same pattern as usage_service)
# ------------------------------------------------------------------ #

_db_available: bool | None = None


def _is_db_available(get_connection_fn) -> bool:
    """Check whether the user_files table exists (cached)."""
    global _db_available
    if _db_available is not None:
        return _db_available
    if get_connection_fn is None:
        _db_available = False
        return False
    try:
        conn = get_connection_fn()
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'user_files'
            )
        """)
        result = cur.fetchone()
        cur.close()
        from db.pool import return_connection
        return_connection(conn)
        _db_available = bool(result[0]) if result else False
    except Exception:
        _db_available = False
    return _db_available

# ------------------------------------------------------------------ #
# Configuration
# ------------------------------------------------------------------ #

FILE_STORAGE_DIR: str = getattr(
    settings, "FILE_STORAGE_DIR",
    os.path.join(os.getcwd(), "data", "uploads"),
)
FILE_MAX_UPLOAD_BYTES: int = getattr(
    settings, "FILE_MAX_UPLOAD_BYTES", 25 * 1024 * 1024,  # 25 MB
)
FILE_ALLOWED_MIME_TYPES: frozenset = frozenset(
    getattr(settings, "FILE_ALLOWED_MIME_TYPES", [
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
        "text/plain",
        "text/markdown",
    ])
)

# ------------------------------------------------------------------ #
# In-memory store (used only when no DB connection is available — tests)
# ------------------------------------------------------------------ #

_lock = threading.Lock()
_mem_files: dict[int, dict] = {}
_mem_next_id = 1


def _reset_mem_store():
    """Reset in-memory file store (for tests)."""
    global _mem_files, _mem_next_id, _db_available
    with _lock:
        _mem_files = {}
        _mem_next_id = 1
    _db_available = None


# ------------------------------------------------------------------ #
# Filename sanitization
# ------------------------------------------------------------------ #

_UNSAFE_RE = re.compile(r"[^a-zA-Z0-9._\-\s]")
_MAX_FILENAME_LEN = 200


def sanitize_filename(raw: str) -> str:
    """
    Sanitize a filename for safe storage.

    - Strips path components (basename only)
    - Replaces unsafe characters
    - Truncates to a reasonable length
    - Prefixes with a UUID to avoid collisions
    """
    if not raw:
        raw = "upload"
    # Take only the basename — strip any path components
    name = os.path.basename(raw)
    # Replace unsafe characters with underscore
    name = _UNSAFE_RE.sub("_", name)
    # Collapse whitespace
    name = re.sub(r"\s+", "_", name.strip())
    # Truncate
    if len(name) > _MAX_FILENAME_LEN:
        base, ext = os.path.splitext(name)
        name = base[: _MAX_FILENAME_LEN - len(ext)] + ext
    if not name:
        name = "upload"
    # Prefix with UUID for uniqueness and to prevent predictable paths
    unique = uuid.uuid4().hex[:12]
    base, ext = os.path.splitext(name)
    return f"{unique}_{base}{ext}"


# ------------------------------------------------------------------ #
# MIME validation
# ------------------------------------------------------------------ #

def validate_mime(content_type: str) -> None:
    """Raise ValueError if the MIME type is not in the allowlist."""
    if not content_type:
        raise ValueError("Content-Type is required")
    # Normalize charset suffix (e.g., "text/plain; charset=utf-8")
    ct = content_type.split(";")[0].strip().lower()
    if ct not in FILE_ALLOWED_MIME_TYPES:
        raise ValueError(
            f"Unsupported file type: {ct}. "
            f"Allowed: {', '.join(sorted(FILE_ALLOWED_MIME_TYPES))}"
        )


# ------------------------------------------------------------------ #
# Size validation
# ------------------------------------------------------------------ #

def validate_size(data: bytes) -> None:
    """Raise ValueError if the data is empty or exceeds the size cap."""
    if not data or len(data) == 0:
        raise ValueError("File is empty")
    if len(data) > FILE_MAX_UPLOAD_BYTES:
        raise ValueError(
            f"File too large (max {FILE_MAX_UPLOAD_BYTES // (1024 * 1024)} MB)"
        )


# ------------------------------------------------------------------ #
# Storage
# ------------------------------------------------------------------ #

def _ensure_storage_dir():
    """Ensure the storage directory exists."""
    os.makedirs(FILE_STORAGE_DIR, exist_ok=True)


def _stored_path(safe_name: str) -> str:
    """Return the full path for a stored file."""
    return os.path.join(FILE_STORAGE_DIR, safe_name)


# ------------------------------------------------------------------ #
# Serialization
# ------------------------------------------------------------------ #

def serialize_file(row: dict) -> dict:
    """Serialize a file record for API responses (no file content)."""
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "filename": row["filename"],
        "content_type": row["content_type"],
        "size_bytes": row["size_bytes"],
        "created_at": row["created_at"].isoformat() if isinstance(
            row.get("created_at"), datetime
        ) else row.get("created_at"),
    }


# ------------------------------------------------------------------ #
# CRUD
# ------------------------------------------------------------------ #

def create_file(
    user_id: int,
    filename: str,
    content_type: str,
    file_data: bytes,
    get_connection_fn=None,
) -> dict:
    """
    Validate, store, and record a user file upload.

    Returns the serialized file record.
    Never logs file bytes or document text.
    """
    # Validate
    ct = (content_type or "").split(";")[0].strip().lower()
    validate_mime(ct)
    validate_size(file_data)

    safe_name = sanitize_filename(filename)

    # Store on disk
    _ensure_storage_dir()
    dest = _stored_path(safe_name)
    with open(dest, "wb") as f:
        f.write(file_data)

    size_bytes = len(file_data)

    # --- No DB connection → in-memory (tests) ---
    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        return _mem_create(user_id, safe_name, ct, size_bytes, dest)

    # --- DB-backed (production) ---
    from db.pool import return_connection
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO user_files
                (user_id, filename, content_type, size_bytes, stored_path)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, user_id, filename, content_type, size_bytes, created_at
        """, (user_id, safe_name, ct, size_bytes, dest))
        row = cur.fetchone()
        conn.commit()
    finally:
        cur.close()
        return_connection(conn)

    return serialize_file(dict(row))


def _mem_create(user_id, filename, ct, size_bytes, stored_path):
    global _mem_next_id
    with _lock:
        fid = _mem_next_id
        _mem_next_id += 1
        record = {
            "id": fid,
            "user_id": user_id,
            "filename": filename,
            "content_type": ct,
            "size_bytes": size_bytes,
            "stored_path": stored_path,
            "created_at": datetime.now(timezone.utc),
        }
        _mem_files[fid] = record
    return serialize_file(record)


def list_files(user_id: int, get_connection_fn=None) -> list[dict]:
    """List all files owned by a user."""
    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        with _lock:
            return [
                serialize_file(dict(r))
                for r in _mem_files.values()
                if r["user_id"] == user_id
            ]

    from db.pool import return_connection
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, user_id, filename, content_type, size_bytes, created_at
            FROM user_files
            WHERE user_id = %s
            ORDER BY created_at DESC, id DESC
        """, (user_id,))
        rows = cur.fetchall()
    finally:
        cur.close()
        return_connection(conn)
    return [serialize_file(dict(r)) for r in rows]


def get_file(
    file_id: int, user_id: int, get_connection_fn=None
) -> Optional[dict]:
    """Get a single file record — only if owned by user_id."""
    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        with _lock:
            r = _mem_files.get(file_id)
            if r and r["user_id"] == user_id:
                return serialize_file(dict(r))
            return None

    from db.pool import return_connection
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, user_id, filename, content_type, size_bytes, created_at
            FROM user_files
            WHERE id = %s AND user_id = %s
        """, (file_id, user_id))
        row = cur.fetchone()
    finally:
        cur.close()
        return_connection(conn)
    return serialize_file(dict(row)) if row else None


def delete_file(
    file_id: int, user_id: int, get_connection_fn=None
) -> bool:
    """
    Delete a file — only if owned by user_id.
    Removes both the DB record and the on-disk file.

    Returns True if deleted, False if not found or not owned.
    """
    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        with _lock:
            r = _mem_files.get(file_id)
            if not r or r["user_id"] != user_id:
                return False
            # Remove on-disk file
            try:
                os.remove(r["stored_path"])
            except OSError:
                pass
            del _mem_files[file_id]
            return True

    from db.pool import return_connection
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Fetch the stored_path first (owner check)
        cur.execute("""
            SELECT id, user_id, stored_path
            FROM user_files
            WHERE id = %s AND user_id = %s
        """, (file_id, user_id))
        row = cur.fetchone()
        if not row:
            return False

        # Delete the DB record
        cur.execute("""
            DELETE FROM user_files WHERE id = %s AND user_id = %s
        """, (file_id, user_id))
        conn.commit()

        # Remove on-disk file
        try:
            os.remove(row["stored_path"])
        except OSError:
            logger.warning("Failed to remove file on disk: %s", row["stored_path"])
        return True
    finally:
        cur.close()
        return_connection(conn)
