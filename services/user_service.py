"""
services/user_service.py
Thin compatibility shim — kept for any future CLI/management use.
Schema is now managed by Flask-Migrate migrations.
"""

import logging

logger = logging.getLogger(__name__)


def create_user_table(get_connection):
    """
    Legacy stub — schema is now managed by Flask-Migrate.
    This function is intentionally a no-op to prevent accidental schema bypass.
    """
    logger.warning(
        "create_user_table() called but schema is managed by Flask-Migrate. "
        "Run 'flask db upgrade' to apply migrations."
    )
