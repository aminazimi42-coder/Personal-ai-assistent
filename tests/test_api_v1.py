"""
tests/test_api_v1.py
Tests for the versioned /api/v1/ API surface and OpenAPI spec.
Uses the Flask test client with mocked auth and in-memory services.
"""

import json
import pytest
from unittest.mock import MagicMock
from tests.conftest import make_user
from services import tenant_service, billing_service
from services.tenant_service import _reset_mem_store as reset_tenants
from services.billing_service import _reset_mem_store as reset_billing
from services.billing_service import set_payment_provider, StripeProvider


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

_AUTH_TARGET = "routes.api_v1.get_current_user"


def _mock_auth(mocker, user=None):
    """Patch get_current_user in the api_v1 module."""
    u = user or make_user(1)
    mocker.patch(_AUTH_TARGET, return_value=(u, None, None))
    return u


def _setup_mock_db(mocker):
    """Configure the mock pool so _is_db_available returns False (in-memory)."""
    import db.pool as pool_module
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None
    mock_cur.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cur
    pool_module._pool.getconn.return_value = mock_conn
    return mock_conn, mock_cur


@pytest.fixture(autouse=True)
def _reset_stores():
    reset_tenants()
    reset_billing()
    set_payment_provider(StripeProvider())
    yield
    reset_tenants()
    reset_billing()
    set_payment_provider(StripeProvider())


# ------------------------------------------------------------------ #
# Health
# ------------------------------------------------------------------ #

def test_api_v1_health(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"


# ------------------------------------------------------------------ #
# OpenAPI spec
# ------------------------------------------------------------------ #

def test_openapi_spec(client):
    res = client.get("/api/v1/openapi.json")
    assert res.status_code == 200
    spec = res.get_json()
    assert spec["openapi"].startswith("3.")
    assert "paths" in spec
    assert "/tenants" in spec["paths"]
    assert "/tenants/{tenant_id}/members" in spec["paths"]
    assert "/tenants/{tenant_id}/subscription" in spec["paths"]
    assert "/billing/webhook" in spec["paths"]


def test_openapi_spec_has_security_schemes(client):
    res = client.get("/api/v1/openapi.json")
    spec = res.get_json()
    assert "components" in spec
    assert "securitySchemes" in spec["components"]
    assert "BearerAuth" in spec["components"]["securitySchemes"]


def test_openapi_spec_has_error_schema(client):
    res = client.get("/api/v1/openapi.json")
    spec = res.get_json()
    assert "schemas" in spec["components"]
    assert "Error" in spec["components"]["schemas"]


def test_openapi_spec_is_valid_json(client):
    res = client.get("/api/v1/openapi.json")
    # Ensure response is valid JSON (get_json would have raised otherwise)
    assert res.is_json
    raw = res.get_data(as_text=True)
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)


# ------------------------------------------------------------------ #
# Tenants — unauthenticated
# ------------------------------------------------------------------ #

def test_list_tenants_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.get("/api/v1/tenants")
    assert res.status_code == 401
    data = res.get_json()
    assert data["status"] == "error"


def test_create_tenant_unauthenticated(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.post("/api/v1/tenants", json={"name": "Test"})
    assert res.status_code == 401


# ------------------------------------------------------------------ #
# Tenants — authenticated
# ------------------------------------------------------------------ #

def test_create_tenant(client, mocker):
    _mock_auth(mocker)
    _setup_mock_db(mocker)
    res = client.post("/api/v1/tenants", json={"name": "Acme Inc"})
    assert res.status_code == 201
    data = res.get_json()
    assert data["name"] == "Acme Inc"
    assert data["slug"] == "acme-inc"


def test_create_tenant_no_body(client, mocker):
    _mock_auth(mocker)
    res = client.post("/api/v1/tenants")
    assert res.status_code == 400


def test_create_tenant_empty_name(client, mocker):
    _mock_auth(mocker)
    res = client.post("/api/v1/tenants", json={"name": ""})
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"


def test_list_tenants(client, mocker):
    user = _mock_auth(mocker)
    _setup_mock_db(mocker)
    tenant_service.create_tenant("T1", user["id"])
    tenant_service.create_tenant("T2", user["id"])
    res = client.get("/api/v1/tenants")
    assert res.status_code == 200
    data = res.get_json()
    assert "items" in data
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["per_page"] == 20


def test_list_tenants_pagination(client, mocker):
    user = _mock_auth(mocker)
    _setup_mock_db(mocker)
    for i in range(5):
        tenant_service.create_tenant(f"T{i}", user["id"])
    res = client.get("/api/v1/tenants?page=1&per_page=2")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["per_page"] == 2


# ------------------------------------------------------------------ #
# Members
# ------------------------------------------------------------------ #

def test_list_members(client, mocker):
    user = _mock_auth(mocker)
    _setup_mock_db(mocker)
    tenant = tenant_service.create_tenant("Corp", user["id"])
    res = client.get(f"/api/v1/tenants/{tenant['id']}/members")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] >= 1


def test_list_members_forbidden(client, mocker):
    _mock_auth(mocker, make_user(999))
    _setup_mock_db(mocker)
    # Tenant owned by user 1; user 999 is not a member
    tenant = tenant_service.create_tenant("Corp", 1)
    res = client.get(f"/api/v1/tenants/{tenant['id']}/members")
    assert res.status_code == 403


