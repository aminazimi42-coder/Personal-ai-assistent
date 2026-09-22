"""
services/privacy.py
Privacy-First / Local-Aware Architecture.

Data classification, encryption where appropriate, secrets isolation,
user/tenant isolation, retention/deletion, audit logs, AI data boundaries.
Local processing is a future capability — never claim it exists unless
implemented and verified.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DataClassification(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class DataCategory(Enum):
    USER_PROFILE = "user_profile"
    AUTH_TOKENS = "auth_tokens"
    AI_CONVERSATION = "ai_conversation"
    MEMORY = "memory"
    TASK_DATA = "task_data"
    VOICE_RECORDINGS = "voice_recordings"
    USAGE_DATA = "usage_data"


@dataclass
class DataPolicy:
    """Data retention and privacy policy for a data category."""
    category: DataCategory
    classification: DataClassification
    retention_days: int = 90
    encrypted_at_rest: bool = True
    encrypted_in_transit: bool = True
    ai_training_eligible: bool = False
    user_deletable: bool = True


# Default policies per data category
_POLICIES: dict[DataCategory, DataPolicy] = {
    DataCategory.USER_PROFILE: DataPolicy(
        category=DataCategory.USER_PROFILE,
        classification=DataClassification.CONFIDENTIAL,
        retention_days=365,
        ai_training_eligible=False,
        user_deletable=True,
    ),
    DataCategory.AUTH_TOKENS: DataPolicy(
        category=DataCategory.AUTH_TOKENS,
        classification=DataClassification.RESTRICTED,
        retention_days=7,
        encrypted_at_rest=True,
        ai_training_eligible=False,
        user_deletable=True,
    ),
    DataCategory.AI_CONVERSATION: DataPolicy(
        category=DataCategory.AI_CONVERSATION,
        classification=DataClassification.CONFIDENTIAL,
        retention_days=30,
        ai_training_eligible=False,
        user_deletable=True,
    ),
    DataCategory.MEMORY: DataPolicy(
        category=DataCategory.MEMORY,
        classification=DataClassification.CONFIDENTIAL,
        retention_days=90,
        ai_training_eligible=False,
        user_deletable=True,
    ),
    DataCategory.TASK_DATA: DataPolicy(
        category=DataCategory.TASK_DATA,
        classification=DataClassification.INTERNAL,
        retention_days=365,
        ai_training_eligible=False,
        user_deletable=True,
    ),
    DataCategory.VOICE_RECORDINGS: DataPolicy(
        category=DataCategory.VOICE_RECORDINGS,
        classification=DataClassification.RESTRICTED,
        retention_days=1,  # Voice recordings deleted immediately after transcription
        encrypted_at_rest=True,
        ai_training_eligible=False,
        user_deletable=True,
    ),
    DataCategory.USAGE_DATA: DataPolicy(
        category=DataCategory.USAGE_DATA,
        classification=DataClassification.INTERNAL,
        retention_days=90,
        ai_training_eligible=False,
        user_deletable=False,
    ),
}


def get_data_policy(category: DataCategory) -> DataPolicy:
    """Get the privacy policy for a data category."""
    return _POLICIES.get(category, DataPolicy(
        category=category,
        classification=DataClassification.CONFIDENTIAL,
        retention_days=90,
        ai_training_eligible=False,
        user_deletable=True,
    ))


def classify_data(category: DataCategory) -> DataClassification:
    """Classify a data category."""
    return get_data_policy(category).classification


def is_ai_training_eligible(category: DataCategory) -> bool:
    """Check if data from a category is eligible for AI training."""
    return get_data_policy(category).ai_training_eligible


def is_user_deletable(category: DataCategory) -> bool:
    """Check if data from a category can be deleted by the user."""
    return get_data_policy(category).user_deletable


def is_local_processing_available() -> bool:
    """
    Check if local (on-device) processing is available.
    Currently NOT implemented — always returns False.
    Never claim local processing exists unless implemented and verified.
    """
    return False


# ------------------------------------------------------------------ #
# Audit logging
# ------------------------------------------------------------------ #
_audit_log: list[dict] = []


def log_data_access(
    user_id: int,
    category: DataCategory,
    action: str,
    success: bool = True,
    details: str = "",
) -> None:
    """Log a data access event for audit."""
    import time
    _audit_log.append({
        "timestamp": time.time(),
        "user_id": user_id,
        "category": category.value,
        "action": action,
        "success": success,
        "details": details[:200],
    })
    logger.info(
        "data_access: user=%d category=%s action=%s success=%s",
        user_id, category.value, action, success,
    )


def get_audit_log(user_id: int, limit: int = 100) -> list[dict]:
    """Get audit log entries for a user."""
    return [e for e in _audit_log if e.get("user_id") == user_id][:limit]


def clear_audit_log():
    """Clear audit log (for tests)."""
    _audit_log.clear()


# ------------------------------------------------------------------ #
# Data anonymization for logging
# ------------------------------------------------------------------ #
def anonymize_value(value: str, visible_chars: int = 2) -> str:
    """Anonymize a sensitive value for logging. Shows first N chars + hash."""
    if not value:
        return ""
    if len(value) <= visible_chars:
        return "*" * len(value)
    return f"{value[:visible_chars]}{'*' * min(len(value) - visible_chars, 20)}"


def hash_for_audit(value: str) -> str:
    """Create a non-reversible hash for audit logging."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------ #
