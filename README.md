<div align="center">

# Personal AI Assistant

### Capture · Retrieve · Understand · Plan · Act · Verify · Remember

**An AI-assisted personal productivity workspace evolving into a production-grade SaaS platform.**

[![Status ribbon](docs/assets/paa-status-ribbon.svg)](docs/assets/paa-status-ribbon.svg)

</div>

---

## Truth / Release Status

| Signal | Verified state |
| --- | --- |
| **Live App** | [`personal-ai-assistent.onrender.com`](https://personal-ai-assistent.onrender.com) |
| **Liveness** | [`/health`](https://personal-ai-assistent.onrender.com/health) |
| **Readiness** | [`/ready`](https://personal-ai-assistent.onrender.com/ready) (DB connectivity) |
| **API v1** | `/api/v1/` with generated OpenAPI spec (`_build_openapi_spec`) |
| **Current version** | 1.1.0 |
| **Immutable baseline** | v1.0.0 / `f02a32f` / Apache-2.0 |
| **Tests** | 802 passing (real count from this run) |
| **License** | Apache-2.0 ([LICENSE](LICENSE)) |
| **Status** | Active maintenance — not a commercial market launch yet |

---

## Cinematic Hero

[![Personal AI Assistant cinematic hero — capture to memory pipeline](docs/assets/paa-cinematic-hero.svg)](docs/assets/paa-cinematic-hero.svg)

> **Capture → Retrieve → Understand → Plan → Act → Verify → Remember**
>
> Every action verified. Every tool permissioned. Every workspace user-isolated.

---

## Screenshot Gallery

> Verified views of the Personal AI Assistant application.

<div align="center">

| | |
| --- | --- |
| <img src="docs/screenshots/app-home.jpeg" alt="Home Dashboard — time-aware greeting, weather, location, exchange rates" width="350" /><br>**Home Dashboard** — time-aware greeting, weather, location | <img src="docs/screenshots/app-tasks.jpeg" alt="Task management — create, track, and manage tasks with priority and due dates" width="350" /><br>**Task Management** — priority, status, due dates |
| <img src="docs/screenshots/app-ai.jpeg" alt="AI chat — conversational AI, voice transcription, and smart task creation" width="350" /><br>**AI Interaction** — chat, voice, smart task creation | <img src="docs/screenshots/app-icon.png" alt="Personal AI Assistant application icon" width="200" /><br>**Application Icon** — companion avatar |

</div>

---

## True Badges Only

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0.3-000000?style=flat-square&logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Production-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Apache](https://img.shields.io/badge/Apache-2.0-blue?style=flat-square)
![pytest](https://img.shields.io/badge/pytest-802%20pass-brightgreen?style=flat-square)

> No fake coverage badge. Test count reflects the actual run (802/802 pass).

---

## Journey Frame

| ORIGIN | CURRENT | INTENDED |
| --- | --- | --- |
| **v1.0.0 — personal productivity foundation** | **Aligned SaaS core after integrity work** | **Production-grade SaaS market offer** |
| Tasks, calendar, reminders, AI, voice, auth, quota, Render deployment. 384 tests. Immutable baseline (`f02a32f`, Apache-2.0). | Hashed-only tokens, quota boundaries on all cost routes, workspace DB path with user isolation, real agent executors on allowlisted writes (no simulated COMPLETE), `/api/v1` with generated OpenAPI, tenant vs. workspace boundary documented. 802 tests. | A production-grade SaaS market offering and a later iPhone client. Not yet shipped. |

> This product is not offered to the market until that intended output is real.

---

## Why Personal AI Assistant

Daily cognitive load comes from fragmented tools — tasks in one app, notes in another, AI in a third, and no memory connecting them. Personal AI Assistant brings planning, contextual information, reminders, AI-assisted actions, and intelligent retrieval into one focused, secure workspace.

| Principle | Meaning |
| --- | --- |
| **Capture-First** | Voice, text, or structured input — all captured and understood |
| **Retrieval-Grounded** | AI responses use real context from your workspace, not hallucination |
| **Verified Action** | Every action produces evidence; no fabricated success |
| **User-Isolated** | Your data never crosses into another user's context |
| **Token-Aware** | Context budgets, cost estimation, and retrieval savings are measured |

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
| **Integration Tests (Testcontainers)** | Infrastructure designed; production-like tests pending real PostgreSQL isolation suite |
| **Live AI Evaluation in CI** | Evaluation framework ready; live AI calls remain isolated and cost-bounded |
| **Live Payment Processor** | Billing model and webhook path exist; live processor integration not yet proven in production-like env |
| **Distributed Rate Limiting** | Per-process Flask-Limiter in place; multi-worker distributed limiter not yet proven |

### Planned

> Future only — owner may add or revise later. Not locked as final.

| Capability | Target |
| --- | --- |
| iPhone / App Store client | Native iOS companion app |
| Richer billing provider | Full live payment processor integration |
| Distributed rate limiting | Across multiple workers |
| Cognitive Memory Graph | Temporal, provenance-aware knowledge graph |
| Decision & Simulation Lab | What-if scenario modeling before consequential actions |
| Portable Personal AI Runtime | Hybrid cloud/local execution with encrypted local storage |

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
```

### Technology Stack

| Category | Technology | Role |
| --- | --- | --- |
| **Runtime** | Python 3.11 | Application runtime |
| **Backend** | Flask 3.0.3 | HTTP routing, REST API, app factory |
| **ORM/Migrations** | Flask-SQLAlchemy + Flask-Migrate | Schema management (Alembic) |
| **Rate Limiting** | Flask-Limiter 3.5.1 | 3-tier rate limiting |
| **Database** | PostgreSQL | Persistent relational storage |
| **DB Driver** | psycopg2-binary 2.9.9 | ThreadedConnectionPool |
| **AI** | OpenAI Python SDK 1.30.1 | GPT-4o-mini, Whisper via `LLMProvider` abstraction |
| **Security** | bcrypt 4.1.2 | Password hashing |
| **Server** | Gunicorn 21.2.0 | WSGI production server |
| **Deployment** | Render | Cloud hosting |

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

# Configure environment (see .env.example for full list)
export DATABASE_URL="postgresql://user:***@localhost/personal_ai_assistant"
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

## API

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

The OpenAPI spec is generated by `_build_openapi_spec()` in `routes/api_v1.py` and served at `/api/v1/openapi.json`.

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
| `POST` | `/ai-to-task` | Yes | Extract task from natural language |
| `POST` | `/transcribe-voice` | Yes | Voice → text transcription |
| `POST` | `/agent/execute` | Yes | Execute an agent action |
| `GET` | `/agent/runs` | Yes | List agent runs |
| `GET` | `/workspaces` | Yes | List/create workspaces |
| `POST` | `/automations` | Yes | List/create automations |
| `GET` | `/control-center` | Yes | Dashboard metrics |
| `GET` | `/privacy/policy` | No | Privacy policy |
| `GET` | `/privacy/export` | Yes | Export user data |

> **Auth:** All protected endpoints require `Authorization: Bearer <token>` header. Tokens are 48-byte URL-safe random values, stored as SHA-256 hashes (raw token never persisted), with configurable expiry (default 24h).

---

## Security & Privacy

### Security Controls

| Control | Implementation |
| --- | --- |
| **Password Storage** | bcrypt (cost factor 12) |
| **Token Storage** | SHA-256 hash only — raw token never persisted |
| **Token Expiry** | Enforced at query time (`token_expires_at > NOW()`) |
| **Token Revocation** | Immediate — nulls hash on logout |
| **Anti-Enumeration** | Same error for bad email / bad password |
| **SQL Injection** | Parameterized queries throughout (`%s` placeholders) |
| **CORS** | Restrictive — configured origins only, no wildcards |
| **Security Headers** | X-Content-Type-Options, X-Frame-Options, Referrer-Policy |
| **Rate Limiting** | 3-tier: login (10/min), AI (20/min), general (60/min) |
| **AI Quota** | Per-user daily, atomic UPSERT, fail-closed in production |
| **Quota Bypass** | ai-to-task + transcription + voice-to-task + evaluation all enforce quota |
| **Upload Security** | MIME validation, filename sanitization, size limits |
| **Prompt Injection** | Query sanitization, control-char stripping, length bounds |
| **Tool Permissions** | Least-privilege registry, approval for destructive, audit logging |
| **MCP Boundary** | MCP tools route through gateway — cannot bypass |
| **User Isolation** | All queries scoped by `user_id` |

### Privacy Controls

| Control | Implementation |
| --- | --- |
| **Data Export** | `GET /privacy/export` — exports all user data |
| **Account Deletion** | `DELETE /privacy/account` — cascades all user data |
| **Safe Logging** | `privacy_safe_log()` masks tokens, passwords, emails |
| **AI Data Boundary** | `enforce_ai_data_boundary()` — classified data not in AI context |
| **No Transcript/Token Logging** | AI metadata logs model/tokens/duration — never prompt content or raw tokens |
| **Tool Gateway as Permission Source** | All tool calls pass through the policy gateway before execution |

---

## Testing

| Metric | Value |
| --- | --- |
| **Total Tests** | 802 |
| **Pass Rate** | 100% (802/802) |
| **External Dependencies** | None (no real DB or OpenAI calls in tests) |
| **Test Framework** | pytest 8.2.2 + pytest-mock 3.14.0 |

```bash
# Run the full test suite
.venv/bin/python -m pytest tests/ -v --tb=short
```

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

### What is not yet production-like

- **Testcontainers / real PostgreSQL isolation suite** — not yet integrated; tests use mocked connection pools
- **Live payment processor** — billing model and webhook path exist; no live processor integration proven
- **Distributed rate limiting** — per-process Flask-Limiter only; multi-worker distributed limiter not proven
- **iPhone / App Store binary** — no iOS client exists

### CI Pipeline

GitHub Actions CI runs on every push to `main` and every PR:

1. **Dependency install** — `pip install -r requirements.txt`
2. **Secret scan** — scans tracked files for API keys
3. **Full test suite** — `pytest tests/ -v --tb=short`
4. **Import smoke check** — verifies all modules import cleanly
5. **Migration validation** — all migration files parse as valid Python

---

## Roadmap

> Future only — owner may add or revise later. Not frozen.

| Stage | Target |
| --- | --- |
| **iPhone / App Store client** | Native iOS companion app |
| **Richer billing provider** | Full live payment processor integration |
| **Distributed rate limiting** | Across multiple workers |
| **Cognitive Memory Graph** | Temporal, provenance-aware knowledge graph connecting person, preference, project, task, conversation, decision, document, code, and outcome |
| **Decision & Simulation Lab** | Structured what-if scenario modeling before consequential actions |
| **Portable Personal AI Runtime** | Hybrid cloud/local execution with encrypted local storage and explicit policy controlling what data may leave the device |
| **Production Integration Test Suite** | Testcontainers PostgreSQL integration tests for real DB, migration upgrade/downgrade, concurrent quota, pool behavior, multi-worker, and tenant isolation |

---

## Author

<div align="center">

[![Engineer portrait](docs/assets/bob-agent-portrait.svg)](docs/assets/bob-agent-portrait.svg)

</div>

### AMIN AZIMI
### AI ARCHITECT
### End-to-End Systems Development
### Azimi Innovation Lab

Personal AI Assistant is a personal laboratory for AI Product Architecture and Evidence-Based AI — a production-grade SaaS system built on evidence over claim, isolation over demo, and verification over a green HTTP status. The work spans end-to-end Systems Development: security-hardened authentication, multi-tenant isolation, retrieval-grounded AI, durable agentic execution, permissioned tool access, and honest technical communication. Azimi Innovation Lab is the author's personal workspace — not an external company. AI Product Architecture · Evidence-Based AI · Production AI Systems.

---

## Footer

| Link | URL |
| --- | --- |
| **Live Application** | https://personal-ai-assistent.onrender.com |
| **GitHub Repository** | https://github.com/aminazimi42-coder/Personal-ai-assistent |
| **License** | Apache 2.0 — see [LICENSE](LICENSE) |

<div align="center">

© Amin Azimi — Apache 2.0

</div>
