<div align="center">

# PERSONAL AI ASSISTANT

### Capture · Retrieve · Understand · Plan · Act · Verify · Remember

[![Live status ribbon for Render, OpenAPI, tests, security and deployment](docs/assets/paa-status-ribbon.svg)](docs/assets/paa-status-ribbon.svg)

**Production-Grade SaaS · Active Maintenance — Not Frozen**

[![Live App](https://img.shields.io/badge/Live_App-Render-00C7B7?style=for-the-badge)](https://personal-ai-assistent.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Production-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/Tests-743%20pass-brightgreen?style=for-the-badge)](#testing--quality)
[![License](https://img.shields.io/badge/Apache-2.0-blue?style=for-the-badge)](LICENSE)

[Live Application](https://personal-ai-assistent.onrender.com) · [GitHub Repository](https://github.com/aminazimi42-coder/Personal-ai-assistent) · [API v1 OpenAPI](#api-reference--generated-openapi) · [Security Model](#security--privacy) · [Quick Start](#quick-start) · [Roadmap](#roadmap)

</div>

---

## Truth / Release Status

**Status:** Active Maintenance — Production-Grade SaaS Evolution

Personal AI Assistant has evolved beyond its v1.0.0 foundation into a production-grade multi-tenant SaaS platform. The v1.0.0 release remains immutable history (commit `f02a32f`, tag `v1.0.0`). Post-v1.0.0 evolution follows semantic versioning: security patches, backward-compatible features, and the new SaaS/billing/tenant/evaluation capabilities described in this directive.

| Signal | Verified state |
| --- | --- |
| **Live App** | [`personal-ai-assistent.onrender.com`](https://personal-ai-assistent.onrender.com) |
| **Liveness** | [`/health`](https://personal-ai-assistent.onrender.com/health) |
| **Readiness** | [`/ready`](https://personal-ai-assistent.onrender.com/ready) (DB connectivity) |
| **API v1** | `/api/v1/` with generated OpenAPI |
| **Base release** | v1.0.0 / `f02a32f` / Apache-2.0 |
| **Current state** | Active Maintenance — Not Frozen |

---

## Cinematic Hero

[![Personal AI Assistant cinematic hero — capture to memory pipeline](docs/assets/paa-cinematic-hero.svg)](docs/assets/paa-cinematic-hero.svg)

> **Capture → Retrieve → Understand → Plan → Act → Verify → Remember**
>
> Every action verified. Every tool permissioned. Every tenant isolated.

---

## Project Visual Gallery

> Four verified views of the Personal AI Assistant production baseline.

<div align="center">

| | |
| --- | --- |
| <img src="docs/screenshots/app-home.jpeg" alt="Home Dashboard — time-aware greeting, weather, location, exchange rates" width="350" /><br>**Home Dashboard** — time-aware greeting, weather, location | <img src="docs/screenshots/app-tasks.jpeg" alt="Task management — create, track, and manage tasks with priority and due dates" width="350" /><br>**Task Management** — priority, status, due dates |
| <img src="docs/screenshots/app-ai.jpeg" alt="AI chat — conversational AI, voice transcription, and smart task creation" width="350" /><br>**AI Interaction** — chat, voice, smart task creation | <img src="docs/screenshots/app-icon.png" alt="Personal AI Assistant application icon" width="200" /><br>**Application Icon** — companion avatar |

</div>

---

## Verified Technology Badges

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white) ![Flask](https://img.shields.io/badge/Flask-3.0.3-000000?style=flat-square&logo=flask&logoColor=white) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Production-4169E1?style=flat-square&logo=postgresql&logoColor=white) ![OpenAI](https://img.shields.io/badge/OpenAI-Provider-412991?style=flat-square&logo=openai&logoColor=white) ![Render](https://img.shields.io/badge/Render-Deployed-46E3B7?style=flat-square&logo=render&logoColor=111827) ![Gunicorn](https://img.shields.io/badge/Gunicorn-21.2.0-499A51?style=flat-square) ![pytest](https://img.shields.io/badge/pytest-743%20pass-brightgreen?style=flat-square) ![Apache](https://img.shields.io/badge/Apache-2.0-blue?style=flat-square)

---

## Control Center / System Snapshot

[![Personal AI Assistant control center snapshot — verified metrics from live system state](docs/assets/paa-control-center-strip.svg)](docs/assets/paa-control-center-strip.svg)

| Control-plane signal | Verified state |
| --- | --- |
| **Live App** | `personal-ai-assistent.onrender.com` |
| **API surface** | `/api/v1/` with generated OpenAPI spec |
| **Automated tests** | 743 passing (up from 384 at v1.0.0) |
| **AI provider** | Abstracted via `LLMProvider` boundary |
| **Retrieval** | Hybrid keyword + symbol search, context compression |
| **Memory** | 4-layer (short_term, task, preference, project), user-isolated |
| **Agent engine** | Durable runs with state machine, cancel, retry, idempotency |
| **Automation** | DB-backed scheduler with background job queue |
| **Multi-tenant** | Tenants, memberships, roles, subscriptions |
| **Billing** | Plan model (free/pro), idempotent webhooks, entitlements |
| **Security** | Hashed-only tokens, quota enforcement, MIME validation, prompt-injection defense |
| **Privacy** | Data export, account deletion, safe logging, AI data boundary |
| **AI evaluation** | 12 scenario families, deterministic, reproducible |
| **MCP tools** | MCP-compatible schemas routing through tool gateway |
| **Deployment** | Live Render service with PostgreSQL |

---

## Table of Contents

1. [Connected Systems](#connected-systems)
2. [Why Personal AI Assistant](#why-personal-ai-assistant)
3. [Capability Matrix](#capability-matrix)
4. [Evidence / System Journey](#evidence--system-journey)
5. [Architecture](#architecture)
6. [Technology Stack](#technology-stack)
7. [Quick Start](#quick-start)
8. [API Reference + Generated OpenAPI](#api-reference--generated-openapi)
9. [Testing & Quality](#testing--quality)
10. [Security & Privacy](#security--privacy)
11. [AI / Retrieval / Token Architecture](#ai--retrieval--token-architecture)
12. [Agentic Execution](#agentic-execution)
13. [Automation](#automation)
14. [Control Center](#control-center)
15. [Roadmap](#roadmap)
16. [Project Timeline / Release History](#project-timeline--release-history)
17. [Documentation Index](#documentation-index)
18. [Project Links Hub](#project-links-hub)
19. [Author](#author)

---

## Connected Systems

[![Connected systems visual story — user to verification through workspace, knowledge, memory, AI, tools, and action](docs/assets/paa-connected-systems.svg)](docs/assets/paa-connected-systems.svg)

Personal AI Assistant connects the user's daily workspace to AI-powered knowledge, memory, tools, and verified action. Every system boundary enforces isolation, permissions, and audit. The connected-systems story communicates the flow: **User → Workspace → Knowledge → Memory → AI → Tools → Action → Verification**.

---

## Why Personal AI Assistant

Daily cognitive load comes from fragmented tools — tasks in one app, notes in another, AI in a third, and no memory connecting them. Personal AI Assistant brings planning, contextual information, reminders, AI-assisted actions, and intelligent retrieval into one focused, secure workspace.

| Principle | Meaning |
| --- | --- |
| **Capture-First** | Voice, text, or structured input — all captured and understood |
| **Retrieval-Grounded** | AI responses use real context from your workspace, not hallucination |
| **Verified Action** | Every action produces evidence; no fabricated success |
| **Permissioned Tools** | Every tool call goes through a policy gateway with approval gates |
| **User-Isolated** | Your data never crosses into another user's context |
| **Token-Aware** | Context budgets, cost estimation, and retrieval savings are measured |
| **Tenant-Scoped** | Multi-tenant architecture with workspace-level isolation |
| **Privacy-First** | Data export, account deletion, and safe logging built in |

---

## Capability Matrix

### Implemented & Verified

| # | Capability | Evidence |
| --- | --- | --- |
| 1 | **Task Management** | CRUD with user isolation, priority, due dates, status validation |
| 2 | **Appointment Scheduling** | CRUD with user isolation, location, status, time validation |
| 3 | **Reminder Aggregation** | Tasks + appointments due within 1-hour window (UTC-aware) |
| 4 | **AI Chat** | Conversational AI via `LLMProvider` abstraction with bounded tokens |
| 5 | **Smart AI** | Single-LLM-call decision: reply vs. task creation |
| 6 | **AI-to-Task** | Natural-language task extraction with quota enforcement |
| 7 | **Voice Transcription** | OpenAI Whisper with MIME validation, filename sanitization, quota |
| 8 | **Voice-to-Task** | End-to-end: voice → transcription → task extraction → confirmation |
| 9 | **Authentication** | bcrypt, SHA-256 hashed-only token storage, expiry, revocation |
| 10 | **Rate Limiting** | 3-tier Flask-Limiter (login, AI, general) |
| 11 | **AI Quota** | Per-user daily quota, atomic UPSERT, fail-closed in production |
| 12 | **External API Reliability** | Bounded retries, exponential backoff, timeouts, URL redaction |
| 13 | **Code Retrieval** | AST symbol extraction, hybrid search, context compression, token counting |
| 14 | **Memory Engine** | 4-layer (short_term, task, preference, project), user-isolated, DB-backed |
| 15 | **Agentic Execution** | Durable runs with state machine, cancel, retry, idempotency, approval gates |
| 16 | **Tool Gateway** | Policy-based tool access, least privilege, audit logging, MCP-compatible |
| 17 | **Cost & Token Intelligence** | Model routing, token budgets, response caching, cost estimation, monthly limits |
| 18 | **Project Workspace** | DB-backed workspaces with project hierarchy and user isolation |
| 19 | **Unified Knowledge Retrieval** | Typed sources, ranking, token-budgeted context assembly |
| 20 | **Context Compiler** | Provenance, relevance, token budgets, selection explanations |
| 21 | **Verification Engine** | Evidence-based verification, no-fabricated-success guard |
| 22 | **Automation** | DB-backed scheduler, background job queue, retries, idempotency, pause/resume |
| 23 | **Privacy Controls** | Data export, account deletion, safe logging, AI data boundary |
| 24 | **Control Center** | Real metrics dashboard from live service state |
| 25 | **Multi-Tenant SaaS** | Tenants, memberships, roles, ownership, tenant-scoped resources |
| 26 | **Billing / Subscriptions** | Plan model (free/pro), idempotent webhooks, entitlement enforcement |
| 27 | **API v1 + OpenAPI** | Versioned `/api/v1/` with generated OpenAPI spec |
| 28 | **LLM Provider Abstraction** | Provider-neutral boundary, OpenAI adapter, registry, timeout/retry |
| 29 | **AI Evaluation** | 12 scenario families, deterministic, reproducible, CI-integrated |
| 30 | **MCP-Compatible Tools** | MCP schemas routing through tool gateway — MCP cannot bypass gateway |
| 31 | **Background Jobs** | Job queue with enqueue, process, status, idempotency, retries |
| 32 | **Server-Side Reminders** | Scheduled work moved out of request threads |

### Active Development

| Capability | Status |
| --- | --- |
| **Integration Tests (Testcontainers)** | Infrastructure designed; production-like tests pending real PostgreSQL |
| **Live AI Evaluation in CI** | Evaluation framework ready; live AI calls remain isolated and cost-bounded |

### Planned

| Capability | Target |
| --- | --- |
| Cognitive Memory Graph | Temporal, provenance-aware knowledge graph |
| Decision & Simulation Lab | What-if scenario modeling before consequential actions |
| Portable Personal AI Runtime | Hybrid cloud/local execution with encrypted local storage |

---

## Evidence / System Journey

[![Evidence constellation — from capture through retrieve, understand, plan, act, verify, remember](docs/assets/paa-evidence-constellation.svg)](docs/assets/paa-evidence-constellation.svg)

| Phase | Commit | Evidence |
| --- | --- | --- |
| **v1.0.0 Foundation** | `f02a32f` | 20-phase production build, 384 tests, Apache-2.0, deployed |
| **Security Hardening** | `4313f5c` | Raw token removed, quota bypass fixed, MIME validation, prompt-injection defense |
| **LLM Provider** | `4313f5c` | Provider abstraction, OpenAI adapter, timeout/retry, cost metadata |
| **SaaS / Billing** | `4313f5c` | Tenants, memberships, subscriptions, idempotent webhooks, API v1/OpenAPI |
| **Durable Agents** | `4313f5c` | DB-backed runs, state machine, cancel, retry, idempotency |
| **Context Compiler** | `4313f5c` | Provenance, relevance, token budgets, selection explanations |
| **Automation** | `4313f5c` | DB-backed scheduler, background jobs, voice-to-task |
| **AI Evaluation** | `4313f5c` | 12 scenario families, deterministic, reproducible |
| **MCP Tools** | `4313f5c` | MCP-compatible schemas routing through tool gateway |
| **Privacy** | `4313f5c` | Export, delete, safe logging, AI data boundary |
| **Control Center** | `4313f5c` | Tenant, billing, agent, automation, tool audit metrics |

---

## Architecture

```mermaid
flowchart TD
    U["User / Browser"] --> UI["Responsive Web UI"]
    UI --> API["Flask REST API"]

    API --> AUTH["Auth Service<br/>bcrypt · SHA-256 · Token Expiry"]
    API --> RL["Rate Limiter<br/>3-tier · per-IP · per-user"]
    API --> QUOTA["Usage Service<br/>Atomic UPSERT · Fail-closed"]

    API --> CORE["Task / Calendar / Reminder Services"]
    API --> LLM["LLM Provider<br/>OpenAI Adapter · Timeout · Retry"]
    API --> AGENT["Agentic Execution<br/>State Machine · Cancel · Retry"]
    API --> GATEWAY["Tool Gateway<br/>Policy · Approval · Audit · MCP"]
    API --> COST["Cost Intelligence<br/>Model routing · Caching · Monthly limits"]

    AUTH --> DB[("PostgreSQL<br/>Connection Pool")]
    CORE --> DB
    QUOTA --> DB

    LLM --> MEM["Memory Engine<br/>4-layer · User-isolated · DB-backed"]
    LLM --> RET["Code Retrieval<br/>AST · Hybrid Search · Sanitize"]
    LLM --> CC["Context Compiler<br/>Provenance · Token Budget"]
    MEM --> DB
    RET --> CC
    CC --> LLM

    API --> TENANT["Tenant Service<br/>Memberships · Roles"]
    API --> BILL["Billing Service<br/>Plans · Webhooks · Entitlements"]
    TENANT --> DB
    BILL --> DB

    API --> AUTO["Automation<br/>Scheduler · Background Jobs"]
    AUTO --> JOBS["Job Queue<br/>Enqueue · Process · Retry"]
    JOBS --> DB

    API --> V2T["Voice → Task<br/>MIME · Transcribe · Confirm"]
    API --> EVAL["AI Evaluation<br/>12 Scenario Families"]
    API --> PRIV["Privacy<br/>Export · Delete · Safe Log"]
    API --> CTRL["Control Center<br/>Real Metrics Dashboard"]
    CTRL --> DB
```

### Service Architecture Layers

| Layer | Components | Responsibility |
| --- | --- | --- |
| **HTTP/API** | `main.py`, `routes/*.py` | Request routing, response orchestration |
| **Authentication** | `services/auth_service.py` | Token hashing, expiry, revocation, user lookup |
| **Application Services** | Task, Calendar, Reminder, AI routes | Business logic orchestration |
| **Domain Services** | Memory, Retrieval, Agent, Tools, Automation | Domain-specific business logic |
| **AI/Retrieval** | `llm_provider`, `ai_service`, `code_retrieval`, `knowledge_retrieval`, `context_compiler` | LLM calls, retrieval, context compilation |
| **Agent/Tools** | `agentic_execution`, `tool_gateway`, `mcp_tools` | Action execution, tool permissions, MCP |
| **SaaS/Billing** | `tenant_service`, `billing_service` | Multi-tenant, subscriptions, entitlements |
| **Privacy/Cost** | `privacy`, `cost_intelligence`, `control_center` | Data protection, cost tracking, dashboard |
| **Persistence** | `db/pool.py`, `db/models.py`, `migrations/` | PostgreSQL connection pool, schema |
| **External Providers** | `external_api.py`, `voice_to_task.py` | External HTTP, voice transcription |

---

## Technology Stack

| Category | Technology | Version | Role |
| --- | --- | --- | --- |
| **Runtime** | Python | 3.11 | Application runtime |
| **Backend** | Flask | 3.0.3 | HTTP routing, REST API, app factory |
| **ORM/Migrations** | Flask-SQLAlchemy + Flask-Migrate | 3.1.1 + 4.0.7 | Schema management (Alembic) |
| **Rate Limiting** | Flask-Limiter | 3.5.1 | 3-tier rate limiting |
| **Database** | PostgreSQL | — | Persistent relational storage |
| **DB Driver** | psycopg2-binary | 2.9.9 | ThreadedConnectionPool |
| **AI** | OpenAI Python SDK | 1.30.1 | GPT-4o-mini, Whisper |
| **Security** | bcrypt | 4.1.2 | Password hashing |
| **HTTP** | requests | 2.31.0 | External API calls |
| **Server** | Gunicorn | 21.2.0 | WSGI production server |
| **Frontend** | HTML5 + CSS3 + Vanilla JS | — | Responsive SPA |
| **CI/CD** | GitHub Actions | — | Test + secret scan + import smoke |
| **Deployment** | Render | — | Cloud hosting |

---

## Quick Start

```bash
# Clone
git clone https://github.com/aminazimi42-coder/Personal-ai-assistent.git
cd Personal-ai-assistent

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
export DATABASE_URL="postgresql://user:pass@localhost/personal_ai_assistant"
export OPENAI_API_KEY="sk-..."
export SECRET_KEY="your-secret-key"
export FLASK_ENV="development"

# Run migrations
flask db upgrade

# Start the server
gunicorn main:app --config gunicorn.conf.py
# or: python main.py
```

**Live application:** https://personal-ai-assistent.onrender.com

> Free-tier cloud instances may require a short warm-up period after inactivity.

---

## API Reference + Generated OpenAPI

### Versioned API v1

All new SaaS capabilities are exposed through `/api/v1/`:

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/api/v1/health` | No | Health check |
| `GET` | `/api/v1/openapi.json` | No | Generated OpenAPI specification |
| `POST` | `/api/v1/tenants` | Yes | Create a tenant |
| `GET` | `/api/v1/tenants` | Yes | List user's tenants |
| `POST` | `/api/v1/tenants/{id}/members` | Yes | Add a member |
| `GET` | `/api/v1/tenants/{id}/members` | Yes | List members |
| `GET` | `/api/v1/tenants/{id}/subscription` | Yes | Get subscription |
| `POST` | `/api/v1/tenants/{id}/subscription` | Yes | Create subscription |
| `POST` | `/api/v1/billing/webhook` | No | Idempotent billing webhook |
| `GET` | `/api/v1/ai-evaluation` | Yes | Run AI evaluations |
| `GET` | `/api/v1/mcp-tools` | Yes | List MCP tool schemas |

### Platform Endpoints

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/health` | No | Liveness probe |
| `GET` | `/ready` | No | Readiness probe (DB connectivity) |
| `POST` | `/signup` | No | Create account → returns token |
| `POST` | `/login` | No | Authenticate → returns token |
| `POST` | `/logout` | Yes | Revoke token |
| `GET` | `/me` | Yes | Current user profile |
| `GET` | `/me/usage` | Yes | Today's AI usage and quota |
| `GET` | `/tasks` | Yes | List/create tasks |
| `GET` | `/appointments` | Yes | List/create appointments |
| `GET` | `/reminders` | Yes | Due within 1-hour window |
| `POST` | `/ai` | Yes | Conversational AI chat |
| `POST` | `/smart-ai` | Yes | Smart AI: reply or task |
| ` `POST` | `/ai-to-task` | Yes | Extract task from natural language |
| `POST` | `/transcribe-voice` | Yes | Voice → text transcription |
| `POST` | `/agent/execute` | Yes | Execute an agent action |
| `GET` | `/agent/runs` | Yes | List agent runs |
| `GET` | `/workspaces` | Yes | List/create workspaces |
| `POST` | `/automations` | Yes | List/create automations |
| `GET` | `/control-center` | Yes | Dashboard metrics |
| `GET` | `/privacy/policy` | No | Privacy policy |
| `GET` | `/privacy/export` | Yes | Export user data |

> **Auth:** All protected endpoints require `Authorization: Bearer <token>` header.
> Tokens are 48-byte URL-safe random values, stored as SHA-256 hashes (raw token never persisted), with configurable expiry (default 24h).

---

## Testing & Quality

| Metric | Value |
| --- | --- |
| **Total Tests** | 743 |
| **Test Modules** | 40+ |
| **Pass Rate** | 100% (743/743) |
| **External Dependencies** | None (no real DB or OpenAI calls in tests) |
| **Test Framework** | pytest 8.2.2 + pytest-mock 3.14.0 |

### Test Coverage by Area

| Area | Tests | Coverage |
| --- | --- | --- |
| Security & Auth | 70+ | Token hashing, bcrypt, CORS, headers, SQL injection, quota bypass |
| AI Service & Provider | 60+ | LLM provider, AI reply, JSON extraction, smart action, fallbacks |
| Code/Knowledge Retrieval | 30+ | AST extraction, hybrid search, compression, token counting, context compiler |
| Memory Engine | 20+ | 4-layer memory, CRUD, search, expiry, isolation |
| Agentic Execution | 40+ | State machine, cancel, retry, idempotency, approval, isolation |
| Tool Gateway & MCP | 37+ | Registry, policy, approval, MCP schemas, bypass prevention |
| Tenant & Billing | 35+ | Tenants, memberships, subscriptions, webhooks, entitlements |
| Automation & Jobs | 25+ | Triggers, scheduler, background jobs, voice-to-task |
| Privacy & Cost | 50+ | Export, delete, safe logging, cost dashboard, cache stats |
| AI Evaluation | 46+ | 12 scenario families, determinism, reproducibility |
| Control Center | 30+ | Dashboard metrics, cost, comprehensive snapshot |
| Workspace & Routes | 60+ | DB-backed workspace, project CRUD, API routes |
| Migration Safety | 13+ | Chain validation, syntax, additive upgrade, FK, downgrade |

### CI Pipeline

GitHub Actions CI runs on every push to `main` and every PR:

1. **Dependency install** — `pip install -r requirements.txt`
2. **Secret scan** — scans tracked files for API keys
3. **Full test suite** — `pytest tests/ -v --tb=short`
4. **Import smoke check** — verifies all modules import cleanly
5. **Migration validation** — all migration files parse as valid Python

---

## Security & Privacy

### Security Controls

| Control | Implementation | Verified By |
| --- | --- | --- |
| **Password Storage** | bcrypt (cost factor 12) | `test_security_hardening.py` |
| **Token Storage** | SHA-256 hash only — raw token never persisted | `test_auth_service.py`, `test_security_hardening.py` |
| **Token Expiry** | Enforced at query time (`token_expires_at > NOW()`) | `test_auth_service.py` |
| **Token Revocation** | Immediate — nulls hash on logout | `test_api_routes.py` |
| **Anti-Enumeration** | Same error for bad email / bad password | `test_security_hardening.py` |
| **SQL Injection** | Parameterized queries throughout (`%s` placeholders) | `test_security_hardening.py` |
| **CORS** | Restrictive — configured origins only, no wildcards | `test_production_env.py` |
| **Security Headers** | X-Content-Type-Options, X-Frame-Options, Referrer-Policy | `test_security_hardening.py` |
| **Rate Limiting** | 3-tier: login (10/min), AI (20/min), general (60/min) | `test_rate_limiter.py` |
| **AI Quota** | Per-user daily, atomic UPSERT, fail-closed in production | `test_usage_service.py`, `test_quota_bypass.py` |
| **Quota Bypass** | ai-to-task + transcription enforce quota | `test_quota_bypass.py` |
| **Upload Security** | MIME validation, filename sanitization, size limits | `test_quota_bypass.py` |
| **Prompt Injection** | Query sanitization, control-char stripping, length bounds | `test_quota_bypass.py` |
| **Tool Permissions** | Least-privilege registry, approval for destructive | `test_tool_gateway.py`, `test_mcp_tools.py` |
| **MCP Boundary** | MCP tools route through gateway — cannot bypass | `test_mcp_tools.py` |
| **User Isolation** | All queries scoped by `user_id` | `test_user_isolation.py` |
| **Secrets** | Environment variables only, validated at startup | `test_config.py` |

### Privacy Controls

| Control | Implementation |
| --- | --- |
| **Data Export** | `GET /privacy/export` — exports all user data |
| **Account Deletion** | `DELETE /privacy/account` — cascades all user data |
| **Memory Deletion** | User-controlled memory deletion |
| **Safe Logging** | `privacy_safe_log()` masks tokens, passwords, emails |
| **AI Data Boundary** | `enforce_ai_data_boundary()` — classified data not in AI context |
| **Data Classification** | PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED |
| **Retention Policies** | Per-category retention with expiry |
| **Privacy Policy** | `GET /privacy/policy` — public endpoint |

---

## AI / Retrieval / Token Architecture

### LLM Provider Abstraction

```
Application Logic → LLMProvider (abstract) → OpenAIProvider (adapter) → OpenAI API
```

| Feature | Implementation |
| --- | --- |
| **Provider Registry** | `get_provider(name)`, `register_provider(name, provider)` |
| **Default Provider** | OpenAIProvider with configurable model |
| **Timeout** | Configurable `AI_REQUEST_TIMEOUT` (default 30s) |
| **Retries** | Bounded with exponential backoff |
| **Error Normalization** | `LLMError` exception class |
| **Cost Metadata** | Model, input/output tokens, estimated cost |
| **Telemetry** | Model, duration, tokens logged per call |

### Retrieval Pipeline

```
USER REQUEST → QUERY SANITIZATION → REPOSITORY INGESTION →
AST SYMBOL EXTRACTION → HYBRID SEARCH (keyword + symbol) →
RELEVANCE RANKING (type-weighted) → CONTEXT COMPRESSION →
TOKEN-BUDGET GUARD → CONTEXT COMPILER → LLM → RESPONSE
```

| Component | Key Features |
| --- | --- |
| **Code Retrieval** | AST parsing, hybrid search, context compression, tiktoken counting |
| **Memory Engine** | 4-layer (short_term/task/preference/project), user-isolated, DB-backed |
| **Knowledge Retrieval** | Typed sources (code/memory/task/note/project), ranked, token-budgeted |
| **Context Compiler** | Provenance, relevance ranking, token budget, selection explanation |
| **Cost Intelligence** | Model routing, response caching, cost estimation, monthly limits |

### Token Budget

| Metric | Measurement |
| --- | --- |
| Input tokens without retrieval | Measured per AI call |
| Input tokens with retrieval | Measured per AI call |
| Tokens saved by retrieval | Computed difference |
| Context size | Token count of assembled context |
| Retrieval latency | `time.monotonic()` measured |
| Estimated cost | Per-model pricing table |

---

## Agentic Execution

```
PLAN → RETRIEVE → ANALYZE → PROPOSE → APPROVAL → EXECUTE → VERIFY → EVIDENCE → REPORT
```

| Feature | Implementation |
| --- | --- |
| **Persistent Runs** | `agent_runs` table with state machine |
| **State Machine** | PENDING → APPROVED → EXECUTING → COMPLETED/FAILED/DENIED/CANCELED |
| **Idempotency** | Unique `action_id` — completed runs return existing result |
| **Cancellation** | `cancel_action(action_id, user_id)` |
| **Retries** | `retry_action(action_id, user_id)` — re-execute failed actions |
| **Approval Gates** | Destructive actions require explicit approval |
| **User Isolation** | All runs scoped by `user_id` |
| **Audit Trail** | Created, updated, completed timestamps |
| **API** | `POST /agent/execute`, `POST /agent/approve`, `POST /agent/cancel`, `GET /agent/runs` |

---

## Automation

```
TRIGGER → CONDITION → AI PROCESSING → ACTION → VERIFICATION
```

| Feature | Implementation |
| --- | --- |
| **Durable Automations** | DB-backed with `automations` table |
| **Background Jobs** | Job queue with `jobs` table — enqueue, process, retry |
| **Triggers** | Daily, hourly, event, manual |
| **Idempotency** | Duplicate detection by payload hash |
| **Retries** | Max retries with exponential backoff |
| **Pause/Resume** | Enable/disable automations |
| **Daily Limits** | Max executions per day per automation |
| **Execution History** | `automation_runs` table |
| **API** | `POST /automations`, `GET /automations`, `POST /automations/{id}/execute` |

---

## Control Center

Real metrics from live service state — not a static mock dashboard.

| Metric | Source |
| --- | --- |
| AI calls today | `usage_service.get_usage()` |
| Monthly cost | `cost_intelligence.get_monthly_usage()` |
| Total tokens | Aggregated from AI call metadata |
| Retrieval savings | Token delta with/without retrieval |
| Memory count by type | `memory_engine` aggregation |
| Workspace/project count | `workspace` service |
| Task count by status | Task queries |
| Automation count/status | `automation` service |
| Agent run count | `agentic_execution` service |
| Tool audit events | `tool_gateway` audit log |
| Tenant/billing status | `tenant_service` + `billing_service` |
| Rate limit configuration | `rate_limiter` settings |
| CORS origins count | `settings.CORS_ALLOWED_ORIGINS` |

**API:** `GET /control-center` (authenticated), `GET /control-center/cost` (authenticated)

---

## Roadmap

> The following stages are **future-only** — not part of the current release.

### ROADMAP 01 — Cognitive Memory Graph

Temporal, provenance-aware personal knowledge graph connecting person, preference, project, task, conversation, decision, document, code, and outcome.

### ROADMAP 02 — Decision & Simulation Lab

Structured what-if scenario modeling before consequential actions — options, assumptions, expected effects, risks, dependencies, uncertainty, and verification plans.

### ROADMAP 03 — Portable Personal AI Runtime

Hybrid cloud/local execution with encrypted local storage and explicit policy controlling what data may leave the device.

### ROADMAP 04 — Production Integration Test Suite

Testcontainers PostgreSQL integration tests for real DB, migration upgrade/downgrade, concurrent quota, pool behavior, multi-worker, and tenant isolation.

---

## Project Timeline / Release History

| Release | Date | Tests | Description |
| --- | --- | --- | --- |
| **v1.0.0** | 2026-09-21 | 384 | Initial production release — 20 phases, Apache-2.0, deployed |
| **v1.1.0** | 2026-09-22 | 743 | Evolution: SaaS, billing, tenants, agents, MCP, evaluation, privacy |

See [CHANGELOG.md](CHANGELOG.md) for the full release notes.

---

## Documentation Index

| Document | Path | Description |
| --- | --- | --- |
| **Project Directive** | `PROJECT_DIRECTIVE.txt` | Master engineering directive |
| **Changelog** | `CHANGELOG.md` | Release history and changes |
| **Handoff** | `HANDOFF.md` | Engineering handoff notes |
| **License** | `LICENSE` | Apache 2.0 full text |
| **Environment Example** | `.env.example` | Configuration template |
| **Migration Source** | `migrations/versions/` | Alembic migration chain (001–009) |
| **OpenAPI Spec** | `/api/v1/openapi.json` | Generated OpenAPI specification (live) |

---

## Project Links Hub

| Link | URL |
| --- | --- |
| **Live Application** | https://personal-ai-assistent.onrender.com |
| **GitHub Repository** | https://github.com/aminazimi42-coder/Personal-ai-assistent |
| **Health Check** | https://personal-ai-assistent.onrender.com/health |
| **Readiness Check** | https://personal-ai-assistent.onrender.com/ready |
| **App Info** | https://personal-ai-assistent.onrender.com/app-info |

---

## Author

[![Amin Azimi AI Architect author command deck](docs/assets/author-command-deck.svg)](docs/assets/author-command-deck.svg)

# AMIN AZIMI

### AI ARCHITECT

**End-to-End AI Systems Architecture · AI Product Architecture · Evidence-Based AI · Production AI Systems**

Personal AI Assistant is architected as a complete production-grade SaaS platform: from security-hardened authentication and multi-tenant isolation to AI-powered retrieval, durable agentic execution, permissioned tool gateway, and verified action with evidence. The author position is system-level and end-to-end, with responsibility centered on architectural integrity, reproducibility, security boundaries, and truthful technical communication.

[![Bob engineering agent portrait — the bounded engineering copilot](docs/assets/bob-agent-portrait.svg)](docs/assets/bob-agent-portrait.svg)

### Bob Engineering Agent

Bob is the **Engineering copilot** used to help design, implement, inspect, and qualify this repository. Bob is **not a deployed runtime service**, production operator, or autonomous decision-maker inside Personal AI Assistant.

| Responsibility | What Bob may do | Required evidence |
| --- | --- | --- |
| **Repository analysis** | Inspect architecture, contracts, tests, migrations | File identities, diffs, reproducible diagnostics |
| **Implementation support** | Propose bounded code and documentation changes | Test-first failure, focused verification, atomic scope |
| **Quality assurance** | Run formatting, linting, tests, coverage | Captured command output and fail-closed result |
| **Deployment preparation** | Diagnose Render and migration failures | Local build, health check, pinned commit evidence |
| **Documentation** | Maintain truthful architecture and release status | Links to source, tests, checkpoints, live endpoints |
| **Rollback protection** | Preserve clean state when a gate fails | Explicit rollback and post-failure repository status |

### Bob's Operating Contract

1. Human intent defines scope before any repository-changing action.
2. Changes are minimized, testable, reviewable, and bound to explicit files.
3. Missing evidence, failed tests, or conflicting state never becomes a pass.
4. Bob cannot authorize production use, paid services, credentials, or legal claims.
5. Git pushes and deployments remain explicit human-controlled actions.
6. Every successful change ends with reproducible evidence and a clear next gate.

**Azimi Innovation Lab**

---

<div align="center">

**PERSONAL AI ASSISTANT**
**PRODUCTION-GRADE SaaS**
**ENGINEERING-COMPLETE FOR THIS DIRECTIVE**
**SECURITY-VERIFIED · DATA-INTEGRITY-VERIFIED · AI-EVALUATED**
**DOCUMENTATION-COMPLETE · CINEMATIC README COMPLETE**
**RELEASE/VERSION SYNCHRONIZED · REMOTE-VERIFIED**
**ACTIVE MAINTENANCE — NOT FROZEN**

© Azimi Innovation Lab — Apache 2.0

</div>
