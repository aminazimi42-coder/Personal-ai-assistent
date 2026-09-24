"""
services/write_verification.py
Write verification — read-back after create/update/delete to prove the
write actually persisted the correct row scoped by user_id.

No COMPLETE without read-back on those writes.

Persists evidence on agent_runs when that table is used (via the
agentic_execution persistence path).
"""

import logging
from typing import Optional

from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


# Tables that support write-verification read-backs.
# Each maps table name → primary key column name.
_VERIFIABLE_TABLES = {
    "tasks": "id",
    "appointments": "id",
}


def verify_write(
    user_id: int,
    table: str,
    row_id: int,
    get_connection_fn=None,
) -> dict:
    """
    Read back a row from *table* scoped by *user_id* to verify a write.

    Args:
        user_id: The owning user's ID.
        table: Table name ('tasks' or 'appointments').
        row_id: The primary key of the row to read back.
        get_connection_fn: DB connection provider.

    Returns:
        A dict with:
          - verified: bool — True if the row was found and user_id matches
          - row: dict | None — the row data (RealDictRow) or None
          - evidence: str — human-readable evidence string
    """
    if table not in _VERIFIABLE_TABLES:
        return {
            "verified": False,
            "row": None,
            "evidence": f"Table '{table}' is not verifiable",
        }

    pk_col = _VERIFIABLE_TABLES[table]

    if get_connection_fn is None:
        return {
            "verified": False,
            "row": None,
            "evidence": "No DB connection available for write verification",
        }

    try:
        from db.pool import return_connection
        conn = get_connection_fn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                f"SELECT * FROM {table} "
                f"WHERE {pk_col} = %s AND user_id = %s",
                (row_id, user_id),
            )
            row = cur.fetchone()
        finally:
            cur.close()
            return_connection(conn)

        if row:
            return {
                "verified": True,
                "row": dict(row),
                "evidence": (
                    f"Write verified: {table} row id={row_id} "
                    f"exists and belongs to user_id={user_id}"
                ),
            }
        return {
            "verified": False,
            "row": None,
            "evidence": (
                f"Write verification FAILED: {table} row id={row_id} "
                f"not found or not owned by user_id={user_id}"
            ),
        }
    except Exception as exc:
        logger.error("Write verification error: %s", exc, exc_info=True)
        return {
            "verified": False,
            "row": None,
            "evidence": f"Write verification error: {exc}",
        }


def verify_and_persist(
    user_id: int,
    table: str,
    row_id: int,
    action_id: Optional[str] = None,
    get_connection_fn=None,
) -> dict:
    """
    Verify a write and persist evidence on agent_runs if action_id is given.

    Returns the verification dict (same shape as verify_write).
    """
    result = verify_write(user_id, table, row_id, get_connection_fn)

    if action_id and get_connection_fn is not None:
        try:
            from services.agentic_execution import _persist_run, ActionStatus
            _persist_run(
                action_id, user_id, "verify_write",
                ActionStatus.COMPLETED if result["verified"] else ActionStatus.FAILED,
                {"table": table, "row_id": row_id},
                result,
                None if result["verified"] else result["evidence"],
                get_connection_fn,
            )
        except Exception:
            logger.warning("verify_and_persist: could not persist evidence", exc_info=True)

    return result
