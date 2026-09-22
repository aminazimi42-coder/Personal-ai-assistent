"""
db/models.py
SQLAlchemy ORM models — used by Flask-Migrate for schema management.
The application uses raw psycopg2 for all runtime queries (performance).
These models define the authoritative schema.
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=True)
    email = db.Column(db.Text, unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    # Hashed token stored; raw token returned to client once, never stored plain.
    # Legacy auth_token column removed in migration 005_remove_legacy_auth_token.
    auth_token_hash = db.Column(db.Text, nullable=True, index=True)
    token_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Multi-tenant: nullable so existing users are not forced into a tenant.
    tenant_id = db.Column(
        db.Integer,
        db.ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )

    tasks = db.relationship("Task", back_populates="user", lazy="dynamic",
                            cascade="all, delete-orphan")
    appointments = db.relationship("Appointment", back_populates="user",
                                   lazy="dynamic", cascade="all, delete-orphan")
    memberships = db.relationship("TenantMembership", back_populates="user",
                                   lazy="dynamic", cascade="all, delete-orphan")


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True, default="")
    status = db.Column(db.Text, nullable=False, default="pending")
    priority = db.Column(db.Text, nullable=False, default="medium")
    due_date = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user = db.relationship("User", back_populates="tasks")

    __table_args__ = (
        db.CheckConstraint("status IN ('pending', 'done')", name="ck_task_status"),
        db.CheckConstraint(
            "priority IN ('low', 'medium', 'high')", name="ck_task_priority"
        ),
        db.Index("ix_tasks_user_id_status", "user_id", "status"),
        db.Index("ix_tasks_user_id_due_date", "user_id", "due_date"),
    )


class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True, default="")
    appointment_time = db.Column(db.DateTime(timezone=True), nullable=False)
    location = db.Column(db.Text, nullable=True, default="")
    status = db.Column(db.Text, nullable=False, default="scheduled")
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user = db.relationship("User", back_populates="appointments")

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('scheduled', 'done', 'cancelled')",
            name="ck_appointment_status",
        ),
        db.Index("ix_appointments_user_id_time", "user_id", "appointment_time"),
    )


# ------------------------------------------------------------------ #
# Multi-Tenant / SaaS models (migration 005_add_tenant_billing)
# ------------------------------------------------------------------ #

class Tenant(db.Model):
    """A tenant / workspace with an owning user."""
    __tablename__ = "tenants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    slug = db.Column(db.Text, nullable=False, unique=True)
    owner_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )

    memberships = db.relationship("TenantMembership", back_populates="tenant",
                                   lazy="dynamic", cascade="all, delete-orphan")
    subscription = db.relationship("Subscription", back_populates="tenant",
                                    uselist=False, cascade="all, delete-orphan")


class TenantMembership(db.Model):
    """A user's membership in a tenant with a role."""
    __tablename__ = "tenant_memberships"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer,
        db.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = db.Column(db.Text, nullable=False, default="member")
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )

    tenant = db.relationship("Tenant", back_populates="memberships")
    user = db.relationship("User", back_populates="memberships")

    __table_args__ = (
        db.CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="ck_tenant_memberships_role",
        ),
        db.UniqueConstraint("tenant_id", "user_id",
                             name="uq_tenant_memberships_tenant_user"),
    )


class Subscription(db.Model):
    """A tenant's subscription plan and billing state."""
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer,
        db.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    plan = db.Column(db.Text, nullable=False, default="free")
    status = db.Column(db.Text, nullable=False, default="active")
    stripe_subscription_id = db.Column(db.Text, nullable=True)
    current_period_start = db.Column(db.DateTime(timezone=True), nullable=True)
    current_period_end = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )

    tenant = db.relationship("Tenant", back_populates="subscription")

    __table_args__ = (
        db.CheckConstraint("plan IN ('free', 'pro')", name="ck_subscriptions_plan"),
        db.CheckConstraint(
            "status IN ('active', 'canceled', 'past_due')",
            name="ck_subscriptions_status",
        ),
    )


class BillingEvent(db.Model):
    """Idempotent billing webhook event log."""
    __tablename__ = "billing_events"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer,
        db.ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type = db.Column(db.Text, nullable=False, index=True)
    event_id = db.Column(db.Text, nullable=False, unique=True)
    payload = db.Column(db.JSON, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )


# ------------------------------------------------------------------ #
# Automations, AutomationRuns, Jobs (migration 006)
# ------------------------------------------------------------------ #

class Automation(db.Model):
    __tablename__ = "automations"

    id = db.Column(db.Text, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = db.Column(db.Text, nullable=False)
    trigger_type = db.Column(db.Text, nullable=False, default="manual")
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    max_daily_executions = db.Column(db.Integer, nullable=False, default=10)
    execution_count = db.Column(db.Integer, nullable=False, default=0)
    last_executed = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        db.CheckConstraint(
            "trigger_type IN ('daily', 'hourly', 'event', 'manual')",
            name="ck_automations_trigger_type",
        ),
    )


class AutomationRun(db.Model):
    __tablename__ = "automation_runs"

    id = db.Column(db.Text, primary_key=True)
    automation_id = db.Column(
        db.Text, db.ForeignKey("automations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status = db.Column(db.Text, nullable=False, default="pending")
    result = db.Column(db.JSON, nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending', 'executing', 'completed', 'failed')",
            name="ck_automation_runs_status",
        ),
        db.Index("ix_automation_runs_status", "status"),
    )


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Text, primary_key=True)
    job_type = db.Column(db.Text, nullable=False)
    payload = db.Column(db.JSON, nullable=True)
    status = db.Column(db.Text, nullable=False, default="queued")
    payload_hash = db.Column(db.Text, nullable=True, index=True)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    max_retries = db.Column(db.Integer, nullable=False, default=3)
    scheduled_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    result = db.Column(db.JSON, nullable=True)
    error = db.Column(db.Text, nullable=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_jobs_status",
        ),
        db.Index("ix_jobs_status", "status"),
    )