def test_add_member(client, mocker):
    user = _mock_auth(mocker)
    _setup_mock_db(mocker)
    tenant = tenant_service.create_tenant("Corp", user["id"])
    res = client.post(
        f"/api/v1/tenants/{tenant['id']}/members",
        json={"user_id": 2, "role": "admin"},
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["role"] == "admin"


def test_add_member_forbidden(client, mocker):
    _mock_auth(mocker, make_user(999))
    _setup_mock_db(mocker)
    tenant = tenant_service.create_tenant("Corp", 1)
    res = client.post(
        f"/api/v1/tenants/{tenant['id']}/members",
        json={"user_id": 2, "role": "member"},
    )
    assert res.status_code == 403


def test_add_member_missing_user_id(client, mocker):
    user = _mock_auth(mocker)
    _setup_mock_db(mocker)
    tenant = tenant_service.create_tenant("Corp", user["id"])
    res = client.post(
        f"/api/v1/tenants/{tenant['id']}/members",
        json={"role": "member"},
    )
    assert res.status_code == 400


# ------------------------------------------------------------------ #
# Subscription
# ------------------------------------------------------------------ #

def test_get_subscription(client, mocker):
    user = _mock_auth(mocker)
    _setup_mock_db(mocker)
    tenant = tenant_service.create_tenant("Corp", user["id"])
    billing_service.create_subscription(tenant["id"], "pro")
    res = client.get(f"/api/v1/tenants/{tenant['id']}/subscription")
    assert res.status_code == 200
    data = res.get_json()
    assert data["plan"] == "pro"


def test_get_subscription_not_found(client, mocker):
    user = _mock_auth(mocker)
    _setup_mock_db(mocker)
    tenant = tenant_service.create_tenant("Corp", user["id"])
    res = client.get(f"/api/v1/tenants/{tenant['id']}/subscription")
    assert res.status_code == 404


def test_create_subscription(client, mocker):
    user = _mock_auth(mocker)
    _setup_mock_db(mocker)
    tenant = tenant_service.create_tenant("Corp", user["id"])
    res = client.post(
        f"/api/v1/tenants/{tenant['id']}/subscription",
        json={"plan": "pro"},
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["plan"] == "pro"


def test_create_subscription_forbidden(client, mocker):
    _mock_auth(mocker, make_user(999))
    _setup_mock_db(mocker)
    tenant = tenant_service.create_tenant("Corp", 1)
    res = client.post(
        f"/api/v1/tenants/{tenant['id']}/subscription",
        json={"plan": "pro"},
    )
    assert res.status_code == 403


def test_create_subscription_invalid_plan(client, mocker):
    user = _mock_auth(mocker)
    _setup_mock_db(mocker)
    tenant = tenant_service.create_tenant("Corp", user["id"])
    res = client.post(
        f"/api/v1/tenants/{tenant['id']}/subscription",
        json={"plan": "enterprise"},
    )
    assert res.status_code == 400


# ------------------------------------------------------------------ #
# Entitlements
# ------------------------------------------------------------------ #

def test_get_entitlements(client, mocker):
    user = _mock_auth(mocker)
    _setup_mock_db(mocker)
    tenant = tenant_service.create_tenant("Corp", user["id"])
    billing_service.create_subscription(tenant["id"], "pro")
    res = client.get(f"/api/v1/tenants/{tenant['id']}/entitlements")
    assert res.status_code == 200
    data = res.get_json()
    assert data["plan"] == "pro"
    assert data["ai_daily_limit"] == 1000


def test_get_entitlements_forbidden(client, mocker):
    _mock_auth(mocker, make_user(999))
    _setup_mock_db(mocker)
    tenant = tenant_service.create_tenant("Corp", 1)
    res = client.get(f"/api/v1/tenants/{tenant['id']}/entitlements")
    assert res.status_code == 403


# ------------------------------------------------------------------ #
# Billing webhook (idempotent, no auth)
# ------------------------------------------------------------------ #

def test_billing_webhook(client, mocker):
    _setup_mock_db(mocker)
    res = client.post(
        "/api/v1/billing/webhook",
        json={
            "event_id": "evt_test_1",
            "event_type": "customer.subscription.created",
            "tenant_id": 1,
            "payload": {"plan": {"id": "pro"}},
        },
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["processed"] is True


def test_billing_webhook_idempotent(client, mocker):
    _setup_mock_db(mocker)
    payload = {
        "event_id": "evt_test_2",
        "event_type": "customer.subscription.created",
        "tenant_id": 1,
        "payload": {"plan": {"id": "pro"}},
    }
    r1 = client.post("/api/v1/billing/webhook", json=payload)
    r2 = client.post("/api/v1/billing/webhook", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    d1 = r1.get_json()
    d2 = r2.get_json()
    assert d1["processed"] is True
    assert d2["processed"] is False


def test_billing_webhook_missing_event_id(client, mocker):
    res = client.post(
        "/api/v1/billing/webhook",
        json={"event_type": "some.event"},
    )
    assert res.status_code == 400


def test_billing_webhook_no_body(client, mocker):
    res = client.post("/api/v1/billing/webhook")
    assert res.status_code == 400


# ------------------------------------------------------------------ #
# Error model
# ------------------------------------------------------------------ #

def test_error_model_has_request_id(client, mocker):
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.get("/api/v1/tenants")
    data = res.get_json()
    assert "request_id" in data
    assert data["status"] == "error"
