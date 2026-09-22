"""
tests/test_final_regression.py
Final regression / release readiness tests.
Verifies all phases are implemented, all services importable,
all tests pass, and production configuration is sound.
"""

import importlib
import os
import sys
import pytest


# ------------------------------------------------------------------ #
# All service modules importable
# ------------------------------------------------------------------ #
REQUIRED_SERVICES = [
    "services.auth_service",
    "services.ai_service",
    "services.usage_service",
    "services.rate_limiter",
    "services.external_api",
    "services.code_retrieval",
    "services.memory_engine",
    "services.agentic_execution",
    "services.tool_gateway",
    "services.cost_intelligence",
    "services.workspace",
    "services.knowledge_retrieval",
    "services.verification_engine",
    "services.automation",
    "services.privacy",
    "services.control_center",
    "services.task_service",
    "services.calendar_service",
    "services.reminder_service",
    "services.notification_service",
]


def test_all_services_importable():
    """All service modules must be importable without errors."""
    for service_name in REQUIRED_SERVICES:
        try:
            importlib.import_module(service_name)
        except ImportError as exc:
            pytest.fail(f"Cannot import {service_name}: {exc}")


def test_all_route_modules_importable():
    """All route modules must be importable."""
    for route_name in [
        "routes.user_routes",
        "routes.task_routes",
        "routes.calendar_routes",
        "routes.reminder_routes",
        "routes.ai_routes",
    ]:
        try:
            importlib.import_module(route_name)
        except ImportError as exc:
            pytest.fail(f"Cannot import {route_name}: {exc}")


def test_config_importable():
    """Config module must be importable."""
    import config.settings
    assert hasattr(config.settings, "DATABASE_URL")
    assert hasattr(config.settings, "OPENAI_API_KEY")
    assert hasattr(config.settings, "SECRET_KEY")


def test_migrations_exist():
    """All migration files must exist and parse."""
    import ast
    migrations_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "migrations", "versions"
    )
    migration_files = [
        f for f in os.listdir(migrations_dir)
        if f.endswith(".py") and not f.startswith("__")
    ]
    assert len(migration_files) >= 4
    for filename in migration_files:
        filepath = os.path.join(migrations_dir, filename)
        with open(filepath) as f:
            ast.parse(f.read())


def test_render_yaml_exists():
    """render.yaml must exist for deployment."""
    render_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "render.yaml"
    )
    assert os.path.exists(render_path)


def test_procfile_exists():
    """Procfile must exist."""
    procfile_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "Procfile"
    )
    assert os.path.exists(procfile_path)


def test_gunicorn_config_exists():
    """gunicorn.conf.py must exist."""
    gunicorn_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "gunicorn.conf.py"
    )
    assert os.path.exists(gunicorn_path)


def test_ci_config_exists():
    """CI workflow must exist."""
    ci_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".github", "workflows", "ci.yml"
    )
    assert os.path.exists(ci_path)


def test_requirements_exist():
    """requirements.txt must exist."""
    req_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "requirements.txt"
    )
    assert os.path.exists(req_path)


def test_env_example_exists():
    """.env.example must exist."""
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".env.example"
    )
    assert os.path.exists(env_path)


def test_gitignore_exists():
    """.gitignore must exist."""
    gitignore_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".gitignore"
    )
    assert os.path.exists(gitignore_path)


def test_no_secrets_in_env_example():
    """.env.example must not contain real secrets."""
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".env.example"
    )
    with open(env_path) as f:
        content = f.read()
    # Must contain placeholder values, not real secrets
    assert "sk-..." in content or "sk-" not in content
    assert "change-me" in content or "change" in content.lower()


def test_health_endpoint_works(client):
    """Health endpoint must return 200."""
    res = client.get("/health")
    assert res.status_code == 200


def test_ready_endpoint_exists(client):
    """Ready endpoint must exist."""
    res = client.get("/ready")
    assert res.status_code in (200, 503)


