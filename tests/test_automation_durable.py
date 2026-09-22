"""
tests/test_automation_durable.py
Tests for DB-backed durable automation engine: pause/resume, daily limits,
execution history, user isolation, using mocked DB connections.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from services.automation import (
    create_automation, get_automation, list_automations,
    delete_automation, execute_automation, pause_automation,
    resume_automation, get_execution_log, list_automation_runs,
    reset_automations, TriggerType,
)


# ------------------------------------------------------------------ #
# Mock DB helpers
# ------------------------------------------------------------------ #

def _make_mock_conn(fetchone_return=None, fetchall_return=None):
    """Create a mock psycopg2 connection that simulates DB behavior."""
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_return
    cur.fetchall.return_value = fetchall_return or []
    conn.cursor.return_value = cur
    return conn, cur


def _mock_automation_row(id="auto1", user_id=1, name="Test", enabled=True,
                        trigger_type="manual", max_daily=10, exec_count=0):
    return {
        "id": id,
        "user_id": user_id,
        "name": name,
        "trigger_type": trigger_type,
        "enabled": enabled,
        "max_daily_executions": max_daily,
        "execution_count": exec_count,
        "last_executed": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


def _mock_run_row(id="run1", automation_id="auto1", user_id=1,
                  status="completed", result=None, error=None):
    return {
        "id": id,
        "automation_id": automation_id,
        "user_id": user_id,
        "status": status,
        "result": result,
        "error": error,
        "created_at": datetime.now(timezone.utc),
        "completed_at": datetime.now(timezone.utc),
    }


@pytest.fixture(autouse=True)
def _clean_inmem():
    reset_automations()
    yield
    reset_automations()


# ------------------------------------------------------------------ #
# In-memory backward compat (existing tests still work)
# ------------------------------------------------------------------ #

def test_inmem_create_automation():
    auto = create_automation(1, "Daily Summary", TriggerType.DAILY)
    assert auto.user_id == 1
    assert auto.name == "Daily Summary"
    assert auto.id is not None


def test_inmem_execute_automation():
    auto = create_automation(1, "Test")
    result = execute_automation(auto.id, 1)
    assert result["status"] == "completed"
    assert result["executed"] is True


# ------------------------------------------------------------------ #
# DB-backed: pause/resume
# ------------------------------------------------------------------ #

def test_db_pause_automation():
    conn, cur = _make_mock_conn(fetchone_return=_mock_automation_row(enabled=True))
    result = pause_automation("auto1", 1, get_connection=lambda: conn)
    assert result is not None
    assert result["id"] == "auto1"
    # Verify the UPDATE set enabled=False
    execute_calls = cur.execute.call_args_list
    update_sql = str(execute_calls[0]).upper()
    assert "FALSE" in update_sql or "FALSE" in str(execute_calls[0])


def test_db_pause_automation_not_found():
    conn, cur = _make_mock_conn(fetchone_return=None)
    result = pause_automation("nonexistent", 1, get_connection=lambda: conn)
    assert result is None


def test_db_resume_automation():
    conn, cur = _make_mock_conn(fetchone_return=_mock_automation_row(enabled=False))
    result = resume_automation("auto1", 1, get_connection=lambda: conn)
    assert result is not None
    assert result["id"] == "auto1"


def test_db_resume_automation_not_found():
    conn, cur = _make_mock_conn(fetchone_return=None)
    result = resume_automation("nonexistent", 1, get_connection=lambda: conn)
    assert result is None


# ------------------------------------------------------------------ #
# DB-backed: create / get / list / delete
# ------------------------------------------------------------------ #

def test_db_create_automation():
    conn, cur = _make_mock_conn(fetchone_return=_mock_automation_row())
    auto = create_automation(1, "My Auto", TriggerType.DAILY, get_connection=lambda: conn)
    assert auto is not None
    assert auto["name"] == "Test"  # mock returns pre-set row
    assert auto["id"] == "auto1"


def test_db_create_automation_empty_name():
    conn, _ = _make_mock_conn()
    with pytest.raises(ValueError):
        create_automation(1, "", get_connection=lambda: conn)


def test_db_get_automation():
    conn, cur = _make_mock_conn(fetchone_return=_mock_automation_row())
    auto = get_automation("auto1", 1, get_connection=lambda: conn)
    assert auto is not None
    assert auto["id"] == "auto1"


def test_db_get_automation_not_found():
    conn, _ = _make_mock_conn(fetchone_return=None)
    auto = get_automation("nonexistent", 1, get_connection=lambda: conn)
    assert auto is None


def test_db_list_automations():
    rows = [_mock_automation_row(id="a1"), _mock_automation_row(id="a2")]
    conn, _ = _make_mock_conn(fetchall_return=rows)
    autos = list_automations(1, get_connection=lambda: conn)
    assert len(autos) == 2


def test_db_delete_automation():
    conn, cur = _make_mock_conn(fetchone_return={"id": "auto1"})
    deleted = delete_automation("auto1", 1, get_connection=lambda: conn)
    assert deleted is True


def test_db_delete_automation_not_found():
    conn, _ = _make_mock_conn(fetchone_return=None)
    deleted = delete_automation("nonexistent", 1, get_connection=lambda: conn)
    assert deleted is False


# ------------------------------------------------------------------ #
# DB-backed: execute with daily limits
# ------------------------------------------------------------------ #

def test_db_execute_automation_success():
    auto_row = _mock_automation_row(enabled=True, max_daily=10)
    conn, cur = _make_mock_conn(fetchone_return=auto_row, fetchall_return=[])
    # For _count_today_runs, the cursor.fetchone returns the auto row
    # We need it to return a count (int) for the count query.
    # Since we use the same cursor mock, the first fetchone returns auto_row,
    # and subsequent calls return the same thing. We need to handle this:
    # The execute_automation flow:
    #   1. _get_automation_db → fetchone → auto_row (dict)
    #   2. _count_today_runs → fetchone → (int,) — but mock returns auto_row
    # So we need to make fetchone return different values per call.
    call_count = [0]

    def side_effect_fetchone():
        call_count[0] += 1
        if call_count[0] == 1:
            return auto_row  # _get_automation_db
        if call_count[0] == 2:
            return (0,)  # _count_today_runs → 0 completed today
        return _mock_run_row()  # _create_run_db calls

    cur.fetchone.side_effect = side_effect_fetchone

    result = execute_automation("auto1", 1, get_connection=lambda: conn)
    assert result["status"] == "completed"
    assert result["executed"] is True


def test_db_execute_automation_disabled():
    auto_row = _mock_automation_row(enabled=False)
    conn, cur = _make_mock_conn(fetchone_return=auto_row)
    result = execute_automation("auto1", 1, get_connection=lambda: conn)
    assert result["status"] == "disabled"
    assert "disabled" in result["error"].lower()


def test_db_execute_automation_not_found():
    conn, _ = _make_mock_conn(fetchone_return=None)
    result = execute_automation("nonexistent", 1, get_connection=lambda: conn)
    assert result["status"] == "denied"


def test_db_execute_automation_daily_limit():
    auto_row = _mock_automation_row(enabled=True, max_daily=2)
    conn, cur = _make_mock_conn(fetchone_return=auto_row)
    call_count = [0]

    def side_effect_fetchone():
        call_count[0] += 1
        if call_count[0] == 1:
            return auto_row  # _get_automation_db
        return (5,)  # _count_today_runs → 5 > max_daily(2)

    cur.fetchone.side_effect = side_effect_fetchone

    result = execute_automation("auto1", 1, get_connection=lambda: conn)
    assert result["status"] == "limit_exceeded"


def test_db_execute_with_executor():
    auto_row = _mock_automation_row(enabled=True)
    conn, cur = _make_mock_conn(fetchone_return=auto_row)
    call_count = [0]

    def side_effect_fetchone():
        call_count[0] += 1
        if call_count[0] == 1:
            return auto_row
        if call_count[0] == 2:
            return (0,)
        return _mock_run_row()

    cur.fetchone.side_effect = side_effect_fetchone

    def executor(user_id):
        return {"summary": "test done", "user": user_id}

    result = execute_automation("auto1", 1, executor=executor, get_connection=lambda: conn)
    assert result["status"] == "completed"
    assert result["result"]["summary"] == "test done"


def test_db_execute_with_failing_executor():
    auto_row = _mock_automation_row(enabled=True)
    conn, cur = _make_mock_conn(fetchone_return=auto_row)
    call_count = [0]

    def side_effect_fetchone():
        call_count[0] += 1
        if call_count[0] == 1:
            return auto_row
        if call_count[0] == 2:
            return (0,)
        return _mock_run_row()

    cur.fetchone.side_effect = side_effect_fetchone

    def bad_executor(user_id):
        raise RuntimeError("execution failed")

    result = execute_automation("auto1", 1, executor=bad_executor, get_connection=lambda: conn)
    assert result["status"] == "failed"
    assert "execution failed" in result["error"]


# ------------------------------------------------------------------ #
# DB-backed: execution history
# ------------------------------------------------------------------ #

def test_db_list_automation_runs():
    rows = [_mock_run_row(id="r1"), _mock_run_row(id="r2")]
    conn, _ = _make_mock_conn(fetchall_return=rows)
    runs = list_automation_runs("auto1", 1, get_connection=lambda: conn)
    assert len(runs) == 2


def test_db_get_execution_log():
    rows = [_mock_run_row(id="r1"), _mock_run_row(id="r2")]
    conn, _ = _make_mock_conn(fetchall_return=rows)
    log = get_execution_log(1, get_connection=lambda: conn)
    assert len(log) == 2