# Privacy operations: export, deletion, safe logging, AI boundary
# ------------------------------------------------------------------ #

def export_user_data(user_id: int, get_connection) -> dict:
    """
    Export all data belonging to a user.

    Collects profile, tasks, appointments, memories, usage,
    agent runs, and automations into a single structured dict.
    Returns an empty structure for unknown users — no fabrication.
    """
    from psycopg2.extras import RealDictCursor

    data: dict[str, Any] = {
        "user_id": user_id,
        "profile": None,
        "tasks": [],
        "appointments": [],
        "memories": [],
        "usage": {},
        "agent_runs": [],
        "automations": [],
        "exported_at": "",
    }

    from datetime import datetime, timezone
    data["exported_at"] = datetime.now(timezone.utc).isoformat()

    # --- DB-backed data (profile, tasks, appointments, usage) --- #
    if get_connection:
        try:
            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Profile
                cur.execute(
                    "SELECT id, name, email, created_at FROM users WHERE id = %s",
                    (user_id,),
                )
                data["profile"] = cur.fetchone()

                # Tasks
                cur.execute(
                    "SELECT id, title, description, status, priority, "
                    "due_date, created_at FROM tasks WHERE user_id = %s "
                    "ORDER BY created_at DESC",
                    (user_id,),
                )
                data["tasks"] = cur.fetchall()

                # Appointments
                cur.execute(
                    "SELECT id, title, description, appointment_time, "
                    "location, status, created_at FROM appointments "
                    "WHERE user_id = %s ORDER BY appointment_time DESC",
                    (user_id,),
                )
                data["appointments"] = cur.fetchall()
            finally:
                cur.close()
                from db.pool import return_connection
                return_connection(conn)
        except Exception:
            logger.warning("export_user_data: DB query failed", exc_info=True)

    # --- In-memory data (memories, automations) --- #
    try:
        from services.memory_engine import list_memories
        mems = list_memories(user_id, limit=10000, get_connection_fn=get_connection)
        data["memories"] = [
            {
                "id": m.id,
                "memory_type": m.memory_type,
                "key": m.key,
                "value": m.value,
                "created_at": m.created_at,
                "updated_at": m.updated_at,
            }
            for m in mems
        ]
    except Exception:
        pass

    # Usage (from usage_service)
    try:
        from services.usage_service import get_usage
        data["usage"] = get_usage(user_id, get_connection)
    except Exception:
        pass

    # Automations (from automation service)
    try:
        from services.automation import list_automations, get_execution_log
        autos = list_automations(user_id)
        data["automations"] = [
            {
                "id": a.id,
                "name": a.name,
                "trigger_type": a.trigger_type.value,
                "enabled": a.enabled,
                "execution_count": a.execution_count,
            }
            for a in autos
        ]
        # Agent runs — use the execution log as a proxy for agent run history
        data["agent_runs"] = get_execution_log(user_id, limit=100)
    except Exception:
        pass

    # Audit log this export
    log_data_access(user_id, DataCategory.USER_PROFILE, "export", True, "User data export")

    return data


