# Changelog

All notable changes to the Personal AI Assistant project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] — 2026-09-22

### Evolution — Production-Grade SaaS

Post-freeze evolution directive. The project is unfrozen for active maintenance
and production-grade SaaS capabilities. v1.0.0 remains immutable history.

### Security Hardening

- Removed legacy raw `auth_token` compatibility — only SHA-256 hashed tokens stored/accepted
- Fixed quota bypass on `/ai-to-task` and `/transcribe-voice` routes
- Added MIME content-type validation for voice uploads
- Added filename sanitization to prevent path traversal
- Added prompt-injection defense: query sanitization, control-character stripping, length bounds
- Migration `005_remove_legacy_auth_token` drops the raw token column

### LLM Provider Abstraction

- `services/llm_provider.py`: abstract `LLMProvider` boundary with `OpenAIProvider` adapter
- Provider registry, timeout, bounded retries, normalized `LLMError` exceptions
- Cost metadata (model, input/output tokens, estimated cost) returned with each call
- `ai_service.py` refactored to use the provider abstraction

### Multi-Tenant SaaS + Billing

- `services/tenant_service.py`: tenants, memberships, roles (owner/admin/member)
- `services/billing_service.py`: plan model (free/pro), subscription lifecycle, idempotent webhooks
- `routes/api_v1.py`: versioned `/api/v1/` API with generated OpenAPI spec
- Migration `006_add_tenant_billing`: tenants, tenant_memberships, subscriptions, billing_events

### Durable Agent Execution

- `agent_runs` table with state machine (PENDING → APPROVED → EXECUTING → COMPLETED/FAILED/DENIED/CANCELED)
- Idempotency via unique `action_id`, cancellation, retry, approval gates
- `routes/agent_routes.py`: execute, approve, cancel, retry, list, get
- Migration `007_add_agent_runs`

### Context Compiler

- `services/context_compiler.py`: compiles inspectable context from memories, code, tasks, projects
- Records source, relevance, provenance, token budget, compression decisions
- Selection explanation: why context was selected

### Automation + Background Jobs + Voice-to-Task

- `services/background_jobs.py`: job queue with enqueue, process, status, idempotency, retries
- `services/voice_to_task.py`: voice → transcription → task extraction → user confirmation
- `services/automation.py` refactored to DB-backed with pause/resume
- Migrations `008_add_workspaces`, `009_automation_jobs_voice_to_task`

### AI Evaluation + MCP-Compatible Tools

- `services/ai_evaluation.py`: 12 scenario families (task extraction, language understanding, retrieval relevance, context sufficiency, prompt-injection resistance, user isolation, token budget, cost controls, agent safety, tool permissions, verification correctness, voice-to-task)
- `services/mcp_tools.py`: MCP-compatible schemas routing through tool gateway — MCP cannot bypass
- `routes/evaluation_routes.py`: AI evaluation and MCP tool endpoints

### Privacy Operations + Cost Intelligence + Control Center

- `services/privacy.py`: user data export, account deletion, safe logging, AI data boundary
- `services/cost_intelligence.py`: monthly usage, workspace budgets, cost dashboard, cache stats
- `services/control_center.py`: tenant, billing, agent, automation, tool audit metrics
- `routes/privacy_routes.py`, `routes/control_center_routes.py`

### Durable Workspace System

- `services/workspace.py` refactored to DB-backed with in-memory fallback for tests
- `routes/workspace_routes.py`: workspace and project CRUD API routes
- Migration `008_add_workspaces`

### Cinematic README

- Rebuilt README using AILORA-inspired cinematic documentation/visual language
- Hero, connected-systems, status-ribbon, evidence-constellation, control-center SVGs
- Bob engineering-agent portrait in Author section
- 27-section structure per directive specification

### Test Count

- 384 → 743 tests (359 new tests across 15+ new test modules)

## [1.0.0] — 2026-09-22

### Final Release — Development Freeze

This is the first stable release of Personal AI Assistant. All 20 development
phases are complete, tested, and deployed. The project enters development freeze
after this release.

### Added — Core Platform

- Flask 3.0.3 application factory architecture with PostgreSQL persistence
- User authentication: signup, login, logout, bearer-token sessions
- bcrypt password hashing (cost factor 12), SHA-256 token hashing
- Anti-enumeration login (same error for bad email / bad password)
- Token expiry enforcement and immediate revocation on logout
- Task CRUD: create, read, update, delete with user isolation
- Appointment CRUD: create, read, update, delete with user isolation
- Reminder aggregation: tasks and appointments due within 1 hour
- Exchange-rate integration via Frankfurter API (USD base)
- Voice transcription via OpenAI Whisper
- Conversational AI chat via GPT-4o-mini
- Smart AI: single-LLM-call decision between reply and task creation
- AI-to-task: natural-language task extraction

### Added — Security Hardening

- Flask-Limiter rate limiting (3 tiers: login, AI, general)
- Per-user AI rate limiting via token-to-user-id resolution
- Restrictive CORS (configured origins only, no wildcards)
- Security headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy
- Global JSON error handlers (never expose raw exceptions or stack traces)
- Parameterized SQL throughout (no string interpolation in queries)
- Voice upload size limits (configurable, default 10 MB) and MIME validation
- AI input length limits (configurable, default 4000 chars)
- AI output token limits on all OpenAI calls
- Per-user daily AI quota with atomic DB UPSERT (multi-worker safe)
- Fail-closed quota in production (denies when DB unavailable)
- Request ID tracking and structured latency logging
- AI operation metadata logging (model, tokens, duration — no prompt content)

