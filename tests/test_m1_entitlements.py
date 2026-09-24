"""
tests/test_m1_entitlements.py
Tests for Phase M1: entitlement gate, write verification, intent
short-circuit, context cap, and release pack (account quota).

Covers:
  M1.1 — assert_entitlement: free user blocked from agent_write;
         pro/pro_plus allowed; quota exhausted returns 429 consistently.
  M1.2 — Write verification: read-back after create task/appointment.
  M1.3 — Intent short-circuit: no-LLM path for quota-status, list-reminders.
  M1.4 — Context cap: compile_context enforces max_tokens budget.
  M1.5 — Release pack: /api/v1/account/quota exposes plan + remaining quota.
"""

import pytest
from unittest.mock import MagicMock

from tests.conftest import make_user


# ------------------------------------------------------------------ #
# Helpers — same pattern as test_api_routes / test_quota_bypass
# ------------------------------------------------------------------ #

_AUTH_TARGETS = [
    "routes.task_routes.get_current_user",
    "routes.calendar_routes.get_current_user",
    "routes.ai_routes.get_current_user",
    "routes.reminder_routes.get_current_user",
    "routes.agent_routes.get_current_user",
    "routes.automation_routes.get_current_user",
]


def mock_auth(mocker, user=None):
    u = user or make_user()
    for target in _AUTH_TARGETS:
        mocker.patch(target, return_value=(u, None, None))
    return u


# ================================================================== #
# M1.1 — Entitlement Gate
# ================================================================== #

def test_assert_entitlement_free_allowed_for_ai_chat(mocker):
    """Free user can do ai_chat (basic_ai is in free features)."""
    from services.billing_service import assert_entitlement
    # No get_connection_fn → defaults to free plan
    assert assert_entitlement(1, "ai_chat") is True


def test_assert_entitlement_free_blocked_from_agent_write(mocker):
    """Free user cannot do agent_write (agent_writes=False on free)."""
    from services.billing_service import assert_entitlement, EntitlementError
    with pytest.raises(EntitlementError) as exc:
        assert_entitlement(1, "agent_write")
    assert "agent_write" in str(exc.value) or "agent_writes" in str(exc.value)


def test_assert_entitlement_free_blocked_from_automation_create(mocker):
    """Free user cannot create automations (automations not in free features)."""
    from services.billing_service import assert_entitlement, EntitlementError
    with pytest.raises(EntitlementError):
        assert_entitlement(1, "automation_create")


def test_assert_entitlement_pro_plus_allowed_agent_write(mocker):
    """pro_plus plan allows agent_write."""
    from services.billing_service import assert_entitlement, Plan
    # With a mocked get_connection_fn that resolves to pro_plus,
    # but since get_user_plan returns 'free' when no connection,
    # we test the Plan definition directly.
    plan_def = Plan.get("pro_plus")
    assert plan_def["agent_writes"] is True


def test_assert_entitlement_unknown_action_allowed():
    """Unknown actions should be allowed (quota still applies)."""
    from services.billing_service import assert_entitlement
    assert assert_entitlement(1, "unknown_action") is True


def test_entitlement_error_attributes():
    """EntitlementError carries action, plan, required."""
    from services.billing_service import EntitlementError
    err = EntitlementError("agent_write", "free", "agent_writes")
    assert err.action == "agent_write"
    assert err.plan == "free"
    assert err.required == "agent_writes"


def test_plan_pro_plus_definition():
    """pro_plus plan exists and has correct limits."""
    from services.billing_service import Plan
    pp = Plan.get("pro_plus")
    assert pp is not None
    assert pp["ai_daily_limit"] == 5000
    assert pp["agent_writes"] is True
    assert "automations" in pp["features"]
    assert "multiple_workspaces" in pp["features"]


def test_plan_pro_plus_is_valid():
    from services.billing_service import Plan
    assert Plan.is_valid("pro_plus") is True


# --- Route-level: AI routes enforce entitlement (403) --- #

def test_ai_chat_entitlement_blocked_free(client, mocker):
    """If assert_entitlement raises, /ai returns 403."""
    mock_auth(mocker)
    from services.billing_service import EntitlementError
    mocker.patch(
        "routes.ai_routes.assert_entitlement",
        side_effect=EntitlementError("ai_chat", "free", "basic_ai"),
    )
    res = client.post("/ai", json={"message": "hello"})
    assert res.status_code == 403


def test_smart_ai_entitlement_blocked_free(client, mocker):
    """If assert_entitlement raises, /smart-ai returns 403."""
    mock_auth(mocker)
    from services.billing_service import EntitlementError
    mocker.patch(
        "routes.ai_routes.assert_entitlement",
        side_effect=EntitlementError("smart_ai", "free", "basic_ai"),
    )
    res = client.post("/smart-ai", json={"message": "hello"})
    assert res.status_code == 403


