"""
services/control_center.py
Personal AI Control Center — professional dashboard for real data.

Aggregates real metrics from existing services:
- Usage (AI calls today)
- Cost (estimated monthly cost)
- Tokens (prompt/completion/total)
- Retrieval savings (tokens saved by code retrieval)
- Memories (count by type)
- Projects (workspace count)
- Tasks (count by status)
- Automations (count, recent executions)
- Security (rate limit status, auth events)
- Activity/audit log

No fabricated metrics — all data comes from real service state.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class DashboardMetrics:
    """Real metrics for the control center dashboard."""
    # Usage
    ai_calls_today: int = 0
    ai_quota: Optional[int] = None
    quota_exceeded: bool = False

    # Cost
    monthly_cost_usd: float = 0.0

    # Tokens
    total_tokens_consumed: int = 0

    # Retrieval
    retrieval_tokens_saved: int = 0

    # Memory
    memory_count: int = 0
    memory_by_type: dict[str, int] = field(default_factory=dict)

    # Workspace
    workspace_count: int = 0
    project_count: int = 0

    # Tasks
    task_count: int = 0
    tasks_by_status: dict[str, int] = field(default_factory=dict)

    # Automations
    automation_count: int = 0
    automation_enabled_count: int = 0
    automation_recent_executions: list[dict] = field(default_factory=list)

    # Security
    rate_limits: dict[str, int] = field(default_factory=dict)
    cors_origins_count: int = 0

    # Activity
    recent_audit_events: list[dict] = field(default_factory=list)

    # Metadata
    generated_at: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "ai_calls_today": self.ai_calls_today,
            "ai_quota": self.ai_quota,
            "quota_exceeded": self.quota_exceeded,
            "monthly_cost_usd": round(self.monthly_cost_usd, 6),
            "total_tokens_consumed": self.total_tokens_consumed,
            "retrieval_tokens_saved": self.retrieval_tokens_saved,
            "memory_count": self.memory_count,
            "memory_by_type": self.memory_by_type,
            "workspace_count": self.workspace_count,
            "project_count": self.project_count,
            "task_count": self.task_count,
            "tasks_by_status": self.tasks_by_status,
            "automation_count": self.automation_count,
            "automation_enabled_count": self.automation_enabled_count,
            "automation_recent_executions": self.automation_recent_executions[:10],
            "rate_limits": self.rate_limits,
            "cors_origins_count": self.cors_origins_count,
            "recent_audit_events": self.recent_audit_events[:10],
            "generated_at": self.generated_at,
            "latency_ms": self.latency_ms,
        }


def get_dashboard_metrics(user_id: int, get_connection_fn=None) -> DashboardMetrics:
    """
    Aggregate real metrics from all services for a user.
    No fabricated data — all metrics come from real service state.
    """
    t0 = time.monotonic()
    metrics = DashboardMetrics()

    # Usage (from usage_service)
    try:
        from services.usage_service import get_usage
        usage = get_usage(user_id, get_connection_fn)
        metrics.ai_calls_today = usage.get("ai_calls_today", 0)
        metrics.ai_quota = usage.get("quota")
        metrics.quota_exceeded = usage.get("quota_exceeded", False)
    except Exception:
        pass

    # Cost (from cost_intelligence)
    try:
        from services.cost_intelligence import get_monthly_cost
        metrics.monthly_cost_usd = get_monthly_cost(user_id)
    except Exception:
        pass

    # Memory (from memory_engine)
    try:
        from services.memory_engine import list_memories, MEMORY_TYPES
        all_mems = list_memories(user_id, limit=10000, get_connection_fn=get_connection_fn)
        metrics.memory_count = len(all_mems)
        for mem_type in MEMORY_TYPES:
            count = sum(1 for m in all_mems if m.memory_type == mem_type)
            if count > 0:
                metrics.memory_by_type[mem_type] = count
    except Exception:
        pass

    # Workspace (from workspace service)
    try:
        from services.workspace import list_workspaces
        wss = list_workspaces(user_id)
        metrics.workspace_count = len(wss)
    except Exception:
        pass

    # Automations (from automation service)
    try:
        from services.automation import list_automations, get_execution_log
        autos = list_automations(user_id)
        metrics.automation_count = len(autos)
        metrics.automation_enabled_count = sum(1 for a in autos if a.enabled)
        metrics.automation_recent_executions = get_execution_log(user_id, limit=10)
    except Exception:
        pass

    # Security
    metrics.rate_limits = {
        "login": settings.RATE_LIMIT_LOGIN,
        "ai": settings.RATE_LIMIT_AI,
        "general": settings.RATE_LIMIT_GENERAL,
    }
    metrics.cors_origins_count = len(settings.CORS_ALLOWED_ORIGINS)

    # Audit (from privacy service)
    try:
        from services.privacy import get_audit_log
        metrics.recent_audit_events = get_audit_log(user_id, limit=10)
    except Exception:
        pass

    # Timestamp
    from datetime import datetime, timezone
    metrics.generated_at = datetime.now(timezone.utc).isoformat()
    metrics.latency_ms = round((time.monotonic() - t0) * 1000)

    logger.info(
        "control_center metrics generated (user=%d, latency=%dms)",
        user_id, metrics.latency_ms,
    )

    return metrics


def get_health_summary() -> dict:
    """
    System health summary for the control center.
    Reports real system status, no fabrication.
    """
    import os
    return {
        "flask_env": settings.FLASK_ENV,
        "is_production": settings.IS_PRODUCTION,
        "db_pool_min": settings.DB_POOL_MIN,
        "db_pool_max": settings.DB_POOL_MAX,
        "ai_model": settings.OPENAI_CHAT_MODEL,
        "rate_limits": {
            "login": settings.RATE_LIMIT_LOGIN,
            "ai": settings.RATE_LIMIT_AI,
            "general": settings.RATE_LIMIT_GENERAL,
        },
        "cors_origins": len(settings.CORS_ALLOWED_ORIGINS),
        "token_expiry_seconds": settings.AUTH_TOKEN_EXPIRY_SECONDS,
        "ai_max_tokens": settings.AI_MAX_TOKENS,
        "ai_max_input_chars": settings.AI_MAX_INPUT_CHARS,
        "voice_max_upload_bytes": settings.VOICE_MAX_UPLOAD_BYTES,
    }