def delete_user_account(user_id: int, get_connection, confirm: bool = False) -> bool:
    """
    Delete all data for a user (cascade delete from the database).
    Requires confirm=True to prevent accidental deletion.
    Returns True on success, False on failure or missing confirmation.
    """
    if not confirm:
        logger.warning(
            "delete_user_account: refused without confirm (user=%d)", user_id
        )
        return False

    if not get_connection:
        logger.error("delete_user_account: no DB connection available")
        return False

    # Delete in-memory data first
    try:
        delete_memory_data(user_id, None)
    except Exception:
        pass

    try:
        from services.automation import list_automations, delete_automation
        for auto in list_automations(user_id):
            delete_automation(auto.id, user_id)
    except Exception:
        pass

    # Delete DB data — cascade order: tasks, appointments, usage, then user
    from psycopg2.extras import RealDictCursor
    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM ai_usage_events WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM appointments WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM tasks WHERE user_id = %s", (user_id,))
            # Delete memories from DB if the table exists
            try:
                cur.execute("DELETE FROM memories WHERE user_id = %s", (user_id,))
            except Exception:
                pass
            # Finally delete the user row
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            deleted_rows = cur.rowcount
            conn.commit()
        finally:
            cur.close()
            from db.pool import return_connection
            return_connection(conn)

        if deleted_rows > 0:
            log_data_access(
                user_id, DataCategory.USER_PROFILE, "delete_account", True,
                "Account and all data deleted",
            )
            return True
        return False
    except Exception:
        logger.error("delete_user_account: DB deletion failed", exc_info=True)
        return False


def delete_memory_data(user_id: int, get_connection) -> bool:
    """
    Delete all memory entries for a user.
    Works with both in-memory and DB-backed stores.
    """
    deleted = False
    try:
        from services.memory_engine import clear_user_memories
        count = clear_user_memories(user_id, get_connection_fn=get_connection)
        deleted = count > 0
        if deleted:
            log_data_access(
                user_id, DataCategory.MEMORY, "delete_all_memories", True,
                f"Cleared {count} memories",
            )
    except Exception:
        logger.error("delete_memory_data failed", exc_info=True)

    return deleted


# ------------------------------------------------------------------ #
# Privacy-safe logging
# ------------------------------------------------------------------ #
_SENSITIVE_KEY_PATTERNS = (
    "token", "password", "secret", "api_key", "apikey",
    "authorization", "auth_token", "credential",
)


def _is_sensitive_key(key: str) -> bool:
    key_lower = str(key).lower()
    return any(p in key_lower for p in _SENSITIVE_KEY_PATTERNS)


def _mask_email(email: str) -> str:
    """Mask an email address for safe logging."""
    if not email or "@" not in email:
        return "[redacted]"
    local, domain = email.rsplit("@", 1)
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = local[:2] + "*" * (len(local) - 2)
    return f"{masked_local}@{domain}"


def _mask_value(value: Any) -> str:
    """Mask a sensitive value for logging."""
    if value is None:
        return "[null]"
    s = str(value)
    if len(s) <= 4:
        return "****"
    return s[:2] + "****" + s[-2:]


