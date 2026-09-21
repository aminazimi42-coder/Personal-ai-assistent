"""
db/pool.py
Thread-safe psycopg2 connection pool.
All application code obtains database connections from get_connection().
"""

import logging
import psycopg2
import psycopg2.pool
import psycopg2.extras

from config import settings

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def init_pool() -> None:
    """Initialize the connection pool. Call once at application startup."""
    global _pool
    if _pool is not None:
        return
    try:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=settings.DB_POOL_MIN,
            maxconn=settings.DB_POOL_MAX,
            dsn=settings.DATABASE_URL,
        )
        logger.info("Database connection pool initialized (min=%d, max=%d)",
                    settings.DB_POOL_MIN, settings.DB_POOL_MAX)
    except Exception as exc:
        logger.error("Failed to initialize database connection pool: %s", exc)
        raise


def get_connection() -> psycopg2.extensions.connection:
    """
    Obtain a connection from the pool.
    Callers MUST return it via return_connection() or use get_db_conn() context manager.
    """
    global _pool
    if _pool is None:
        init_pool()
    try:
        conn = _pool.getconn()
        conn.autocommit = False
        return conn
    except psycopg2.pool.PoolError as exc:
        logger.error("Connection pool exhausted: %s", exc)
        raise


def return_connection(conn: psycopg2.extensions.connection, discard: bool = False) -> None:
    """Return a connection to the pool."""
    global _pool
    if _pool is None or conn is None:
        return
    try:
        if discard:
            _pool.putconn(conn, close=True)
        else:
            _pool.putconn(conn)
    except Exception as exc:
        logger.warning("Error returning connection to pool: %s", exc)


def close_pool() -> None:
    """Close all pool connections. Called on application teardown."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("Database connection pool closed")
