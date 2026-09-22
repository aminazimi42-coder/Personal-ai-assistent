"""add ai_usage_events table for DB-backed usage accounting

Revision ID: 003_add_ai_usage_events
Revises: 002_upgrade_existing_schema
Create Date: 2026-09-22

This migration adds the ai_usage_events table for multi-worker-safe
AI quota tracking. Uses atomic UPSERT (ON CONFLICT) for concurrency.
"""

from alembic import op
import sqlalchemy as sa

revision = "003_add_ai_usage_events"
down_revision = "002_upgrade_existing_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("ai_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_ai_usage_events_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "usage_date", name="pk_ai_usage_events"),
    )
    op.create_index(
        "ix_ai_usage_events_user_date",
        "ai_usage_events",
        ["user_id", "usage_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_events_user_date", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
