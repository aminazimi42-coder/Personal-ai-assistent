"""initial schema: users, tasks, appointments with FK indexes constraints

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-21

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # users
    # ------------------------------------------------------------------ #
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password", sa.Text(), nullable=False),
        # Hashed token — raw token is never stored
        sa.Column("auth_token_hash", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_auth_token_hash", "users", ["auth_token_hash"])

    # ------------------------------------------------------------------ #
    # tasks
    # ------------------------------------------------------------------ #
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True, server_default=""),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Text(), nullable=False, server_default="medium"),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_tasks_user_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'done')", name="ck_task_status"
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high')", name="ck_task_priority"
        ),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_user_id_status", "tasks", ["user_id", "status"])
    op.create_index(
        "ix_tasks_user_id_due_date", "tasks", ["user_id", "due_date"]
    )

    # ------------------------------------------------------------------ #
    # appointments
    # ------------------------------------------------------------------ #
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True, server_default=""),
        sa.Column("appointment_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.Text(), nullable=True, server_default=""),
        sa.Column("status", sa.Text(), nullable=False, server_default="scheduled"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_appointments_user_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'done', 'cancelled')",
            name="ck_appointment_status",
        ),
    )
    op.create_index("ix_appointments_user_id", "appointments", ["user_id"])
    op.create_index(
        "ix_appointments_user_id_time",
        "appointments",
        ["user_id", "appointment_time"],
    )


def downgrade() -> None:
    op.drop_table("appointments")
    op.drop_table("tasks")
    op.drop_table("users")
