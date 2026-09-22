"""
services/billing_service.py
Subscription plans, billing state, idempotent webhooks, entitlements.

Plan model:
  - FREE: ai_daily_limit = 50
  - PRO:  ai_daily_limit = 1000

Billing:
  - Subscription per tenant (plan, status, stripe id, period)
  - Idempotent webhook processing (dedup by event_id)
  - Entitlement enforcement (plan-based feature limits)
  - PaymentProvider ABC for pluggable providers (Stripe, etc.)

Uses raw psycopg2 with RealDictCursor (matches the rest of the codebase).
A thread-safe in-memory store is used when no DB is available (tests).
"""

import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Plan definitions
# ------------------------------------------------------------------ #

class Plan:
    """Subscription plan with entitlement limits."""

    FREE = "free"
    PRO = "pro"

    PLANS: dict[str, dict] = {
        "free": {
            "name": "Free",
            "price_monthly": 0,
            "ai_daily_limit": 50,
            "features": ["basic_ai", "tasks", "calendar"],
        },
        "pro": {
            "name": "Pro",
            "price_monthly": 20,
            "ai_daily_limit": 1000,
            "features": ["basic_ai", "tasks", "calendar", "advanced_ai",
                          "priority_support", "team_collaboration"],
        },
    }

    @classmethod
    def get(cls, plan: str) -> Optional[dict]:
        return cls.PLANS.get(plan)

    @classmethod
    def is_valid(cls, plan: str) -> bool:
        return plan in cls.PLANS

    @classmethod
    def all(cls) -> dict:
        return dict(cls.PLANS)


# ------------------------------------------------------------------ #
# Payment provider abstraction
# ------------------------------------------------------------------ #

class PaymentProvider(ABC):
    """Abstract base for payment providers (Stripe, etc.)."""

    @abstractmethod
    def process_event(self, event_type: str, payload: dict) -> dict:
        """
        Process a webhook event from the provider.

        Returns a dict with keys:
          - plan: the plan to set (or None)
          - status: the subscription status to set (or None)
          - stripe_subscription_id: (or None)
        """
        ...


class StripeProvider(PaymentProvider):
    """Stripe webhook event processor."""

    def process_event(self, event_type: str, payload: dict) -> dict:
        result = {
            "plan": None,
            "status": None,
            "stripe_subscription_id": None,
            "current_period_start": None,
            "current_period_end": None,
        }

        if event_type == "customer.subscription.created":
            sub = payload.get("object", payload)
            result["plan"] = "pro" if sub.get("plan", {}).get("id") == "pro" else "free"
            result["status"] = "active"
            result["stripe_subscription_id"] = sub.get("id")
        elif event_type == "customer.subscription.updated":
            sub = payload.get("object", payload)
            result["plan"] = "pro" if sub.get("plan", {}).get("id") == "pro" else "free"
            result["status"] = sub.get("status", "active")
            result["stripe_subscription_id"] = sub.get("id")
        elif event_type == "customer.subscription.deleted":
            result["status"] = "canceled"
        elif event_type == "invoice.payment_failed":
            result["status"] = "past_due"

        return result


# Default provider instance (can be swapped)
_default_provider: PaymentProvider | None = None


def get_payment_provider() -> PaymentProvider:
    """Get the configured payment provider (default: StripeProvider)."""
    global _default_provider
    if _default_provider is None:
        _default_provider = StripeProvider()
    return _default_provider


def set_payment_provider(provider: PaymentProvider) -> None:
    """Override the default payment provider (for tests)."""
    global _default_provider
    _default_provider = provider


# ------------------------------------------------------------------ #
# In-memory store (tests only)
# ------------------------------------------------------------------ #
_lock = threading.Lock()
_mem_subscriptions: dict[int, dict] = {}
_mem_billing_events: dict[str, dict] = {}
_mem_next_sub_id = 1
_mem_next_event_id = 1


def _reset_mem_store():
    """Reset in-memory data (for tests)."""
    global _mem_subscriptions, _mem_billing_events
    global _mem_next_sub_id, _mem_next_event_id
    with _lock:
        _mem_subscriptions.clear()
        _mem_billing_events.clear()
        _mem_next_sub_id = 1
        _mem_next_event_id = 1


