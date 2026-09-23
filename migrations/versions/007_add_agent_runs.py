"""add agent_runs table for durable agentic task execution

Revision ID: 006_add_agent_runs
Revises: 005_remove_legacy_auth_token
Create Date: 2026-09-22

This migration adds the agent_runs table for DB-backed agentic execution:
  - Persistent agent runs with explicit state machine
  - Idempotency via unique action_id
  - User isolation via user_id FK
  - Audit trail via created_at / updated_at / completed_at
  - Cancellation, retry, and failure handling
"""

from alembic import op
import sqlalchemy as sa

revision = "006_add_agent_runs"
down_revision = "005_add_tenant_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("action_id", sa.Text(), nullable=False),
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
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_agent_runs_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("action_id", name="uq_agent_runs_action_id"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'executing', 'completed', "
            "'failed', 'denied', 'canceled')",
            name="ck_agent_runs_status",
        ),
    )
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_agent_runs_action_id", "agent_runs", ["action_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_runs_action_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_user_id", table_name="agent_runs")
    op.drop_table("agent_runs")