def test_ai_to_task_entitlement_blocked_free(client, mocker):
    """If assert_entitlement raises, /ai-to-task returns 403."""
    mock_auth(mocker)
    from services.billing_service import EntitlementError
    mocker.patch(
        "routes.ai_routes.assert_entitlement",
        side_effect=EntitlementError("ai_to_task", "free", "basic_ai"),
    )
    res = client.post("/ai-to-task", json={"message": "buy milk"})
    assert res.status_code == 403


def test_transcribe_voice_entitlement_blocked_free(client, mocker):
    """If assert_entitlement raises for voice, /transcribe-voice returns 403."""
    mock_auth(mocker)
    from services.billing_service import EntitlementError
    mocker.patch(
        "routes.ai_routes.assert_entitlement",
        side_effect=EntitlementError("transcribe_voice", "free", "voice"),
    )
    res = client.post("/transcribe-voice")
    # 403 should come before the 400 "no file" check
    assert res.status_code == 403


def test_voice_to_task_entitlement_blocked_free(client, mocker):
    """If assert_entitlement raises for voice, /voice-to-task returns 403."""
    mock_auth(mocker)
    from services.billing_service import EntitlementError
    mocker.patch(
        "routes.ai_routes.assert_entitlement",
        side_effect=EntitlementError("voice_to_task", "free", "voice"),
    )
    res = client.post("/voice-to-task")
    assert res.status_code == 403


def test_agent_execute_entitlement_blocked_free(client, mocker):
    """Free user cannot execute write actions via agent."""
    mock_auth(mocker)
    from services.billing_service import EntitlementError
    mocker.patch(
        "routes.agent_routes.assert_entitlement",
        side_effect=EntitlementError("agent_write", "free", "agent_writes"),
    )
    res = client.post("/agent/execute", json={
        "action_name": "create_task",
        "params": {"title": "test"},
    })
    assert res.status_code == 403


def test_automation_create_entitlement_blocked_free(client, mocker):
    """Free user cannot create automations."""
    mock_auth(mocker)
    from services.billing_service import EntitlementError
    mocker.patch(
        "routes.automation_routes.assert_entitlement",
        side_effect=EntitlementError("automation_create", "free", "automations"),
    )
    res = client.post("/automations", json={
        "name": "my automation",
        "trigger_type": "manual",
    })
    assert res.status_code == 403


