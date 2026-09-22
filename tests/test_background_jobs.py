"""
tests/test_background_jobs.py
Tests for the background job queue: enqueue, process, status, idempotency, retries.
Uses the in-memory fallback (no DB needed).
"""

import pytest
from services.background_jobs import (
    JobQueue, register_handler, reset_jobs, run_worker,
)


@pytest.fixture(autouse=True)
def _clean():
    reset_jobs()
    yield
    reset_jobs()


# ------------------------------------------------------------------ #
# Enqueue / process
# ------------------------------------------------------------------ #

def test_enqueue_basic():
    q = JobQueue()
    job_id = q.enqueue("reminder", {"task_id": 42}, user_id=1)
    assert job_id is not None
    assert isinstance(job_id, str)


def test_enqueue_requires_job_type():
    q = JobQueue()
    with pytest.raises(ValueError):
        q.enqueue("", {"data": 1}, user_id=1)


def test_process_next_no_jobs():
    q = JobQueue()
    result = q.process_next()
    assert result is None


def test_process_next_with_handler():
    results = []

    def handler(payload):
        results.append(payload)
        return {"ok": True}

    register_handler("test_job", handler)
    q = JobQueue()
    job_id = q.enqueue("test_job", {"msg": "hello"}, user_id=1)
    job = q.process_next()
    assert job is not None
    assert job["status"] == "completed"
    assert job["result"] == {"ok": True}
    assert results == [{"msg": "hello"}]


def test_process_next_without_handler():
    q = JobQueue()
    q.enqueue("no_handler_type", {"data": 1}, user_id=1)
    job = q.process_next()
    assert job is not None
    assert job["status"] == "completed"
    assert job["result"] == {"processed": True}


def test_process_next_marks_running_then_completed():
    register_handler("track", lambda payload: {"v": 1})
    q = JobQueue()
    q.enqueue("track", {"x": 1}, user_id=1)
    job = q.process_next()
    assert job["status"] == "completed"
    assert job["started_at"] is not None
    assert job["completed_at"] is not None


# ------------------------------------------------------------------ #
# Idempotency
# ------------------------------------------------------------------ #

def test_idempotency_duplicate_payload_returns_same_id():
    q = JobQueue()
    id1 = q.enqueue("reminder", {"task_id": 99}, user_id=1)
    id2 = q.enqueue("reminder", {"task_id": 99}, user_id=1)
    assert id1 == id2


def test_idempotency_different_payload_returns_different_id():
    q = JobQueue()
    id1 = q.enqueue("reminder", {"task_id": 99}, user_id=1)
    id2 = q.enqueue("reminder", {"task_id": 100}, user_id=1)
    assert id1 != id2


def test_idempotency_different_type_same_payload_returns_different_id():
    q = JobQueue()
    id1 = q.enqueue("reminder", {"data": 1}, user_id=1)
    id2 = q.enqueue("summary", {"data": 1}, user_id=1)
    assert id1 != id2


def test_idempotency_after_processing_allows_requeue():
    register_handler("once", lambda p: {"done": True})
    q = JobQueue()
    id1 = q.enqueue("once", {"x": 1}, user_id=1)
    q.process_next()  # process it (status -> completed)
    # Now a new enqueue with same payload should create a new job
    # because the old one is no longer "queued"
    id2 = q.enqueue("once", {"x": 1}, user_id=1)
    assert id1 != id2


# ------------------------------------------------------------------ #
# Retries
# ------------------------------------------------------------------ #

def test_retry_on_failure():
    call_count = [0]

    def failing_handler(payload):
        call_count[0] += 1
        if call_count[0] < 2:
            raise RuntimeError("transient error")
        return {"ok": True}

    register_handler("retry_job", failing_handler)
    q = JobQueue(max_retries=3)
    q.enqueue("retry_job", {"data": 1}, user_id=1)

    # First attempt fails → re-queued
    job = q.process_next()
    assert job["status"] == "queued"  # re-queued for retry
    assert job["error"] is not None
    assert "transient error" in job["error"]

    # Second attempt succeeds
    job = q.process_next()
    assert job["status"] == "completed"
    assert job["result"] == {"ok": True}


def test_retry_exhausted_marks_failed():
    def always_fails(payload):
        raise RuntimeError("permanent error")

    register_handler("perm_fail", always_fails)
    q = JobQueue(max_retries=2)
    q.enqueue("perm_fail", {"x": 1}, user_id=1)

    # Attempt 1: re-queued
    job1 = q.process_next()
    assert job1["status"] == "queued"

    # Attempt 2: re-queued
    job2 = q.process_next()
    assert job2["status"] == "queued"

    # Attempt 3: exceeds max_retries → failed
    job3 = q.process_next()
    assert job3["status"] == "failed"
    assert "permanent error" in job3["error"]


# ------------------------------------------------------------------ #
# Job status tracking
# ------------------------------------------------------------------ #

def test_get_job():
    q = JobQueue()
    job_id = q.enqueue("test", {"x": 1}, user_id=1)
    job = q.get_job(job_id, user_id=1)
    assert job is not None
    assert job["id"] == job_id
    assert job["status"] == "queued"


def test_get_job_wrong_user():
    q = JobQueue()
    job_id = q.enqueue("test", {"x": 1}, user_id=1)
    job = q.get_job(job_id, user_id=999)
    assert job is None


def test_get_job_not_found():
    q = JobQueue()
    job = q.get_job("nonexistent", user_id=1)
    assert job is None


def test_list_jobs():
    q = JobQueue()
    q.enqueue("type_a", {"1": 1}, user_id=1)
    q.enqueue("type_b", {"2": 2}, user_id=1)
    q.enqueue("type_c", {"3": 3}, user_id=2)  # different user
    jobs = q.list_jobs(user_id=1)
    assert len(jobs) == 2
    assert all(j["user_id"] == 1 for j in jobs)


def test_list_jobs_limit():
    q = JobQueue()
    for i in range(10):
        q.enqueue("bulk", {"i": i}, user_id=1)
    jobs = q.list_jobs(user_id=1, limit=3)
    assert len(jobs) == 3


# ------------------------------------------------------------------ #
# Worker loop
# ------------------------------------------------------------------ #

def test_run_worker_processes_all():
    register_handler("batch", lambda p: {"v": p["n"]})
    q = JobQueue()
    for i in range(5):
        q.enqueue("batch", {"n": i}, user_id=1)

    # run_worker uses its own JobQueue, but in-memory store is shared
    # Reset and re-enqueue to ensure isolation
    reset_jobs()
    q2 = JobQueue()
    for i in range(5):
        q2.enqueue("batch", {"n": i}, user_id=1)

    processed = run_worker(max_jobs=10)
    assert processed == 5

    # No more jobs left
    assert run_worker(max_jobs=10) == 0


def test_run_worker_no_jobs():
    reset_jobs()
    processed = run_worker(max_jobs=10)
    assert processed == 0
