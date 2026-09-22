# Personal AI Assistant — Production Handoff Documentation

## Overview

A production-grade, security-hardened AI-native personal productivity platform built on Flask + PostgreSQL + OpenAI. Features task management, appointment scheduling, reminders, voice transcription, conversational AI, code retrieval, layered memory, agentic execution, tool gateway, cost intelligence, project workspace, unified knowledge retrieval, verification engine, automation, privacy controls, and a real-time control center.

**Version:** 1.0.0 | **Tests:** 384/384 pass | **License:** Apache-2.0

---

## Architecture

```
Browser/UI → Flask API → Auth (Bearer token, SHA-256) → Rate Limiter → Route Handlers
                                                → AI Orchestration (ai_service)
                                                → Domain Services (task/calendar/reminder)
                                                → Memory Engine (4-layer, user-isolated)
                                                → Code Retrieval (AST, hybrid search)
                                                → Knowledge Retrieval (typed sources)
                                                → Agentic Execution (plan→execute→verify)
                                                → Tool Gateway (policy, approval, audit)
                                                → Cost Intelligence (routing, caching)
                                                → Workspace (user-isolated projects)
                                                → Control Center (real metrics)
                                                → PostgreSQL (psycopg2 pool)
```

### Module / Directory Map

| Layer | Files |
|---|---|
| **Entry point** | `main.py` (app factory, middleware, error handlers) |
| **Configuration** | `config/settings.py` (centralized, validated env) |
| **DB pool** | `db/pool.py` (ThreadedConnectionPool) |
| **DB models** | `db/models.py` (SQLAlchemy for Flask-Migrate) |
| **Migrations** | `migrations/versions/001–004` (4 Alembic migrations) |
| **Auth** | `services/auth_service.py` |
| **AI** | `services/ai_service.py` |
| **Usage/Quota** | `services/usage_service.py` |
| **Rate limiting** | `services/rate_limiter.py` |
| **External API** | `services/external_api.py` |
| **Code retrieval** | `services/code_retrieval.py` |
| **Memory engine** | `services/memory_engine.py` |
| **Agentic execution** | `services/agentic_execution.py` |
| **Tool gateway** | `services/tool_gateway.py` |
| **Cost intelligence** | `services/cost_intelligence.py` |
| **Workspace** | `services/workspace.py` |
| **Knowledge retrieval** | `services/knowledge_retrieval.py` |
| **Verification engine** | `services/verification_engine.py` |
| **Automation** | `services/automation.py` |
| **Privacy** | `services/privacy.py` |
| **Control center** | `services/control_center.py` |
| **Domain services** | `services/task_service.py`, `calendar_service.py`, `reminder_service.py` |
| **Routes** | `routes/user_routes.py`, `task_routes.py`, `calendar_routes.py`, `reminder_routes.py`, `ai_routes.py` |
| **Utils** | `utils/datetime_utils.py`, `utils/validators.py` |
| **Frontend** | `templates/index.html`, `static/js/app.js`, `static/css/style.css` |
| **Tests** | `tests/` (27 modules, 384 tests) |
| **CI** | `.github/workflows/ci.yml` |
| **Deployment** | `Procfile`, `gunicorn.conf.py`, `render.yaml` |

---

## Configuration Map

All configuration is centralized in `config/settings.py` using `_require()`, `_get()`, and `_get_int()` helpers. See `.env.example` for the full list.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `SECRET_KEY` | No | `dev-insecure-change-in-production` | Flask secret key |
| `FLASK_ENV` | No | `development` | `development` or `production` |
| `CORS_ALLOWED_ORIGINS` | No | localhost (dev) | Comma-separated allowed origins |
| `OPENAI_CHAT_MODEL` | No | `gpt-4o-mini` | OpenAI model |
| `AUTH_TOKEN_EXPIRY_SECONDS` | No | `86400` (24h) | Token lifetime |
| `RATE_LIMIT_LOGIN` | No | `10` | Login attempts/min per IP |
| `RATE_LIMIT_AI` | No | `20` | AI requests/min per user |
| `RATE_LIMIT_GENERAL` | No | `60` | General requests/min per IP |
| `AI_DAILY_QUOTA_PER_USER` | No | `0` (unlimited) | Daily AI call limit per user |
| `AI_MAX_TOKENS` | No | `1024` | Max output tokens per AI response |
| `AI_MAX_TOKENS_EXTRACTION` | No | `512` | Max tokens for extraction |
| `AI_MAX_INPUT_CHARS` | No | `4000` | Max input message length |
| `AI_REQUEST_TIMEOUT` | No | `30` | OpenAI request timeout (seconds) |
| `VOICE_MAX_UPLOAD_BYTES` | No | `10485760` (10 MB) | Max voice upload size |
| `DB_POOL_MIN` | No | `1` | Min DB pool connections |
| `DB_POOL_MAX` | No | `10` | Max DB pool connections |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |

---

## DB / Migration Map

Migrations are managed by Flask-Migrate (Alembic). 4 migrations total:

| Migration | Description |
|---|---|
| `001_initial_schema.py` | Full schema for new deployments (users, tasks, appointments) |
| `002_upgrade_existing_schema.py` | Safe additive upgrade for existing DBs |
| `003_add_ai_usage_events.py` | AI usage tracking table (per-user daily quota) |
| `004_add_memories.py` | Layered memory table (4 types, user-isolated) |

**Tables:** `users`, `tasks`, `appointments`, `ai_usage_events`, `memories`

**Key constraints:** FK with CASCADE on user deletion, check constraints on status/priority/type, unique constraints on email and memory (user_id, type, key), indexes on user_id and composite indexes for query patterns.

---

## Security Model

| Control | Implementation |
|---------|----------------|
| Authentication | Bearer token, SHA-256 hashed, expiry enforced |
| Password storage | bcrypt (cost factor 12) |
| SQL injection | Parameterized queries throughout (`%s` placeholders) |
| XSS | Jinja2 autoescaping |
| CORS | Restrictive — configured origins only, no wildcards |
| Security headers | X-Content-Type-Options, X-Frame-Options, Referrer-Policy |
| Error messages | Never expose raw exceptions or stack traces |
| Anti-enumeration | Login returns same error for bad email/password |
| File uploads | Size-limited (10 MB), MIME-type validated |
| AI abuse | Per-user daily quota (configurable), input length limits |
| Rate limiting | 3-tier: login (10/min), AI (20/min), general (60/min) |
| Secrets | Environment variables only, validated at startup, no defaults in production |
| Debug mode | Disabled in production |
| User isolation | All queries scoped by `user_id` |
| Tool permissions | Least-privilege registry, approval for destructive |
| Prompt injection | Retrieved content treated as untrusted, query sanitized |
| Quota safety | Fail-closed in production — denies when DB unavailable |

---

## Testing Model

```bash
# Run all tests (no real DB or OpenAI needed)
.venv/bin/python -m pytest tests/ -v --tb=short
```

- **384 tests** across 27 modules
- No real DB or OpenAI API calls in tests
- Mock pool via `conftest.py`
- Security, migration, isolation, API integration, and full regression covered
- CI: GitHub Actions (test, secret scan, import smoke, migration parse)

---

## Deployment (Render)

1. Push to GitHub `main` branch
2. Render uses `render.yaml` (Infrastructure as Code)
3. Set secrets in Render dashboard: `OPENAI_API_KEY`, `CORS_ALLOWED_ORIGINS`
4. `SECRET_KEY` is auto-generated by `render.yaml`
5. Render health check uses `GET /health`
6. Database: Render managed PostgreSQL

### Manual deployment

```bash
pip install -r requirements.txt
# Set env vars (copy .env.example → .env and fill values)
# Never commit .env
flask db upgrade
gunicorn main:app --config gunicorn.conf.py
```

### Rollback

- `flask db downgrade` reverts one migration revision
- Each migration has a tested `downgrade()` function
- Git revert to previous commit for code rollback

---

## Troubleshooting

| Issue | Solution |
|---|---|
| DB connection refused | Check `DATABASE_URL`, ensure pool min/max are valid |
| OpenAI timeout | Check `OPENAI_API_KEY`, increase `AI_REQUEST_TIMEOUT` |
| 429 Too Many Requests | Rate limit hit — check `RATE_LIMIT_*` settings |
| AI quota exceeded | `AI_DAILY_QUOTA_PER_USER` reached — wait for UTC midnight reset |
| CORS error | Add origin to `CORS_ALLOWED_ORIGINS` |
| Token expired | Re-login to get a new token |
| Import error | Ensure `.venv/bin/python` is used (system Python lacks deps) |

---

