"""add user_files table for file uploads (M2.3)

Revision ID: 009_user_files
Revises: 008_automation_jobs
Create Date: 2026-09-24

Adds:
  - user_files: user-scoped file upload records (photos + documents)
    Stored on disk outside git; this table tracks metadata only.
    Owner-isolated: users can only GET/DELETE their own files.
"""

from alembic import op
import sqlalchemy as sa

revision = "009_user_files"
down_revision = "008_automation_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_files_user_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_user_files_user_id", "user_files", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_files_user_id", table_name="user_files")
    op.drop_table("user_files")
