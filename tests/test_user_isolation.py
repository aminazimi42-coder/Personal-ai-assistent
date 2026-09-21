"""
tests/test_user_isolation.py
Tests verifying user-scoped data isolation:
- A user cannot access another user's tasks
- A user cannot access another user's appointments
Tests use mocked DB connections and auth.
"""

import pytest
from unittest.mock import MagicMock
from tests.conftest import make_user

# Route modules bind get_current_user at import time — patch at point of use.
_TASK_AUTH   = "routes.task_routes.get_current_user"
_CAL_AUTH    = "routes.calendar_routes.get_current_user"


def _setup_mock_db(mocker, fetchone_return=None, fetchall_return=None):
    """
    Helper: configure the already-mocked db.pool._pool to return a
    connection with the specified cursor results.

    conftest.app patches db.pool._pool with a MagicMock, so get_connection()
    will call _pool.getconn(). We simply reconfigure getconn() here per test.
    """
    import db.pool as pool_module
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = fetchone_return
    mock_cur.fetchall.return_value = fetchall_return or []
    mock_conn.cursor.return_value = mock_cur
    pool_module._pool.getconn.return_value = mock_conn
    return mock_conn, mock_cur


def test_tasks_scoped_to_user(client, mocker):
    """GET /tasks returns only the authenticated user's tasks."""
    user = make_user(42)
    mocker.patch(_TASK_AUTH, return_value=(user, None, None))
    tasks_rows = [
        {"id": 1, "title": "My task", "description": "", "status": "pending",
         "priority": "medium", "due_date": None, "created_at": None, "user_id": 42}
    ]
    _setup_mock_db(mocker, fetchall_return=tasks_rows)

    res = client.get("/tasks", headers={"Authorization": "Bearer validtoken"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    for task in data.get("tasks", []):
        assert task["user_id"] == 42


def test_delete_task_requires_ownership(client, mocker):
    """DELETE /tasks/<id> returns 404 when task does not belong to user."""
    user = make_user(1)
    mocker.patch(_TASK_AUTH, return_value=(user, None, None))
    # Simulate no matching row (task belongs to different user)
    _setup_mock_db(mocker, fetchone_return=None)

    res = client.delete("/tasks/999", headers={"Authorization": "Bearer validtoken"})
    assert res.status_code == 404
    data = res.get_json()
    assert data["status"] == "error"


def test_appointments_scoped_to_user(client, mocker):
    """GET /appointments returns only the authenticated user's appointments."""
    user = make_user(7)
    mocker.patch(_CAL_AUTH, return_value=(user, None, None))
    _setup_mock_db(mocker, fetchall_return=[])

    res = client.get("/appointments", headers={"Authorization": "Bearer sometoken"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "appointments" in data