## Ownership / License

- **Copyright:** 2026 Amin Azimi
- **License:** Apache License 2.0 — see `LICENSE` file
- **Third-party:** Dependencies retain their own licenses (Flask, OpenAI SDK, psycopg2, bcrypt, etc.)
- This license does not override third-party licenses or transfer ownership.

---

## Release Procedure

1. Ensure all tests pass: `.venv/bin/python -m pytest tests/ -v`
2. Verify CI passes on the release commit
3. Create annotated git tag: `git tag -a v1.0.0 -m "Release v1.0.0"`
4. Push tag: `git push origin v1.0.0`
5. Create GitHub Release from the tag
6. Verify tag points to exact final commit
7. Verify main branch is clean

---

## Git History (since productionization)

```
94fc97a feat(phase20): production deployment smoke tests — 18 E2E tests
a3102d9 feat(phase19): final regression / release readiness audit
8140aa2 feat(phase18): personal AI control center — real metrics dashboard
1be3f3a feat(phase14-17): unified knowledge retrieval, verification, automation, privacy
fac3fe3 feat(phase10-13): agentic execution, tool gateway, cost intelligence, workspace
f5810d8 feat(phase9): personal AI memory engine — layered, user-isolated
f277d8a feat(phase8): code retrieval & token efficiency engine
fdf08a4 feat(phase7): final security hardening audit + 27 security tests
aa12fe7 feat(phase6): production environment/Render audit + tests
5dd825f feat(phase5): database migration safety audit + tests
8048eab fix(phase2-4): production-grade rate limiting, fail-closed quota, browser timeouts
4273d1d feat(phase4): external API reliability — timeouts, bounded retries
bdc63c2 feat(phase3): DB-backed shared AI usage quota with atomic UPSERT
32b997c feat(phase2): production rate limiting via Flask-Limiter
132cea9 docs(phase1): update PROJECT_DIRECTIVE to final engineering directive
```

> **Remote status:** `origin` → `https://github.com/aminazimi42-coder/Personal-ai-assistent.git`. Local `main` is up to date with `origin/main`.

---

## Release Checklist

- [x] `.gitignore` covers secrets, venv, caches, editor artifacts
- [x] No secrets in repository
- [x] `.env.example` with all variable names
- [x] DB connection pooling (psycopg2 ThreadedConnectionPool)
- [x] Flask-Migrate migrations with FK constraints and indexes
- [x] No DDL-on-request (all schema managed by migrations)
- [x] bcrypt password hashing
- [x] Token hashed in DB (raw token never stored)
- [x] Token expiry enforced
- [x] Token revocation on logout
- [x] Anti-enumeration login
- [x] Centralized `get_current_user()` — no duplicate auth logic
- [x] All AI endpoints require authentication
- [x] Restrictive CORS (configured origins only)
- [x] Security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy)
- [x] Global JSON error handlers (never raw exceptions)
- [x] No side-effecting GET endpoints
- [x] Parameterized SQL throughout
- [x] Single-call smart-ai (no duplicate LLM calls)
- [x] Bounded token output (max_tokens on all AI calls)
- [x] Input length limits on AI messages
- [x] Per-user daily AI quota (configurable, fail-closed in production)
- [x] Voice upload size-limited and MIME-validated
- [x] Exchange rates fix (TRY and AED included)
- [x] UTC-aware timestamps throughout
- [x] Request IDs and latency logging
- [x] AI operation metadata logging (no prompt content logged)
- [x] Health (`/health`) and readiness (`/ready`) endpoints
- [x] Gunicorn configured (workers, timeout, binding, security limits)
- [x] Procfile for Render deployment
- [x] render.yaml Infrastructure as Code
- [x] GitHub Actions CI pipeline
- [x] 384 tests — 384/384 pass
- [x] No real DB or OpenAI calls in tests
- [x] All modules import cleanly
- [x] All migration files parse as valid Python
- [x] Clean git working tree
- [x] Git remote configured and up to date
- [x] Flask-Limiter installed and configured (3-tier rate limiting)
- [x] DB-backed usage quota (atomic UPSERT, fail-closed in production)
- [x] External API timeout hardening (retries, backoff, URL redaction)
- [x] LICENSE finalized (Apache 2.0)
- [x] CHANGELOG.md
- [x] README rebuilt with full capability matrix
- [x] HANDOFF synchronized with actual state
