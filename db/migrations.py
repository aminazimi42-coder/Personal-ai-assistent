"""
db/migrations.py
Migration helper: creates/upgrades schema via Flask-Migrate (Alembic).
Used at application startup and by CLI management commands.
"""

import logging

logger = logging.getLogger(__name__)


def run_migrations(app) -> None:
    """
    Apply any pending Alembic migrations at startup.
    This replaces the ad-hoc ensure_*_schema() calls on every request.
    """
    from flask_migrate import upgrade as flask_migrate_upgrade
    try:
        with app.app_context():
            flask_migrate_upgrade()
            logger.info("Database migrations applied successfully")
    except Exception as exc:
        logger.error("Database migration failed: %s", exc)
        raise