def _is_db_available(get_connection_fn) -> bool:
    """Check whether the subscriptions table exists."""
    if get_connection_fn is None:
        return False
    try:
        conn = get_connection_fn()
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'subscriptions'
            )
        """)
        result = cur.fetchone()
        cur.close()
        from db.pool import return_connection
        return_connection(conn)
        return bool(result[0]) if result else False
    except Exception:
        return False


def _serialize_subscription(row: dict) -> dict:
    """Serialize a subscription row to a plain dict."""
    def _ts(v):
        if v and hasattr(v, "isoformat"):
            return v.isoformat()
        return v
    return {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "plan": row["plan"],
        "status": row["status"],
        "stripe_subscription_id": row.get("stripe_subscription_id"),
        "current_period_start": _ts(row.get("current_period_start")),
        "current_period_end": _ts(row.get("current_period_end")),
        "created_at": _ts(row.get("created_at")),
        "updated_at": _ts(row.get("updated_at")),
    }


# ------------------------------------------------------------------ #
# Public API — Subscriptions
# ------------------------------------------------------------------ #

def get_subscription(tenant_id: int, get_connection_fn=None) -> Optional[dict]:
    """
    Get the subscription for a tenant.
    Returns the serialized subscription dict or None if not found.
    """
    tenant_id = int(tenant_id)

    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        with _lock:
            sub = _mem_subscriptions.get(tenant_id)
            return _serialize_subscription(dict(sub)) if sub else None

    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, tenant_id, plan, status, stripe_subscription_id,
                   current_period_start, current_period_end,
                   created_at, updated_at
            FROM subscriptions WHERE tenant_id = %s
        """, (tenant_id,))
        row = cur.fetchone()
    finally:
        cur.close()
        from db.pool import return_connection
        return_connection(conn)

    return _serialize_subscription(dict(row)) if row else None


