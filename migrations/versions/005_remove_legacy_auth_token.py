"""remove legacy raw auth_token column from users table

Revision ID: 005_remove_legacy_auth_token
Revises: 004_add_memories
Create Date: 2026-09-22

Drops the legacy auth_token column that stored raw bearer tokens alongside
the hashed auth_token_hash column. Raw tokens are never stored — only the
SHA-256 hash is persisted. This is a security hardening migration.
"""

from alembic import op
import sqlalchemy as sa

revision = "005_remove_legacy_auth_token"
down_revision = "004_add_memories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS auth_token")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_token", sa.Text(), nullable=True),
    )
