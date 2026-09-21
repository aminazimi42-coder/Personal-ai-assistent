"""safe upgrade of existing schema: add auth_token_hash, token_expires_at, FK, indexes

Revision ID: 002_upgrade_existing_schema
Revises: 001_initial_schema
Create Date: 2026-09-21

This migration runs safely against the existing production database.
It adds new columns and constraints without dropping user data.
"""

from alembic import op
import sqlalchemy as sa

revision = "002_upgrade_existing_schema"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # Users — add new token columns, keep old auth_token for compatibility
    # ------------------------------------------------------------------ #
    # Add auth_token_hash (hashed token storage)
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS auth_token_hash TEXT;
    """)
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS token_expires_at TIMESTAMPTZ;
    """)
    # Keep old auth_token during transition — will be phased out in C
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS auth_token TEXT;
    """)
    # Add indexes if not present
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_users_email
        ON users (email);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_users_auth_token_hash
        ON users (auth_token_hash);
    """)

    # ------------------------------------------------------------------ #
    # Tasks — add user_id FK, indexes if not present
    # ------------------------------------------------------------------ #
    op.execute("""
        ALTER TABLE tasks
        ADD COLUMN IF NOT EXISTS user_id INTEGER;
    """)
    op.execute("""
        ALTER TABLE tasks
        ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'medium';
    """)
    op.execute("""
        ALTER TABLE tasks
        ADD COLUMN IF NOT EXISTS due_date TIMESTAMPTZ;
    """)
    # Add FK only if tasks.user_id exists and fk does not
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_tasks_user_id'
                AND table_name = 'tasks'
            ) THEN
                ALTER TABLE tasks
                ADD CONSTRAINT fk_tasks_user_id
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
            END IF;
        END $$;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_tasks_user_id ON tasks (user_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_tasks_user_id_status
        ON tasks (user_id, status);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_tasks_user_id_due_date
        ON tasks (user_id, due_date);
    """)

    # ------------------------------------------------------------------ #
    # Appointments — add user_id FK, indexes if not present
    # ------------------------------------------------------------------ #
    op.execute("""
        ALTER TABLE appointments
        ADD COLUMN IF NOT EXISTS user_id INTEGER;
    """)
    op.execute("""
        ALTER TABLE appointments
        ADD COLUMN IF NOT EXISTS description TEXT;
    """)
    op.execute("""
        ALTER TABLE appointments
        ADD COLUMN IF NOT EXISTS location TEXT;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_appointments_user_id'
                AND table_name = 'appointments'
            ) THEN
                ALTER TABLE appointments
                ADD CONSTRAINT fk_appointments_user_id
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
            END IF;
        END $$;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_appointments_user_id
        ON appointments (user_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_appointments_user_id_time
        ON appointments (user_id, appointment_time);
    """)


def downgrade() -> None:
    # Remove new columns/indexes only — do not drop tables
    op.execute("DROP INDEX IF EXISTS ix_appointments_user_id_time")
    op.execute("DROP INDEX IF EXISTS ix_appointments_user_id")
    op.execute("DROP INDEX IF EXISTS ix_tasks_user_id_due_date")
    op.execute("DROP INDEX IF EXISTS ix_tasks_user_id_status")
    op.execute("DROP INDEX IF EXISTS ix_tasks_user_id")
    op.execute("DROP INDEX IF EXISTS ix_users_auth_token_hash")
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS token_expires_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS auth_token_hash")
