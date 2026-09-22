"""add tenant and billing tables for multi-tenant SaaS

Revision ID: 005_add_tenant_billing
Revises: 004_add_memories
Create Date: 2026-09-22

Multi-Tenant / SaaS Foundation:
  - tenants: workspace/tenant identity, ownership
  - tenant_memberships: roles (owner/admin/member) per tenant per user
  - subscriptions: per-tenant plan + billing state
  - billing_events: idempotent webhook event log
  - users.tenant_id: nullable FK for backward compatibility
"""

from alembic import op
import sqlalchemy as sa


revision = "005_add_tenant_billing"
down_revision = "005_remove_legacy_auth_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # tenants
    # ------------------------------------------------------------------ #
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name="fk_tenants_owner_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index("ix_tenants_owner_user_id", "tenants", ["owner_user_id"])

    # ------------------------------------------------------------------ #
    # tenant_memberships
    # ------------------------------------------------------------------ #
    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="member"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_tenant_memberships_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_tenant_memberships_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_tenant_memberships_tenant_user"),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="ck_tenant_memberships_role",
        ),
    )
    op.create_index("ix_tenant_memberships_tenant_id", "tenant_memberships", ["tenant_id"])
    op.create_index("ix_tenant_memberships_user_id", "tenant_memberships", ["user_id"])

    # ------------------------------------------------------------------ #
    # subscriptions
    # ------------------------------------------------------------------ #
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("plan", sa.Text(), nullable=False, server_default="free"),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("stripe_subscription_id", sa.Text(), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
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
            ["tenant_id"], ["tenants.id"], name="fk_subscriptions_tenant_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", name="uq_subscriptions_tenant_id"),
        sa.CheckConstraint("plan IN ('free', 'pro')", name="ck_subscriptions_plan"),
        sa.CheckConstraint(
            "status IN ('active', 'canceled', 'past_due')",
            name="ck_subscriptions_status",
        ),
    )

    # ------------------------------------------------------------------ #
    # billing_events (idempotent webhook log)
    # ------------------------------------------------------------------ #
    op.create_table(
        "billing_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_billing_events_tenant_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("event_id", name="uq_billing_events_event_id"),
    )
    op.create_index("ix_billing_events_tenant_id", "billing_events", ["tenant_id"])
    op.create_index("ix_billing_events_event_type", "billing_events", ["event_type"])

    # ------------------------------------------------------------------ #
    # users.tenant_id (nullable — existing users have no tenant)
    # ------------------------------------------------------------------ #
    op.add_column(
        "users",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_tenant_id",
        "users",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_constraint("fk_users_tenant_id", "users", type_="foreignkey")
    op.drop_column("users", "tenant_id")

    op.drop_index("ix_billing_events_event_type", table_name="billing_events")
    op.drop_index("ix_billing_events_tenant_id", table_name="billing_events")
    op.drop_table("billing_events")

    op.drop_table("subscriptions")

    op.drop_index("ix_tenant_memberships_user_id", table_name="tenant_memberships")
    op.drop_index("ix_tenant_memberships_tenant_id", table_name="tenant_memberships")
    op.drop_table("tenant_memberships")

    op.drop_index("ix_tenants_owner_user_id", table_name="tenants")
    op.drop_table("tenants")
