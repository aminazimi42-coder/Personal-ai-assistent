"""add automations, automation_runs, and jobs tables

Revision ID: 006_automation_jobs_voice_to_task
Revises: 005_remove_legacy_auth_token
Create Date: 2026-09-22

Adds:
  - automations: durable, user-isolated automation definitions
  - automation_runs: execution history per automation
  - jobs: background job queue for reminders, long-running tasks, scheduled work
"""

from alembic import op
import sqlalchemy as sa

revision = "009_automation_jobs_voice_to_task"
down_revision = "008_add_workspaces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # automations
    # ------------------------------------------------------------------ #
    op.create_table(
        "automations",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("trigger_type", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_daily_executions", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("execution_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_executed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_automations_user_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "trigger_type IN ('daily', 'hourly', 'event', 'manual')",
            name="ck_automations_trigger_type",
        ),
    )
    op.create_index("ix_automations_user_id", "automations", ["user_id"])
    op.create_index("ix_automations_status", "automations", ["user_id", "enabled"])

    # ------------------------------------------------------------------ #
    # automation_runs
    # ------------------------------------------------------------------ #
    op.create_table(
        "automation_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("automation_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["automation_id"], ["automations.id"], name="fk_automation_runs_automation_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_automation_runs_user_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'executing', 'completed', 'failed')",
            name="ck_automation_runs_status",
        ),
    )
    op.create_index("ix_automation_runs_automation_id", "automation_runs", ["automation_id"])
    op.create_index("ix_automation_runs_user_id", "automation_runs", ["user_id"])
    op.create_index("ix_automation_runs_status", "automation_runs", ["status"])

    # ------------------------------------------------------------------ #
    # jobs (background job queue)
    # ------------------------------------------------------------------ #
    op.create_table(
        "jobs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("payload_hash", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_jobs_user_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_jobs_status",
        ),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_payload_hash", "jobs", ["payload_hash"])


def downgrade() -> None:
    op.drop_index("ix_jobs_payload_hash", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_user_id", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("ix_automation_runs_status", table_name="automation_runs")
    op.drop_index("ix_automation_runs_user_id", table_name="automation_runs")
    op.drop_index("ix_automation_runs_automation_id", table_name="automation_runs")
    op.drop_table("automation_runs")

    op.drop_index("ix_automations_status", table_name="automations")
    op.drop_index("ix_automations_user_id", table_name="automations")
    op.drop_table("automations")
