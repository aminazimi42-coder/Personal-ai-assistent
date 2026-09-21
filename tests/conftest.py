"""
tests/conftest.py
Shared test fixtures.
All tests use an in-memory test application with mocked DB pool.
No real DB or OpenAI calls are made in tests.
"""

import os

# Set test environment BEFORE any app import
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/testdb"
os.environ["OPENAI_API_KEY"] = "sk-test-key"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FLASK_ENV"] = "testing"
os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost:5000"

import pytest
from unittest.mock import MagicMock, patch
import config.settings as _settings  # noqa — ensure settings are loaded with test env


def _make_mock_pool():
    """Return a psycopg2-like pool mock."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None
    mock_cur.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cur
    mock_pool.getconn.return_value = mock_conn
    return mock_pool


@pytest.fixture
def app(mocker):
    """
    Create test app with mocked DB pool.

    We patch db.pool._pool *before* create_app() so that the already-imported
    get_connection() function in main.py uses the mock pool when called.
    """
    mock_pool = _make_mock_pool()

    # Patch _pool so get_connection() works without a real DB
    mocker.patch("db.pool._pool", mock_pool, create=True)
    # Also prevent init_pool() from overwriting our mock
    mocker.patch("db.pool.init_pool", return_value=None)

    from main import create_app
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


def make_user(uid=1):
    return {
        "id": uid,
        "name": f"User{uid}",
        "email": f"user{uid}@example.com",
        "created_at": None,
        "token_expires_at": None,
    }


def make_mock_conn(fetchone_return=None, fetchall_return=None):
    """Create a mock psycopg2 connection with configurable cursor results."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = fetchone_return
    mock_cur.fetchall.return_value = fetchall_return or []
    mock_conn.cursor.return_value = mock_cur
    return mock_conn, mock_cur
