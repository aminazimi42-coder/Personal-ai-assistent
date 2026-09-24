"""add second auth-token slot to users for multi-device sessions (P0-1)

Revision ID: 011_add_second_token_slot
Revises: 010_allow_pro_plus_plan
Create Date: 2026-09-24

Root cause of P0-1 (session lost on iPhone):
  The users table stored a single auth_token_hash.  Logging in on a second
  device overwrote the hash, invalidating the first device's token.  Every
  API call from the first device returned 401.

Fix: add auth_token_hash_2 + token_expires_at_2 so login can use the
secondary slot when the primary is still valid, preventing single-slot wipe.
Logout clears only the presented token's slot.  Up to two concurrent
sessions per user.
"""

from alembic import op
import sqlalchemy as sa


revision = "011_add_second_token_slot"
down_revision = "010_allow_pro_plus_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_token_hash_2", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("token_expires_at_2", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_users_auth_token_hash_2", "users", ["auth_token_hash_2"]
    )


def downgrade() -> None:
    op.drop_index("ix_users_auth_token_hash_2", table_name="users")
    op.drop_column("users", "token_expires_at_2")
    op.drop_column("users", "auth_token_hash_2")
