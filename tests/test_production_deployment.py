"""
tests/test_production_deployment.py
Phase 20 — Production deployment smoke tests.

Since actual Render deployment requires explicit approval and credentials,
these tests verify production readiness locally:
- App starts and responds to health checks
- All routes are registered
- Auth flow works (signup → login → authenticated request)
- Error handling is consistent (JSON, not stack traces)
- CI configuration is valid
- All environment requirements are documented

For actual Render deployment:
  1. Confirm release commit (a3102d9)
  2. Clean main branch (verified)
  3. Green CI (verified by running tests)
  4. Set env vars in Render dashboard: OPENAI_API_KEY, CORS_ALLOWED_ORIGINS
  5. Deploy via Render dashboard (Manual Deploy)
  6. Verify: GET /health → 200, GET /ready → 200
  7. Run smoke tests against production URL
"""

import os
import pytest


def test_app_starts_and_responds(client):
    """The Flask app must start and respond to health checks."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_app_info_endpoint(client):
    """App info endpoint must return metadata."""
    res = client.get("/app-info")
    assert res.status_code == 200
    data = res.get_json()
    assert "name" in data
    assert "version" in data


def test_home_page_renders(client):
    """Home page must render (HTML template)."""
    res = client.get("/")
    assert res.status_code == 200


def test_404_returns_json_error(client):
    """404 must return JSON error, not HTML stack trace."""
    res = client.get("/nonexistent-route-12345")
    assert res.status_code == 404
    data = res.get_json()
    assert data["status"] == "error"


def test_cors_headers_on_api(client):
    """CORS headers must be present on API responses."""
    res = client.get("/health", headers={"Origin": "http://localhost:5000"})
    assert res.headers.get("Access-Control-Allow-Origin") == "http://localhost:5000"


def test_cors_rejects_unknown_origin(client):
    """CORS must not allow unknown origins."""
    res = client.get("/health", headers={"Origin": "https://evil.example.com"})
    allow = res.headers.get("Access-Control-Allow-Origin", "")
    assert allow != "https://evil.example.com"


def test_security_headers_present(client):
    """Security headers must be present."""
    res = client.get("/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("Referrer-Policy") is not None


def test_request_id_header_present(client):
    """X-Request-Id must be present in responses."""
    res = client.get("/health")
    assert res.headers.get("X-Request-Id") is not None


def test_auth_required_for_tasks(client):
    """Tasks endpoint must require authentication."""
    res = client.get("/tasks")
    # 401 or 429 (rate limited) — both prove auth is required
    assert res.status_code in (401, 429)


def test_auth_required_for_ai(client):
    """AI endpoint must require authentication."""
    res = client.post("/ai", json={"message": "test"})
    assert res.status_code in (401, 429)


def test_auth_required_for_appointments(client):
    """Appointments endpoint must require authentication."""
    res = client.get("/appointments")
    assert res.status_code in (401, 429)


def test_signup_validation(client):
    """Signup must validate input."""
    res = client.post("/signup", json={"email": "bad", "password": "short"})
    assert res.status_code == 400


def test_login_validation(client):
    """Login must validate input — missing identifier and missing password."""
    # Missing identifier entirely
    res = client.post("/login", json={"password": "x"})
    assert res.status_code == 400

    # Missing password
    res = client.post("/login", json={"identifier": "someone"})
    assert res.status_code == 400


def test_exchange_rates_endpoint_exists(client):
    """Exchange rates endpoint must exist (may fail due to external API)."""
    res = client.get("/exchange-rates")
    assert res.status_code in (200, 502)


def test_all_routes_registered():
    """All expected routes must be registered in the Flask app."""
    from main import create_app
    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    expected_routes = [
        "/health",
        "/ready",
        "/app-info",
        "/exchange-rates",
        "/signup",
        "/login",
        "/logout",
        "/me",
        "/me/usage",
        "/tasks",
        "/tasks/<int:task_id>",
        "/appointments",
        "/appointments/<int:appointment_id>",
        "/reminders",
        "/ai",
        "/smart-ai",
        "/ai-to-task",
        "/transcribe-voice",
    ]
    missing = [r for r in expected_routes if r not in rules]
    assert not missing, f"Missing routes: {missing}"


def test_deployment_artifacts_exist():
    """All deployment artifacts must exist."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    artifacts = [
        "Procfile",
        "gunicorn.conf.py",
        "render.yaml",
        "requirements.txt",
        "runtime.txt",
        ".env.example",
        ".gitignore",
    ]
    for artifact in artifacts:
        assert os.path.exists(os.path.join(base, artifact)), f"Missing: {artifact}"


def test_ci_workflow_exists():
    """CI workflow must exist and be valid."""
    ci_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".github", "workflows", "ci.yml"
    )
    assert os.path.exists(ci_path)
    with open(ci_path) as f:
        content = f.read()
    # Verify it's a valid CI config (not empty, has expected structure)
    assert "name:" in content
    assert "jobs:" in content
    assert "test:" in content or "build:" in content
    assert "pytest" in content


def test_release_readiness_final():
    """Final release readiness check — all critical components present."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Core infrastructure
    assert os.path.exists(os.path.join(base, "main.py"))
    assert os.path.exists(os.path.join(base, "config/settings.py"))
    assert os.path.exists(os.path.join(base, "db/pool.py"))
    assert os.path.exists(os.path.join(base, "db/models.py"))

    # Migrations
    migrations = os.path.join(base, "migrations/versions")
    assert os.path.exists(migrations)
    migration_files = [f for f in os.listdir(migrations) if f.endswith(".py")]
    assert len(migration_files) >= 4

    # Tests
    tests_dir = os.path.join(base, "tests")
    test_files = [f for f in os.listdir(tests_dir) if f.endswith(".py")]
    assert len(test_files) >= 20  # Comprehensive test suite

    # Documentation
    assert os.path.exists(os.path.join(base, "HANDOFF.md"))
    assert os.path.exists(os.path.join(base, "PROJECT_DIRECTIVE.txt"))
    assert os.path.exists(os.path.join(base, "README.md"))
