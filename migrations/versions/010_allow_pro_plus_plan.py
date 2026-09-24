"""allow pro_plus in subscriptions plan check constraint (M2 hotfix H3)

Revision ID: 010_allow_pro_plus_plan
Revises: 009_user_files
Create Date: 2026-09-24

Root cause of /api/v1/account/quota 500:
  The subscriptions table had a CHECK constraint ck_subscriptions_plan
  that only allowed ('free', 'pro'). M1.1 added a 'pro_plus' plan to the
  Plan model (billing_service.Plan) but never updated the DB constraint.
  When get_user_plan() resolved a tenant whose subscription was set to
  'pro_plus' (or when a webhook tried to INSERT/UPDATE that plan), PostgreSQL
  rejected the row with a check-violation, the exception bubbled up through
  get_user_plan → account_quota handler, and the catch-all returned 500.

Fix: drop and recreate the check constraint to include 'pro_plus'.
"""

from alembic import op


revision = "010_allow_pro_plus_plan"
down_revision = "009_user_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS ck_subscriptions_plan"
    )
    op.execute(
        "ALTER TABLE subscriptions "
        "ADD CONSTRAINT ck_subscriptions_plan "
        "CHECK (plan IN ('free', 'pro', 'pro_plus'))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS ck_subscriptions_plan"
    )
    op.execute(
        "ALTER TABLE subscriptions "
        "ADD CONSTRAINT ck_subscriptions_plan "
        "CHECK (plan IN ('free', 'pro'))"
    )