### Added — Reliability

- psycopg2 ThreadedConnectionPool with configurable min/max connections
- External API retry with exponential backoff (max 3 retries, 0.5s base)
- External API timeout enforcement (default 10s)
- URL redaction in logs (no query params exposed)
- Browser-side fetchWithTimeout using AbortController (geocoding + weather)
- Graceful degradation: safe fallbacks on external API failure
- Health endpoint (`GET /health`) and readiness probe (`GET /ready`)
- Gunicorn production configuration (workers, threads, timeouts, security limits)
- Render Infrastructure as Code (`render.yaml`)

### Added — Code Retrieval Engine

- AST-based Python symbol extraction (functions, classes, methods, modules)
- Hybrid search: keyword matching + symbol-name matching with type weighting
- Context compression with deduplication and token-budget truncation
- Token counting via tiktoken (heuristic fallback if unavailable)
- Query sanitization (prompt-injection-aware)
- Retrieval latency measurement
- Repository ingestion with file-count limits and large-file skip
- Token-savings reporting

### Added — Memory Engine

- 4-layer memory: short_term, task, preference, project
- User-isolated: strict per-user separation, no cross-user leakage
- DB-backed with in-memory fallback for tests/dev
- Short-term TTL expiry (24h)
- Keyword search with relevance scoring
- CRUD: set, get, search, delete, list, clear
- Conflicting memory handling (update-in-place by type+key)

### Added — Agentic Execution

- Pipeline: PLAN → RETRIEVE → ANALYZE → PROPOSE → APPROVAL → EXECUTE → VERIFY → REPORT
- Action registry with type classification (read_only, write, destructive, communication)
- Approval gates for destructive actions
- Idempotency via action_id
- Structured error states (no silent failures)
- Audit logging for every action

### Added — Tool Gateway

- Centralized tool access with policy enforcement
- Least-privilege tool registration
- 4 policy categories: read_only, write, destructive, communication
- Approval required for destructive and communication tools
- Unregistered tools denied by default
- Per-call audit logging
- Tool call result tracking with duration

### Added — Cost & Token Intelligence

- Model routing by task complexity (simple → gpt-4o-mini, complex → gpt-4o)
- Token budget computation (context budget minus output reservation)
- Response caching with TTL for identical prompts
- Cost estimation per model (input/output token pricing)
- Monthly cost tracking per user

### Added — Project Workspace

- User-owned workspaces with strict isolation
- Workspace → Projects hierarchy
- Create, list, get, delete operations
- Cascading deletion (deleting workspace deletes its projects)
- User-scoped access on every operation

### Added — Unified Knowledge Retrieval

- Typed sources: code, document, memory, task, note, project
- Source attribution and relevance ranking
- Token-budgeted context assembly
- Latency measurement
- Builds on existing code_retrieval and memory_engine (no duplicate systems)

### Added — Verification Engine

- Structured verification: PENDING → VERIFIED / PARTIAL / FAILED / UNVERIFIED
- File existence and content verification
- Callable execution verification
- DB row existence verification
- No-fabricated-success guard: verified status requires evidence + passed checks

### Added — Automation

- Trigger types: daily, hourly, event, manual
- Idempotency via unique automation IDs
- Daily execution limits (configurable, default 10)
- Execution logging with status and error tracking
- User-scoped automations with ownership checks
- Enable/disable toggles

### Added — Privacy

- Data classification: public, internal, confidential, restricted
- 7 data categories with per-category policies
- Retention policies per category (1–365 days)
- AI training eligibility (all categories: not eligible)
- User-deletable flags per category
- Audit logging for data access events
- Value anonymization for safe logging
- `is_local_processing_available()` — always returns False (honest, not implemented)

### Added — Control Center

- Real dashboard metrics aggregation from live service state
- AI usage, quota, cost, token, retrieval-savings metrics
- Memory count by type
- Workspace and project counts
- Task count by status
- Automation count and recent executions
- Rate limit configuration and CORS origin count
- Audit event feed
- Health summary with real configuration values

### Added — Testing & CI

- 384 tests across 27 test modules
- Full regression suite (no real DB or OpenAI calls)
- Security hardening tests (27 tests)
- Migration safety tests (13 tests: chain, syntax, additive upgrade, FK)
- API integration tests (25 tests)
- User isolation tests
- Agentic execution, tool gateway, cost intelligence tests
- Memory engine, workspace, knowledge retrieval tests
- Verification engine, automation, privacy tests
- Control center, production deployment, final regression tests
- GitHub Actions CI pipeline (test, secret scan, import smoke, migration parse)

### Added — Documentation

- Apache License 2.0
- README with capability matrix, architecture diagrams, security model
- HANDOFF documentation with module map, configuration, deployment
- `.env.example` with all environment variables
- API reference documentation

### Infrastructure

- Python 3.11.9 runtime
- Flask 3.0.3, Flask-Migrate 4.0.7, Flask-SQLAlchemy 3.1.1, Flask-Limiter 3.5.1
- psycopg2-binary 2.9.9, openai 1.30.1, bcrypt 4.1.2, requests 2.31.0
- Gunicorn 21.2.0, Render deployment
- 4 database migrations (initial schema, upgrade, usage events, memories)