def privacy_safe_log(message: str, **kwargs) -> str:
    """
    Sanitize sensitive data before logging.

    Replaces values for keys matching sensitive patterns (token, password,
    secret, api_key, etc.) with a masked representation.  Masks email
    addresses in kwarg values that look like emails.

    Returns the sanitized log string (does not perform the actual logging).
    """
    safe_kwargs: dict[str, Any] = {}
    for key, value in kwargs.items():
        if _is_sensitive_key(key):
            safe_kwargs[key] = _mask_value(value)
        elif isinstance(value, str) and "@" in value and "." in value:
            # Heuristic: could be an email
            if EMAIL_RE.match(value):
                safe_kwargs[key] = _mask_email(value)
            else:
                safe_kwargs[key] = value
        else:
            safe_kwargs[key] = value

    parts = [message]
    for k, v in safe_kwargs.items():
        parts.append(f"{k}={v}")
    return " ".join(parts)


# ------------------------------------------------------------------ #
# AI data boundary
# ------------------------------------------------------------------ #
_AI_ALLOWED_CATEGORIES = {
    DataCategory.USER_PROFILE,
    DataCategory.TASK_DATA,
    DataCategory.AI_CONVERSATION,
    DataCategory.MEMORY,
}

_AI_FORBIDDEN_CATEGORIES = {
    DataCategory.AUTH_TOKENS,
    DataCategory.VOICE_RECORDINGS,
    DataCategory.USAGE_DATA,
}


def enforce_ai_data_boundary(
    data_category: DataCategory,
    context: str = "",
) -> bool:
    """
    Check whether a data category is allowed in AI context.

    RESTRICTED data (auth tokens, voice recordings) is never sent to AI.
    CONFIDENTIAL data (profile, memory, conversation) is allowed only
    in the user's own AI context, never for training.

    Returns True if the data may be included in AI context, False otherwise.
    """
    if data_category in _AI_FORBIDDEN_CATEGORIES:
        return False

    policy = get_data_policy(data_category)
    # Only CONFIDENTIAL or lower classifications may enter AI context
    if policy.classification == DataClassification.RESTRICTED:
        return False
    if policy.ai_training_eligible:
        # Currently no categories are training-eligible
        return False
    # CONFIDENTIAL and INTERNAL data may be used in user-scoped AI context
    return data_category in _AI_ALLOWED_CATEGORIES


# ------------------------------------------------------------------ #
# Privacy policy document
# ------------------------------------------------------------------ #
def get_privacy_policy() -> dict:
    """
    Return the privacy policy as a structured document.
    """
    policies = []
    for cat in DataCategory:
        policy = get_data_policy(cat)
        policies.append({
            "category": cat.value,
            "classification": policy.classification.value,
            "retention_days": policy.retention_days,
            "encrypted_at_rest": policy.encrypted_at_rest,
            "encrypted_in_transit": policy.encrypted_in_transit,
            "ai_training_eligible": policy.ai_training_eligible,
            "user_deletable": policy.user_deletable,
        })

    return {
        "version": "1.0",
        "title": "Privacy Policy",
        "description": (
            "This Personal AI Assistant follows a privacy-first architecture. "
            "All user data is classified, encrypted at rest and in transit, "
            "and subject to retention limits. No data is used for AI training. "
            "Users can export and delete their data at any time."
        ),
        "data_categories": policies,
        "principles": [
            "Data minimization: only collect what is needed",
            "Encryption at rest and in transit for sensitive data",
            "No data is used for AI model training",
            "User-controlled deletion and export",
            "Strict user and workspace isolation",
            "Privacy-safe logging: sensitive data masked in all logs",
            "AI data boundary: restricted data never sent to AI models",
        ],
        "user_rights": {
            "export": "Users can export all their data via /privacy/export",
            "delete_account": "Users can delete their account via /privacy/account",
            "delete_memory": "Users can delete all memories via /privacy/account",
            "data_categories": "Users can view data classifications via /privacy/data-categories",
        },
        "local_processing": {
            "available": is_local_processing_available(),
            "note": "Local (on-device) processing is not currently available.",
        },
    }


# Re-import EMAIL_RE for privacy_safe_log
import re as _re
EMAIL_RE = _re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
