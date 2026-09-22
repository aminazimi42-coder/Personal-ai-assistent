"""add memories table for personal AI memory engine

Revision ID: 004_add_memories
Revises: 003_add_ai_usage_events
Create Date: 2026-09-22

Memories table stores layered memory:
  - short_term: transient conversation context (with TTL)
  - task: notes attached to tasks
  - preference: user-level settings/facts
  - project: notes attached to projects
"""

from alembic import op
import sqlalchemy as sa

revision = "004_add_memories"
down_revision = "003_add_ai_usage_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("memory_type", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_memories_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "memory_type", "key", name="uq_memories_user_type_key"),
        sa.CheckConstraint(
            "memory_type IN ('short_term', 'task', 'preference', 'project')",
            name="ck_memories_type",
        ),
    )
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    op.create_index(
        "ix_memories_user_type",
        "memories", ["user_id", "memory_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_memories_user_type", table_name="memories")
    op.drop_index("ix_memories_user_id", table_name="memories")
    op.drop_table("memories")
