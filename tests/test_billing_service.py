"""
tests/test_billing_service.py
Tests for billing_service: plans, subscription lifecycle, webhook idempotency, entitlements.
Uses in-memory store (no DB needed).
"""

import pytest
from services import billing_service
from services.billing_service import (
    Plan, PaymentProvider, StripeProvider,
    get_payment_provider, set_payment_provider,
    _reset_mem_store,
)


@pytest.fixture(autouse=True)
def _reset():
    _reset_mem_store()
    set_payment_provider(StripeProvider())
    yield
    _reset_mem_store()
    set_payment_provider(StripeProvider())


# ------------------------------------------------------------------ #
# Plan model
# ------------------------------------------------------------------ #

def test_plan_definitions():
    free = Plan.get("free")
    assert free["ai_daily_limit"] == 50
    pro = Plan.get("pro")
    assert pro["ai_daily_limit"] == 1000


def test_plan_is_valid():
    assert Plan.is_valid("free") is True
    assert Plan.is_valid("pro") is True
    assert Plan.is_valid("enterprise") is False


def test_plan_all():
    all_plans = Plan.all()
    assert "free" in all_plans
    assert "pro" in all_plans


# ------------------------------------------------------------------ #
# Subscription lifecycle
# ------------------------------------------------------------------ #

def test_create_subscription():
    sub = billing_service.create_subscription(1, "free")
    assert sub["tenant_id"] == 1
    assert sub["plan"] == "free"
    assert sub["status"] == "active"


def test_create_subscription_pro():
    sub = billing_service.create_subscription(1, "pro")
    assert sub["plan"] == "pro"


def test_create_subscription_invalid_plan():
    with pytest.raises(ValueError, match="Invalid plan"):
        billing_service.create_subscription(1, "enterprise")


def test_create_subscription_upsert():
    billing_service.create_subscription(1, "free")
    sub = billing_service.create_subscription(1, "pro")
    assert sub["plan"] == "pro"
    subs = [billing_service.get_subscription(1)]
    assert len(subs) == 1  # only one subscription per tenant


def test_get_subscription():
    billing_service.create_subscription(1, "pro")
    sub = billing_service.get_subscription(1)
    assert sub is not None
    assert sub["plan"] == "pro"


def test_get_subscription_not_found():
    assert billing_service.get_subscription(999) is None


def test_update_subscription_status():
    billing_service.create_subscription(1, "pro")
    sub = billing_service.update_subscription_status(1, "canceled")
    assert sub["status"] == "canceled"


def test_update_subscription_status_invalid():
    billing_service.create_subscription(1, "pro")
    with pytest.raises(ValueError, match="Invalid status"):
        billing_service.update_subscription_status(1, "expired")


def test_update_subscription_status_not_found():
    with pytest.raises(ValueError, match="No subscription found"):
        billing_service.update_subscription_status(999, "active")


def test_update_subscription_with_stripe_id():
    billing_service.create_subscription(1, "pro")
    sub = billing_service.update_subscription_status(
        1, "active", stripe_subscription_id="sub_abc123"
    )
    assert sub["stripe_subscription_id"] == "sub_abc123"


# ------------------------------------------------------------------ #
# Webhook idempotency
# ------------------------------------------------------------------ #

def test_process_webhook_creates_subscription():
    result = billing_service.process_webhook(
        "evt_001", "customer.subscription.created",
        {"plan": {"id": "pro"}},
        tenant_id=1,
    )
    assert result["processed"] is True
    assert result["subscription"] is not None
    assert result["subscription"]["plan"] == "pro"


def test_process_webhook_idempotent():
    """Processing the same event_id twice returns duplicate=False."""
    payload = {"plan": {"id": "pro"}}
    r1 = billing_service.process_webhook(
        "evt_002", "customer.subscription.created", payload, tenant_id=1
    )
    r2 = billing_service.process_webhook(
        "evt_002", "customer.subscription.created", payload, tenant_id=1
    )
    assert r1["processed"] is True
    assert r2["processed"] is False
    assert "Duplicate" in r2["message"]


