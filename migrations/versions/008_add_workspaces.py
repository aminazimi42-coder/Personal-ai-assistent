"""add workspaces and projects tables for durable project workspace system

Revision ID: 006_add_workspaces
Revises: 005_remove_legacy_auth_token
Create Date: 2026-09-22

Workspaces table stores user-owned workspaces with strict ownership
isolation. Projects table stores projects within workspaces, also
user-scoped. Cascade deletes ensure cleanup on workspace removal.
"""

from alembic import op
import sqlalchemy as sa

revision = "007_add_workspaces"
down_revision = "006_add_agent_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # Workspaces
    # ------------------------------------------------------------------ #
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
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
            ["user_id"], ["users.id"], name="fk_workspaces_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "name", name="uq_workspaces_user_name"),
    )
    op.create_index("ix_workspaces_user_id", "workspaces", ["user_id"])

    # ------------------------------------------------------------------ #
    # Projects
    # ------------------------------------------------------------------ #
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
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
            ["workspace_id"], ["workspaces.id"], name="fk_projects_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_projects_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("workspace_id", "name", name="uq_projects_workspace_name"),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])
    op.create_index("ix_projects_user_id", "projects", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_index("ix_projects_workspace_id", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_workspaces_user_id", table_name="workspaces")
    op.drop_table("workspaces")
