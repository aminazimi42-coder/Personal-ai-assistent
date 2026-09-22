"""
services/background_jobs.py — Durable background job queue.

Provides a persistent job queue backed by PostgreSQL. Jobs are enqueued,
processed by a worker, tracked through status transitions, retried with
exponential backoff on failure, and deduplicated by payload hash.

Flow: enqueue → queued → running → completed/failed
"""

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from psycopg2.extras import RealDictCursor

from db.pool import return_connection

logger = logging.getLogger(__name__)

# Job handler registry — maps job_type → callable(job_payload) → result
_job_handlers: dict[str, Callable[[dict], Any]] = {}


def register_handler(job_type: str, handler: Callable[[dict], Any]) -> None:
    """Register a handler for a job type."""
    _job_handlers[job_type] = handler


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _payload_hash(job_type: str, payload: dict) -> str:
    """Compute a stable hash for idempotency detection."""
    raw = json.dumps({"type": job_type, "payload": payload}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _serialize_job(row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    j = dict(row)
    for key in ("scheduled_at", "started_at", "completed_at"):
        v = j.get(key)
        if isinstance(v, datetime):
            j[key] = v.isoformat()
    if isinstance(j.get("payload"), str):
        try:
            j["payload"] = json.loads(j["payload"])
        except (json.JSONDecodeError, TypeError):
            pass
    if isinstance(j.get("result"), str):
        try:
            j["result"] = json.loads(j["result"])
        except (json.JSONDecodeError, TypeError):
            pass
    return j


# ------------------------------------------------------------------ #
# In-memory fallback (for unit tests without DB)
# ------------------------------------------------------------------ #

class _InMemoryJob:
    def __init__(self, id, job_type, payload, status="queued", user_id=None,
                 scheduled_at=None, started_at=None, completed_at=None,
                 result=None, error=None, retry_count=0, max_retries=3,
                 payload_hash=None):
        self.id = id
        self.job_type = job_type
        self.payload = payload
        self.status = status
        self.user_id = user_id
        self.scheduled_at = scheduled_at or _now()
        self.started_at = started_at
        self.completed_at = completed_at
        self.result = result
        self.error = error
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.payload_hash = payload_hash

_inmem_jobs: dict[str, _InMemoryJob] = {}


class JobQueue:
    """
    Durable job queue.

    If *get_connection* is provided, uses the DB-backed jobs table.
    Otherwise, uses an in-memory store (for unit tests).
    """

    def __init__(self, get_connection=None, max_retries: int = 3):
        self._get_connection = get_connection
        self._max_retries = max_retries

    def enqueue(self, job_type: str, payload: dict, user_id: int,
                scheduled_at: Optional[datetime] = None) -> str:
        """
        Enqueue a new job.

        Idempotency: if a job with the same payload_hash already exists
        and is in 'queued' status, return the existing job_id instead
        of creating a duplicate.

        Returns: job_id (str)
        """
        if not job_type or not job_type.strip():
            raise ValueError("job_type is required")
        if not isinstance(payload, dict):
            payload = {}
        ph = _payload_hash(job_type, payload)
        now = scheduled_at or _now()

        if self._get_connection is not None:
            return self._enqueue_db(job_type, payload, user_id, ph, now)
        return self._enqueue_inmem(job_type, payload, user_id, ph, now)

    def _enqueue_db(self, job_type, payload, user_id, ph, now) -> str:
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Check for existing queued job with same hash (idempotency)
            cur.execute(
                """
                SELECT id FROM jobs
                WHERE payload_hash = %s AND status = 'queued'
                ORDER BY scheduled_at ASC LIMIT 1
                """,
                (ph,),
            )
            existing = cur.fetchone()
            if existing:
                logger.info("Duplicate job detected, returning existing: %s", existing["id"])
                return existing["id"]

            job_id = str(uuid.uuid4())[:12]
            cur.execute(
                """
                INSERT INTO jobs
                    (id, job_type, payload, status, payload_hash,
                     retry_count, max_retries, scheduled_at, user_id)
                VALUES (%s, %s, %s, 'queued', %s, 0, %s, %s, %s)
                RETURNING id
                """,
                (job_id, job_type, json.dumps(payload), ph, self._max_retries, now, user_id),
            )
            row = cur.fetchone()
            conn.commit()
            return row["id"]
        finally:
            cur.close()
            return_connection(conn)

    def _enqueue_inmem(self, job_type, payload, user_id, ph, now) -> str:
        # Check for existing queued job (idempotency)
        for j in _inmem_jobs.values():
            if j.payload_hash == ph and j.status == "queued":
                logger.info("Duplicate job detected (in-mem), returning existing: %s", j.id)
                return j.id
        job_id = str(uuid.uuid4())[:12]
        job = _InMemoryJob(
            id=job_id, job_type=job_type, payload=payload, user_id=user_id,
            scheduled_at=now, payload_hash=ph, max_retries=self._max_retries,
        )
        _inmem_jobs[job_id] = job
        return job_id

    def process_next(self) -> Optional[dict]:
        """
        Process the next queued job.

        Picks the oldest 'queued' job, marks it 'running', executes it
        via the registered handler (if any), and marks it 'completed'
        or 'failed'. On failure, if retries remain, re-queues it with
        exponential backoff.

        Returns the serialized job dict, or None if no jobs to process.
        """
        if self._get_connection is not None:
            return self._process_next_db()
        return self._process_next_inmem()

    def _process_next_db(self) -> Optional[dict]:
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'queued'
                ORDER BY scheduled_at ASC
                LIMIT 1
                """,
            )
            job_row = cur.fetchone()
            if not job_row:
                return None

            job = _serialize_job(job_row)
            job_id = job["id"]
            now = _now()

            cur.execute(
                """
                UPDATE jobs SET status = 'running', started_at = %s
                WHERE id = %s RETURNING *
                """,
                (now, job_id),
            )
            updated = cur.fetchone()
            conn.commit()
        finally:
            cur.close()
            return_connection(conn)

        job = _serialize_job(updated)
        handler = _job_handlers.get(job["job_type"])
        try:
            result = handler(job["payload"]) if handler else {"processed": True}
            self._complete_db(job_id, result)
            job["status"] = "completed"
            job["result"] = result
            return job
        except Exception as exc:
            job["error"] = str(exc)
            self._fail_or_retry_db(job, exc)
            return job

    def _complete_db(self, job_id: str, result: dict) -> None:
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                UPDATE jobs SET status = 'completed', completed_at = %s,
                                 result = %s
                WHERE id = %s
                """,
                (_now(), json.dumps(result), job_id),
            )
            conn.commit()
        finally:
            cur.close()
            return_connection(conn)

    def _fail_or_retry_db(self, job: dict, exc: Exception) -> None:
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            retry_count = (job.get("retry_count") or 0) + 1
            max_retries = job.get("max_retries", self._max_retries)
            if retry_count <= max_retries:
                # Re-queue with exponential backoff
                backoff_seconds = 2 ** (retry_count - 1)
                next_time = _now() + timedelta_safe(backoff_seconds)
                cur.execute(
                    """
                    UPDATE jobs SET status = 'queued', retry_count = %s,
                                     scheduled_at = %s, error = %s
                    WHERE id = %s
                    """,
                    (retry_count, next_time, str(exc), job["id"]),
                )
                logger.info("Job %s failed, retry %d/%d (backoff %ds)",
                            job["id"], retry_count, max_retries, backoff_seconds)
            else:
                cur.execute(
                    """
                    UPDATE jobs SET status = 'failed', completed_at = %s,
                                     error = %s, retry_count = %s
                    WHERE id = %s
                    """,
                    (_now(), str(exc), retry_count, job["id"]),
                )
                logger.error("Job %s permanently failed after %d retries",
                             job["id"], retry_count)
            conn.commit()
        finally:
            cur.close()
            return_connection(conn)

    def _process_next_inmem(self) -> Optional[dict]:
        queued = sorted(
            [j for j in _inmem_jobs.values() if j.status == "queued"],
            key=lambda j: j.scheduled_at,
        )
        if not queued:
            return None
        job = queued[0]
        job.status = "running"
        job.started_at = _now()
        handler = _job_handlers.get(job.job_type)
        try:
            result = handler(job.payload) if handler else {"processed": True}
            job.status = "completed"
            job.completed_at = _now()
            job.result = result
            return self._serialize_inmem(job)
        except Exception as exc:
            job.error = str(exc)
            job.retry_count = (job.retry_count or 0) + 1
            if job.retry_count <= job.max_retries:
                job.status = "queued"
                job.started_at = None
                logger.info("Job %s failed (in-mem), retry %d/%d",
                            job.id, job.retry_count, job.max_retries)
            else:
                job.status = "failed"
                job.completed_at = _now()
                logger.error("Job %s permanently failed (in-mem)", job.id)
            return self._serialize_inmem(job)

    def _serialize_inmem(self, job: _InMemoryJob) -> dict:
        return {
            "id": job.id,
            "job_type": job.job_type,
            "payload": job.payload,
            "status": job.status,
            "payload_hash": job.payload_hash,
            "retry_count": job.retry_count,
            "max_retries": job.max_retries,
            "scheduled_at": job.scheduled_at.isoformat() if job.scheduled_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "result": job.result,
            "error": job.error,
            "user_id": job.user_id,
        }

    def get_job(self, job_id: str, user_id: int) -> Optional[dict]:
        """Get a job by ID, scoped to the user."""
        if self._get_connection is not None:
            return self._get_job_db(job_id, user_id)
        job = _inmem_jobs.get(job_id)
        if job and job.user_id == user_id:
            return self._serialize_inmem(job)
        return None

    def _get_job_db(self, job_id: str, user_id: int) -> Optional[dict]:
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                "SELECT * FROM jobs WHERE id = %s AND user_id = %s",
                (job_id, user_id),
            )
            row = cur.fetchone()
        finally:
            cur.close()
            return_connection(conn)
        return _serialize_job(row)

    def list_jobs(self, user_id: int, limit: int = 50) -> list[dict]:
        """List jobs for a user."""
        if self._get_connection is not None:
            return self._list_jobs_db(user_id, limit)
        jobs = [self._serialize_inmem(j) for j in _inmem_jobs.values()
                if j.user_id == user_id]
        return sorted(jobs, key=lambda j: j.get("scheduled_at") or "", reverse=True)[:limit]

    def _list_jobs_db(self, user_id: int, limit: int = 50) -> list[dict]:
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                "SELECT * FROM jobs WHERE user_id = %s ORDER BY scheduled_at DESC LIMIT %s",
                (user_id, limit),
            )
            rows = cur.fetchall()
        finally:
            cur.close()
            return_connection(conn)
        return [_serialize_job(r) for r in rows if r]  # type: ignore[list-item]


def run_worker(get_connection=None, max_jobs: int = 100) -> int:
    """
    Process up to *max_jobs* queued jobs sequentially.

    Used for development/testing. In production, a dedicated worker
    process would call this in a loop.

    Returns the number of jobs processed.
    """
    queue = JobQueue(get_connection=get_connection)
    processed = 0
    for _ in range(max_jobs):
        job = queue.process_next()
        if job is None:
            break
        processed += 1
    return processed


def reset_jobs() -> None:
    """Reset in-memory job store (for tests)."""
    _inmem_jobs.clear()


def timedelta_safe(seconds: float):
    """Create a timedelta without importing at module level."""
    from datetime import timedelta
    return timedelta(seconds=seconds)