def create_subscription(tenant_id: int, plan: str = "free",
                         get_connection_fn=None) -> dict:
    """
    Create a subscription for a tenant.
    If one already exists, update the plan instead.
    Raises ValueError if the plan is invalid.
    """
    if not Plan.is_valid(plan):
        raise ValueError(f"Invalid plan: {plan}. Must be one of {list(Plan.PLANS)}")

    tenant_id = int(tenant_id)

    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        return _mem_create_subscription(tenant_id, plan)

    now = datetime.now(timezone.utc)
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO subscriptions (tenant_id, plan, status, created_at, updated_at)
            VALUES (%s, %s, 'active', %s, %s)
            ON CONFLICT (tenant_id) DO UPDATE
                SET plan = EXCLUDED.plan,
                    updated_at = EXCLUDED.updated_at
            RETURNING id, tenant_id, plan, status, stripe_subscription_id,
                      current_period_start, current_period_end,
                      created_at, updated_at
        """, (tenant_id, plan, now, now))
        row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        from db.pool import return_connection
        return_connection(conn)

    return _serialize_subscription(dict(row))


def _mem_create_subscription(tenant_id: int, plan: str) -> dict:
    """In-memory create subscription (for tests)."""
    global _mem_next_sub_id
    with _lock:
        existing = _mem_subscriptions.get(tenant_id)
        if existing:
            existing["plan"] = plan
            existing["updated_at"] = datetime.now(timezone.utc)
            return _serialize_subscription(dict(existing))

        sid = _mem_next_sub_id
        _mem_next_sub_id += 1
        now = datetime.now(timezone.utc)
        sub = {
            "id": sid,
            "tenant_id": tenant_id,
            "plan": plan,
            "status": "active",
            "stripe_subscription_id": None,
            "current_period_start": None,
            "current_period_end": None,
            "created_at": now,
            "updated_at": now,
        }
        _mem_subscriptions[tenant_id] = sub
    return _serialize_subscription(dict(sub))


def update_subscription_status(tenant_id: int, status: str,
                               get_connection_fn=None,
                               stripe_subscription_id: str = None) -> dict:
    """
    Update the subscription status for a tenant.
    Raises ValueError if the status is invalid or no subscription exists.
    """
    valid_statuses = ("active", "canceled", "past_due")
    if status not in valid_statuses:
        raise ValueError(
            f"Invalid status: {status}. Must be one of {valid_statuses}"
        )

    tenant_id = int(tenant_id)

    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        return _mem_update_status(tenant_id, status, stripe_subscription_id)

    now = datetime.now(timezone.utc)
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if stripe_subscription_id is not None:
            cur.execute("""
                UPDATE subscriptions
                SET status = %s, stripe_subscription_id = %s, updated_at = %s
                WHERE tenant_id = %s
                RETURNING id, tenant_id, plan, status, stripe_subscription_id,
                          current_period_start, current_period_end,
                          created_at, updated_at
            """, (status, stripe_subscription_id, now, tenant_id))
        else:
            cur.execute("""
                UPDATE subscriptions
                SET status = %s, updated_at = %s
                WHERE tenant_id = %s
                RETURNING id, tenant_id, plan, status, stripe_subscription_id,
                          current_period_start, current_period_end,
                          created_at, updated_at
            """, (status, now, tenant_id))
        row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        from db.pool import return_connection
        return_connection(conn)

    if not row:
        raise ValueError(f"No subscription found for tenant {tenant_id}")
    return _serialize_subscription(dict(row))


def _mem_update_status(tenant_id: int, status: str,
                       stripe_subscription_id: str = None) -> dict:
    """In-memory update status (for tests)."""
    with _lock:
        sub = _mem_subscriptions.get(tenant_id)
        if not sub:
            raise ValueError(f"No subscription found for tenant {tenant_id}")
        sub["status"] = status
        if stripe_subscription_id is not None:
            sub["stripe_subscription_id"] = stripe_subscription_id
        sub["updated_at"] = datetime.now(timezone.utc)
        return _serialize_subscription(dict(sub))


# ------------------------------------------------------------------ #
# Public API — Webhooks (idempotent)
# ------------------------------------------------------------------ #

def process_webhook(event_id: str, event_type: str, payload: dict,
                     tenant_id: int = None,
                     get_connection_fn=None) -> dict:
    """
    Process a billing webhook event idempotently.

    If event_id has already been processed, return the existing result
    without re-processing (idempotency).

    Returns a dict with:
      - processed: True if newly processed, False if duplicate
      - event_id, event_type
      - subscription: the updated subscription (if any)
    """
    if not event_id:
        raise ValueError("event_id is required for idempotency")
    if not event_type:
        raise ValueError("event_type is required")

    # --- In-memory path ---
    if get_connection_fn is None or not _is_db_available(get_connection_fn):
        return _mem_process_webhook(event_id, event_type, payload, tenant_id)

    # --- DB path ---
    conn = get_connection_fn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Check idempotency — has this event been seen?
        cur.execute("""
            SELECT id FROM billing_events WHERE event_id = %s
        """, (event_id,))
        existing = cur.fetchone()
        if existing:
            conn.rollback()
            return {
                "processed": False,
                "event_id": event_id,
                "event_type": event_type,
                "message": "Duplicate event — already processed",
            }

        # Record the event
        import json
        payload_json = json.dumps(payload) if payload else None
        cur.execute("""
            INSERT INTO billing_events (tenant_id, event_type, event_id, payload)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (tenant_id, event_type, event_id, payload_json))
        event_row = cur.fetchone()

        # Process via payment provider
        provider = get_payment_provider()
        provider_result = provider.process_event(event_type, payload)

        subscription = None
        if tenant_id is not None and (
            provider_result.get("plan") or provider_result.get("status")
        ):
            # Ensure a subscription exists
            sub = get_subscription(tenant_id, get_connection_fn)
            if sub:
                if provider_result.get("status"):
                    update_subscription_status(
                        tenant_id,
                        provider_result["status"],
                        get_connection_fn,
                        stripe_subscription_id=provider_result.get("stripe_subscription_id"),
                    )
                if provider_result.get("plan"):
                    cur2 = conn.cursor(cursor_factory=RealDictCursor)
                    now = datetime.now(timezone.utc)
                    cur2.execute("""
                        UPDATE subscriptions SET plan = %s, updated_at = %s
                        WHERE tenant_id = %s
                        RETURNING id, tenant_id, plan, status, stripe_subscription_id,
                                  current_period_start, current_period_end,
                                  created_at, updated_at
                    """, (provider_result["plan"], now, tenant_id))
                    row = cur2.fetchone()
                    cur2.close()
                    subscription = _serialize_subscription(dict(row))
            else:
                plan = provider_result.get("plan", "free")
                subscription = create_subscription(
                    tenant_id, plan, get_connection_fn
                )
                if provider_result.get("status"):
                    update_subscription_status(
                        tenant_id,
                        provider_result["status"],
                        get_connection_fn,
                        stripe_subscription_id=provider_result.get("stripe_subscription_id"),
                    )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        from db.pool import return_connection
        return_connection(conn)

    return {
        "processed": True,
        "event_id": event_id,
        "event_type": event_type,
        "subscription": subscription,
    }


