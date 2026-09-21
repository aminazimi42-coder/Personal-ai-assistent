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
    # Hashed token stored; raw token returned to client once, never stored plain
    auth_token_hash = db.Column(db.Text, nullable=True, index=True)
    token_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )

    tasks = db.relationship("Task", back_populates="user", lazy="dynamic",
                            cascade="all, delete-orphan")
    appointments = db.relationship("Appointment", back_populates="user",
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