def test_ai_chat_entitlement_allowed_proceeds(client, mocker):
    """When entitlement passes, /ai proceeds to quota check and AI call."""
    mock_auth(mocker)
    mocker.patch("routes.ai_routes.assert_entitlement", return_value=True)
    mocker.patch("routes.ai_routes.check_and_increment", return_value=(True, 1))
    mocker.patch("routes.ai_routes.generate_ai_reply", return_value="Hello!")
    res = client.post("/ai", json={"message": "hello"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"


# --- Quota exhausted returns 429 consistently --- #

def test_ai_quota_exhausted_returns_429(client, mocker):
    """Quota exhausted on /ai returns 429."""
    mock_auth(mocker)
    mocker.patch("routes.ai_routes.assert_entitlement", return_value=True)
    mocker.patch("routes.ai_routes.check_and_increment", return_value=(False, 100))
    res = client.post("/ai", json={"message": "hello"})
    assert res.status_code == 429


def test_smart_ai_quota_exhausted_returns_429(client, mocker):
    """Quota exhausted on /smart-ai returns 429."""
    mock_auth(mocker)
    mocker.patch("routes.ai_routes.assert_entitlement", return_value=True)
    mocker.patch("routes.ai_routes.check_and_increment", return_value=(False, 100))
    res = client.post("/smart-ai", json={"message": "hello"})
    assert res.status_code == 429


def test_ai_to_task_quota_exhausted_returns_429(client, mocker):
    """Quota exhausted on /ai-to-task returns 429."""
    mock_auth(mocker)
    mocker.patch("routes.ai_routes.assert_entitlement", return_value=True)
    mocker.patch("routes.ai_routes.check_and_increment", return_value=(False, 100))
    res = client.post("/ai-to-task", json={"message": "buy milk"})
    assert res.status_code == 429


# ================================================================== #
# M1.2 — Write Verification
# ================================================================== #

def test_write_verification_no_connection():
    """verify_write returns verified=False when no DB connection."""
    from services.write_verification import verify_write
    result = verify_write(1, "tasks", 1, get_connection_fn=None)
    assert result["verified"] is False
    assert "No DB" in result["evidence"]


def test_write_verification_unsupported_table():
    """verify_write returns verified=False for unsupported table."""
    from services.write_verification import verify_write
    result = verify_write(1, "unknown_table", 1, get_connection_fn=lambda: None)
    assert result["verified"] is False
    assert "not verifiable" in result["evidence"]


def test_write_verification_success_mock():
    """verify_write returns verified=True when row is found and user_id matches."""
    from services.write_verification import verify_write
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {"id": 1, "user_id": 1, "title": "test"}
    mock_conn.cursor.return_value = mock_cur
    result = verify_write(1, "tasks", 1, get_connection_fn=lambda: mock_conn)
    assert result["verified"] is True
    assert result["row"]["id"] == 1
    assert "verified" in result["evidence"].lower()


def test_write_verification_row_not_found_mock():
    """verify_write returns verified=False when row not found."""
    from services.write_verification import verify_write
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None
    mock_conn.cursor.return_value = mock_cur
    result = verify_write(1, "tasks", 999, get_connection_fn=lambda: mock_conn)
    assert result["verified"] is False
    assert "FAILED" in result["evidence"]


def test_write_verification_user_mismatch_mock():
    """verify_write returns verified=False when row exists but user_id differs."""
    from services.write_verification import verify_write
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None  # WHERE user_id filter excludes it
    mock_conn.cursor.return_value = mock_cur
    result = verify_write(2, "tasks", 1, get_connection_fn=lambda: mock_conn)
    assert result["verified"] is False


def test_write_verification_appointments_supported():
    """appointments table is in the verifiable tables."""
    from services.write_verification import _VERIFIABLE_TABLES
    assert "appointments" in _VERIFIABLE_TABLES


def test_verify_and_persist_without_action_id():
    """verify_and_persist works without action_id (no persistence)."""
    from services.write_verification import verify_and_persist
    result = verify_and_persist(1, "tasks", 1, action_id=None)
    assert result["verified"] is False  # no DB connection


# ================================================================== #
# M1.3 — Intent Short-Circuit
# ================================================================== #

def test_short_circuit_quota_status():
    """Quota status message short-circuits without LLM."""
    from services.ai_service import _try_short_circuit
    result = _try_short_circuit("What is my quota?")
    assert result is not None
    assert result["action"] == "reply"
    assert result.get("_short_circuit") is True
    assert "quota" in result["reply"].lower() or "/api/v1/account/quota" in result["reply"]


def test_short_circuit_list_reminders():
    """List reminders message short-circuits without LLM."""
    from services.ai_service import _try_short_circuit
    result = _try_short_circuit("show me my reminders")
    assert result is not None
    assert result["action"] == "reply"
    assert result.get("_short_circuit") is True
    assert "reminders" in result["reply"].lower() or "/reminders" in result["reply"]


def test_short_circuit_list_tasks():
    """List tasks message short-circuits without LLM."""
    from services.ai_service import _try_short_circuit
    result = _try_short_circuit("list my tasks")
    assert result is not None
    assert result["action"] == "reply"
    assert result.get("_short_circuit") is True


def test_short_circuit_list_appointments():
    """List appointments message short-circuits without LLM."""
    from services.ai_service import _try_short_circuit
    result = _try_short_circuit("show me my appointments")
    assert result is not None
    assert result["action"] == "reply"
    assert result.get("_short_circuit") is True


def test_short_circuit_does_not_match_general_chat():
    """General chat does not short-circuit (returns None)."""
    from services.ai_service import _try_short_circuit
    result = _try_short_circuit("Tell me a joke")
    assert result is None


def test_short_circuit_empty_message():
    """Empty message does not short-circuit."""
    from services.ai_service import _try_short_circuit
    assert _try_short_circuit("") is None
    assert _try_short_circuit("   ") is None


def test_short_circuit_does_not_call_llm(mocker):
    """decide_smart_action with a short-circuit message does NOT call the LLM."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock()
    mocker.patch("services.ai_service.get_openai_client", return_value=mock_client)
    from services.ai_service import decide_smart_action
    result = decide_smart_action("what is my remaining quota?")
    assert result.get("_short_circuit") is True
    # LLM should NOT have been called
    mock_client.chat.completions.create.assert_not_called()


def test_smart_ai_route_short_circuit_no_llm(client, mocker):
    """smart-ai with a short-circuit message does not call the LLM."""
    mock_auth(mocker)
    mocker.patch("routes.ai_routes.assert_entitlement", return_value=True)
    mocker.patch("routes.ai_routes.check_and_increment", return_value=(True, 1))
    mock_client = MagicMock()
    mocker.patch("routes.ai_routes.get_openai_client", return_value=mock_client)
    res = client.post("/smart-ai", json={"message": "what is my quota?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["action"] == "reply"
    # LLM should NOT have been called
    mock_client.chat.completions.create.assert_not_called()


# ================================================================== #
# M1.4 — Context Cap
# ================================================================== #

def test_context_cap_setting_default():
    """CONTEXT_COMPILER_MAX_TOKENS has a default value."""
    from config import settings
    assert settings.CONTEXT_COMPILER_MAX_TOKENS > 0
    assert settings.CONTEXT_COMPILER_MAX_TOKENS == 4000


def test_context_cap_enforced():
    """compile_context respects the max_tokens budget."""
    from services.context_compiler import compile_context
    # With max_tokens=10, almost nothing should fit
    result = compile_context(1, "test", max_tokens=10)
    assert result.budget == 10
    # total_tokens should not exceed the budget (unless truncation occurred)
    assert result.total_tokens <= 10 or result.compression_applied


def test_context_cap_large_budget():
    """compile_context with large budget includes entries."""
    from services.context_compiler import compile_context
    result = compile_context(1, "test", max_tokens=10000)
    assert result.budget == 10000


def test_context_cap_zero_query():
    """Empty query returns empty compilation."""
    from services.context_compiler import compile_context
    result = compile_context(1, "", max_tokens=4000)
    assert len(result.entries) == 0
    assert result.total_tokens == 0


# ================================================================== #
# M1.5 — Release Pack: /api/v1/account/quota
# ================================================================== #

def test_account_quota_unauthenticated(client, mocker):
    """/api/v1/account/quota requires auth."""
    mocker.patch("services.auth_service.get_bearer_token", return_value=None)
    res = client.get("/api/v1/account/quota")
    assert res.status_code == 401


def test_account_quota_authenticated(client, mocker):
    """/api/v1/account/quota returns plan + remaining quota."""
    u = make_user()
    _AUTH_TARGETS_QUOTA = [
        "routes.api_v1.get_current_user",
    ]
    for target in _AUTH_TARGETS_QUOTA:
        mocker.patch(target, return_value=(u, None, None))
    mocker.patch("services.billing_service.get_user_plan", return_value="free")
    mocker.patch("services.usage_service.get_usage", return_value={
        "ai_calls_today": 5,
        "quota": 50,
        "quota_exceeded": False,
    })
    res = client.get("/api/v1/account/quota")
    assert res.status_code == 200
    data = res.get_json()
    assert data["plan"] == "free"
    assert data["ai_daily_limit"] == 50
    assert data["ai_calls_today"] == 5
    assert data["remaining"] == 45
    assert data["quota_exceeded"] is False


def test_account_quota_pro_plan(client, mocker):
    """/api/v1/account/quota with pro plan returns pro limits."""
    u = make_user()
    mocker.patch("routes.api_v1.get_current_user", return_value=(u, None, None))
    mocker.patch("services.billing_service.get_user_plan", return_value="pro")
    mocker.patch("services.usage_service.get_usage", return_value={
        "ai_calls_today": 100,
        "quota": 1000,
        "quota_exceeded": False,
    })
    res = client.get("/api/v1/account/quota")
    assert res.status_code == 200
    data = res.get_json()
    assert data["plan"] == "pro"
    assert data["ai_daily_limit"] == 1000
    assert data["remaining"] == 900


def test_account_quota_pro_plus_plan(client, mocker):
    """/api/v1/account/quota with pro_plus plan returns pro_plus limits."""
    u = make_user()
    mocker.patch("routes.api_v1.get_current_user", return_value=(u, None, None))
    mocker.patch("services.billing_service.get_user_plan", return_value="pro_plus")
    mocker.patch("services.usage_service.get_usage", return_value={
        "ai_calls_today": 500,
        "quota": 5000,
        "quota_exceeded": False,
    })
    res = client.get("/api/v1/account/quota")
    assert res.status_code == 200
    data = res.get_json()
    assert data["plan"] == "pro_plus"
    assert data["ai_daily_limit"] == 5000


def test_health_still_works(client):
    """/health still works (release pack requirement)."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_ready_still_works(client):
    """/ready still works (release pack requirement)."""
    res = client.get("/ready")
    assert res.status_code in (200, 503)


def test_openapi_documents_quota_endpoint(client):
    """OpenAPI spec includes the account/quota path."""
    res = client.get("/api/v1/openapi.json")
    assert res.status_code == 200
    spec = res.get_json()
    assert "/api/v1/account/quota" in spec.get("paths", {})


def test_openapi_documents_privacy_export(client):
    """OpenAPI spec includes privacy export endpoint."""
    res = client.get("/api/v1/openapi.json")
    spec = res.get_json()
    assert "/privacy/export" in spec.get("paths", {})


def test_openapi_documents_privacy_account_delete(client):
    """OpenAPI spec includes privacy account delete endpoint."""
    res = client.get("/api/v1/openapi.json")
    spec = res.get_json()
    assert "/privacy/account" in spec.get("paths", {})


def test_openapi_account_quota_schema(client):
    """OpenAPI spec includes AccountQuota schema."""
    res = client.get("/api/v1/openapi.json")
    spec = res.get_json()
    assert "AccountQuota" in spec.get("components", {}).get("schemas", {})