def _mem_process_webhook(event_id: str, event_type: str, payload: dict,
                         tenant_id: int = None) -> dict:
    """In-memory webhook processing (for tests)."""
    global _mem_next_event_id
    with _lock:
        if event_id in _mem_billing_events:
            return {
                "processed": False,
                "event_id": event_id,
                "event_type": event_type,
                "message": "Duplicate event — already processed",
            }

        eid = _mem_next_event_id
        _mem_next_event_id += 1
        _mem_billing_events[event_id] = {
            "id": eid,
            "tenant_id": tenant_id,
            "event_type": event_type,
            "event_id": event_id,
            "payload": payload,
            "created_at": datetime.now(timezone.utc),
        }

    provider = get_payment_provider()
    provider_result = provider.process_event(event_type, payload)

    subscription = None
    if tenant_id is not None and (
        provider_result.get("plan") or provider_result.get("status")
    ):
        sub = _mem_subscriptions.get(tenant_id)
        if sub:
            if provider_result.get("status"):
                sub["status"] = provider_result["status"]
            if provider_result.get("plan"):
                sub["plan"] = provider_result["plan"]
            if provider_result.get("stripe_subscription_id"):
                sub["stripe_subscription_id"] = provider_result["stripe_subscription_id"]
            sub["updated_at"] = datetime.now(timezone.utc)
            subscription = _serialize_subscription(dict(sub))
        else:
            plan = provider_result.get("plan", "free")
            subscription = _mem_create_subscription(tenant_id, plan)
            if provider_result.get("status"):
                _mem_update_status(
                    tenant_id,
                    provider_result["status"],
                    provider_result.get("stripe_subscription_id"),
                )

    return {
        "processed": True,
        "event_id": event_id,
        "event_type": event_type,
        "subscription": subscription,
    }


# ------------------------------------------------------------------ #
# Public API — Entitlements
# ------------------------------------------------------------------ #

def get_entitlements(tenant_id: int, get_connection_fn=None) -> dict:
    """
    Get the entitlements for a tenant based on its subscription plan.
    If no subscription exists, defaults to the FREE plan.
    """
    sub = get_subscription(tenant_id, get_connection_fn)
    plan = sub["plan"] if sub else "free"
    plan_def = Plan.get(plan) or Plan.get("free")

    return {
        "tenant_id": tenant_id,
        "plan": plan,
        "ai_daily_limit": plan_def["ai_daily_limit"],
        "features": list(plan_def["features"]),
        "price_monthly": plan_def["price_monthly"],
        "status": sub["status"] if sub else "active",
    }


def check_entitlement(tenant_id: int, feature: str,
                      get_connection_fn=None) -> bool:
    """
    Check whether a tenant's plan includes a given feature.
    Returns True if the feature is in the plan's feature list.
    """
    entitlements = get_entitlements(tenant_id, get_connection_fn)
    return feature in entitlements["features"]