def test_process_webhook_different_events():
    """Different event_ids are both processed."""
    r1 = billing_service.process_webhook(
        "evt_a", "customer.subscription.created",
        {"plan": {"id": "pro"}}, tenant_id=1
    )
    r2 = billing_service.process_webhook(
        "evt_b", "customer.subscription.created",
        {"plan": {"id": "pro"}}, tenant_id=2
    )
    assert r1["processed"] is True
    assert r2["processed"] is True


def test_process_webhook_missing_event_id():
    with pytest.raises(ValueError, match="event_id is required"):
        billing_service.process_webhook("", "some.type", {}, tenant_id=1)


def test_process_webhook_missing_event_type():
    with pytest.raises(ValueError, match="event_type is required"):
        billing_service.process_webhook("evt_x", "", {}, tenant_id=1)


def test_process_webhook_canceled():
    billing_service.create_subscription(1, "pro")
    result = billing_service.process_webhook(
        "evt_cancel", "customer.subscription.deleted", {}, tenant_id=1
    )
    assert result["processed"] is True
    sub = billing_service.get_subscription(1)
    assert sub["status"] == "canceled"


def test_process_webhook_past_due():
    billing_service.create_subscription(1, "pro")
    result = billing_service.process_webhook(
        "evt_fail", "invoice.payment_failed", {}, tenant_id=1
    )
    assert result["processed"] is True
    sub = billing_service.get_subscription(1)
    assert sub["status"] == "past_due"


# ------------------------------------------------------------------ #
# Entitlements
# ------------------------------------------------------------------ #

def test_get_entitlements_free():
    billing_service.create_subscription(1, "free")
    ent = billing_service.get_entitlements(1)
    assert ent["plan"] == "free"
    assert ent["ai_daily_limit"] == 50
    assert "basic_ai" in ent["features"]


def test_get_entitlements_pro():
    billing_service.create_subscription(1, "pro")
    ent = billing_service.get_entitlements(1)
    assert ent["plan"] == "pro"
    assert ent["ai_daily_limit"] == 1000
    assert "advanced_ai" in ent["features"]
    assert "priority_support" in ent["features"]


def test_get_entitlements_no_subscription():
    """Defaults to FREE plan when no subscription exists."""
    ent = billing_service.get_entitlements(999)
    assert ent["plan"] == "free"
    assert ent["ai_daily_limit"] == 50


def test_check_entitlement_true():
    billing_service.create_subscription(1, "pro")
    assert billing_service.check_entitlement(1, "advanced_ai") is True


def test_check_entitlement_false():
    billing_service.create_subscription(1, "free")
    assert billing_service.check_entitlement(1, "advanced_ai") is False


def test_check_entitlement_default_free():
    assert billing_service.check_entitlement(999, "basic_ai") is True


# ------------------------------------------------------------------ #
# Payment provider abstraction
# ------------------------------------------------------------------ #

def test_payment_provider_abc():
    """PaymentProvider is abstract and cannot be instantiated directly."""
    with pytest.raises(TypeError):
        PaymentProvider()


def test_stripe_provider_process_event_created():
    provider = StripeProvider()
    result = provider.process_event(
        "customer.subscription.created", {"id": "sub_123", "plan": {"id": "pro"}}
    )
    assert result["plan"] == "pro"
    assert result["status"] == "active"
    assert result["stripe_subscription_id"] == "sub_123"


def test_stripe_provider_process_event_deleted():
    provider = StripeProvider()
    result = provider.process_event("customer.subscription.deleted", {})
    assert result["status"] == "canceled"


def test_get_payment_provider_default():
    provider = get_payment_provider()
    assert isinstance(provider, StripeProvider)


def test_custom_payment_provider():
    """Can plug in a custom payment provider."""
    class MockProvider(PaymentProvider):
        def process_event(self, event_type, payload):
            return {"plan": "free", "status": "active",
                    "stripe_subscription_id": None,
                    "current_period_start": None,
                    "current_period_end": None}

    set_payment_provider(MockProvider())
    provider = get_payment_provider()
    assert isinstance(provider, MockProvider)