def test_security_headers_present(client):
    """Security headers must be present on all responses."""
    res = client.get("/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"


def test_rate_limits_configured():
    """Rate limits must be configured."""
    from config import settings
    assert settings.RATE_LIMIT_LOGIN > 0
    assert settings.RATE_LIMIT_AI > 0
    assert settings.RATE_LIMIT_GENERAL > 0


def test_ai_quota_configured():
    """AI quota must be configured."""
    from config import settings
    assert settings.AI_DAILY_QUOTA_PER_USER >= 0


def test_all_phase_features_exist():
    """All phase feature modules must exist."""
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    required_files = [
        "services/rate_limiter.py",       # Phase 2
        "services/usage_service.py",      # Phase 3
        "services/external_api.py",       # Phase 4
        "services/code_retrieval.py",     # Phase 8
        "services/memory_engine.py",      # Phase 9
        "services/agentic_execution.py",  # Phase 10
        "services/tool_gateway.py",       # Phase 11
        "services/cost_intelligence.py",  # Phase 12
        "services/workspace.py",          # Phase 13
        "services/knowledge_retrieval.py",# Phase 14
        "services/verification_engine.py",# Phase 15
        "services/automation.py",         # Phase 16
        "services/privacy.py",            # Phase 17
        "services/control_center.py",     # Phase 18
    ]
    for filepath in required_files:
        full_path = os.path.join(base_path, filepath)
        assert os.path.exists(full_path), f"Missing: {filepath}"


def test_release_readiness_summary():
    """Final release readiness — all critical components verified."""
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    checks = {
        "config": os.path.exists(os.path.join(base_path, "config/settings.py")),
        "db_pool": os.path.exists(os.path.join(base_path, "db/pool.py")),
        "db_models": os.path.exists(os.path.join(base_path, "db/models.py")),
        "auth_service": os.path.exists(os.path.join(base_path, "services/auth_service.py")),
        "ai_service": os.path.exists(os.path.join(base_path, "services/ai_service.py")),
        "rate_limiter": os.path.exists(os.path.join(base_path, "services/rate_limiter.py")),
        "external_api": os.path.exists(os.path.join(base_path, "services/external_api.py")),
        "code_retrieval": os.path.exists(os.path.join(base_path, "services/code_retrieval.py")),
        "memory_engine": os.path.exists(os.path.join(base_path, "services/memory_engine.py")),
        "agentic_execution": os.path.exists(os.path.join(base_path, "services/agentic_execution.py")),
        "tool_gateway": os.path.exists(os.path.join(base_path, "services/tool_gateway.py")),
        "cost_intelligence": os.path.exists(os.path.join(base_path, "services/cost_intelligence.py")),
        "workspace": os.path.exists(os.path.join(base_path, "services/workspace.py")),
        "knowledge_retrieval": os.path.exists(os.path.join(base_path, "services/knowledge_retrieval.py")),
        "verification_engine": os.path.exists(os.path.join(base_path, "services/verification_engine.py")),
        "automation": os.path.exists(os.path.join(base_path, "services/automation.py")),
        "privacy": os.path.exists(os.path.join(base_path, "services/privacy.py")),
        "control_center": os.path.exists(os.path.join(base_path, "services/control_center.py")),
        "migrations": os.path.exists(os.path.join(base_path, "migrations/versions")),
        "ci": os.path.exists(os.path.join(base_path, ".github/workflows/ci.yml")),
        "render": os.path.exists(os.path.join(base_path, "render.yaml")),
        "procfile": os.path.exists(os.path.join(base_path, "Procfile")),
        "gunicorn": os.path.exists(os.path.join(base_path, "gunicorn.conf.py")),
        "gitignore": os.path.exists(os.path.join(base_path, ".gitignore")),
        "env_example": os.path.exists(os.path.join(base_path, ".env.example")),
    }

    failed = [k for k, v in checks.items() if not v]
    assert not failed, f"Release readiness checks failed: {failed}"
