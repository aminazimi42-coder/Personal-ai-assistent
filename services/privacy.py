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
