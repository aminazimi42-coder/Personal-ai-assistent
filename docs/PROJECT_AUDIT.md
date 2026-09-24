# Personal AI Assistant — Full Read-Only Project Audit

**Date:** 2026-09-24  
**Auditor:** Hermes Agent  
**Mode:** Read-only (no app code modified)

---

## 1. SHA and Test Count (This Machine)

| Field | Value |
| --- | --- |
| Branch | `main` |
| HEAD SHA | `331b3bc` (matches expected directive tip) |
| Test result | **838 passed in 10.44s** (`.venv/bin/python -m pytest tests/ -q --tb=no`) |
| Python | 3.11.15 (`.venv/`) |
| Flask | 3.0.3 |

**Note:** README.md claims 802 tests in three places (badges + table + Journey Frame). Actual count is **838**. README is stale by 36 tests (M2 hotfix + login patch added tests). This is a documentation defect, not a code defect — the directive says do not rewrite README now.

---

## 2. What the System Is / Is Not

### What It Is
- **Flask 3.0.3** monolith deployed on **Render** (Gunicorn, `render.yaml`, Procfile).
- **PostgreSQL** via **psycopg2** connection pool (`db/pool.py`), with **Flask-SQLAlchemy/Flask-Migrate** for Alembic schema management only — runtime queries use raw SQL cursors.
- **15 ORM models** in `db/models.py`; **10 migrations** (001–010), linear chain.
- **Bearer-token auth**: raw token generated via `secrets.token_urlsafe(48)`, stored only as **SHA-256 hash** (`auth_token_hash`), 24h expiry, revocable via logout (NULLs hash + expiry).
- **Rate limiting** via Flask-Limiter (login=10/min, AI=20/min, general=60/min).
- **Quota enforcement** on all AI cost routes (`/ai`, `/ai-to-task`, `/smart-ai`, `/transcribe-voice`, `/voice-to-task`, `/api/v1/ai-evaluation`). Entitlement gate (403) before quota (429). Fail-closed in production.
- **API v1** surface with generated OpenAPI 3.0 spec at `/api/v1/openapi.json`.
- **File uploads** (`/api/v1/files`) with MIME allowlist, size cap, user-scoped storage.
- **Privacy endpoints** (GDPR export/delete).
- **Voice**: browser MediaRecorder → `/transcribe-voice` → OpenAI Whisper. iOS MIME types (`audio/mp4`, `video/mp4`) in allowlist.

### What It Is Not
- **Not a native iOS app** — web-only, PWA meta tags present but no Swift/StoreKit project.
- **Not a multi-tenant production SaaS** at runtime — Tenant/Workspace boundary is documented but `workspace` table has no `tenant_id` column. No live payment processor; billing webhooks are idempotent but no real Stripe key or processor is wired.
- **Not a cookie-session app** — all auth is bearer-token-based (correct for future mobile).
- **Not frozen** — active development, M2 hotfix + login patch recently shipped.

---

## 3. P0 Defects (Block Personal Use)

### P0-1: Session token lost on iPhone → Tasks return HTTP 401

**Root cause:** See §6 below for full analysis. The login flow is functionally correct server-side, but the client-side `login()` function sends `identifier` as the value of `nameInput` (the "Name / Username" field). On iPhone Safari, the `nameInput` element may be populated by browser autofill in a way the user doesn't expect, or the user may fill only the email field. The client-side validation logic (`identifier.includes("@") || identifier.length >= 2`) can pass with an empty `nameInput` if `emailInput` has a valid email — but the server query `WHERE email = %s OR name = %s` will fail if the email doesn't match the `name` column and the name doesn't match the `email` column.

**However**, the deeper P0 issue is: after login succeeds and a token is stored in `localStorage`, the token can expire (24h) or be invalidated, but the client has **no proactive token validation on page load**. The page calls `loadTasks()`, `loadAppointments()`, `loadReminders()` on every load (lines 2108–2113) — if the token is expired/invalid, every API call returns 401 simultaneously, `authorizedFetch` clears the token and shows the login panel, but the user perceives "I was logged in but Tasks returned 401."

**Impact:** User cannot maintain a usable session across iPhone Safari sessions. Token expiry or Safari ITP (Intelligent Tracking Prevention) clearing localStorage on inactivity makes the app appear broken.

**Files involved:** `static/js/app.js` (lines 131–155, 242–271, 2104–2113), `routes/user_routes.py` (login route)

### P0-2: Voice recording → transcription fails silently or with generic error

**Root cause:** `sendAudioToServer` posts `FormData` with `formData.append("audio", audioBlob, "voice.webm")`. The filename is always `voice.webm` regardless of the actual MIME type. On iOS Safari, `MediaRecorder` may produce `audio/mp4` or `video/mp4` blobs, but the filename stays `voice.webm`. The server-side `/transcribe-voice` route checks `content_type` against `ALLOWED_AUDIO_MIME_TYPES` (which includes `video/mp4`) — so MIME passes — but the file extension `voice.webm` may confuse the Whisper API when the actual codec is AAC/MP4.

**Additionally**, if `_ai_provider_configured()` returns False (empty `OPENAI_API_KEY` on Render), the route returns 503 "AI provider not configured" — but only **after** quota is consumed. The user sees the error but loses a quota unit.

**Impact:** Voice input is unusable — records but never becomes text.

**Files involved:** `static/js/app.js` (lines 1184–1185, 1172–1236), `routes/ai_routes.py` (lines 247–345)

---

## 4. P1 Defects (Product / UX)

### P1-1: Home "About" section is a stale key-value block, not the brand panel
The Home tab's About card (`templates/index.html` lines 96–103) shows `App Name / Version / Author / Description` as static key-value pairs. The Account tab has the intended Author panel (`templates/index.html` lines 272–293) with portrait, "AMIN AZIMI / AI Architect / Azimi Innovation Lab" branding. The Home About should either be replaced with the brand panel or removed — the directive explicitly states Home About is "still the old key-value block" and Account Author is "the intended brand."

### P1-2: Author panel bio has stale test count (802, not 838)
`templates/index.html` line 286: `"802 tests pass"` — should be 838. Minor but visible to the user.

### P1-3: OpenAPI Subscription schema enum missing `pro_plus`
`routes/api_v1.py` lines 144 and 163: `Subscription` and `SubscriptionCreate` schemas have `enum: ["free", "pro"]` — missing `pro_plus`. The `AccountQuota` schema (line 231) correctly includes `pro_plus`. API consumers reading the OpenAPI spec will see an incomplete plan list.

### P1-4: SVG file names still contain "bob" prefix
`docs/assets/bob-agent-portrait.svg` and `docs/assets/bob-engineering-agent.svg` — filenames contain "bob" (a coding-agent name). SVG `<title>` elements were already fixed to say "Personal AI Assistant — engineer portrait" / "engineering workflow", but the **file paths** still contain "bob". README line 404 references `bob-agent-portrait.svg` by path.

### P1-5: Send button disabled until auth — but no visual feedback on AI tab
`sendButton` starts `disabled` (line 202). `updateSendButtonState()` (line 187) sets it based on `getAuthToken()`. If a user opens the AI tab before logging in, the button is disabled with a small error message — but there is no clear "Log in first" call-to-action visible on the AI tab itself.

### P1-6: No proactive session check on page load
`updateLoggedInUiState()` only checks `!!getAuthToken()` — it does not validate the token against the server. A token in localStorage that has expired (24h) or been revoked still appears as "Logged in" until the first API call returns 401. This causes the P0-1 cascade.

---

## 5. P2 Later

| ID | Description |
| --- | --- |
| P2-1 | `_db_available` in `usage_service.py` is a module-level cached boolean (line 38). Once set, it never resets within a worker's lifetime. If the DB becomes available after initial failure, the worker keeps using in-memory until restart. Acceptable for Render (single deploy = fresh workers), but fragile. |
| P2-2 | `SECRET_KEY` defaults to `"dev-insecure-change-in-production"` (settings.py line 70). If not set in production env, Flask uses a predictable secret. Should be `_require("SECRET_KEY")` in production. |
| P2-3 | `_cors_raw` allows empty `CORS_ALLOWED_ORIGINS` in production (settings.py line 82) — same-origin only, which is correct for a same-origin SPA, but should be documented. |
| P2-4 | `loadAppInfo()` fetches `/app-info` on every page load (line 2111) — unauthenticated, no cache. Trivial but unnecessary network round-trip. |
| P2-5 | `findCustomCurrency()` uses raw `fetch()` (line 1435) instead of `authorizedFetch` — not auth-gated, but also not using the timeout helper. |
| P2-6 | No CSP (Content-Security-Policy) header. Security headers present (nosniff, DENY, Referrer-Policy) but no CSP. |

---

## 6. Root Cause Analysis: Login UI Success vs Tasks 401

### The Symptom
After login on iPhone, the UI shows "Logged in" and the quota panel appears. But when the Tasks tab loads, every API call returns HTTP 401. The user believes they are logged in but the app is broken.

### The Mechanism

1. **Login succeeds server-side** (`/login` returns 200 with `user.token`). The raw token is stored in `localStorage` via `setAuthToken()` (app.js line 1629).

2. **`updateLoggedInUiState()` runs** (line 1631) — checks `!!getAuthToken()` → True → hides login panel, shows quota panel, sets status "Logged in". Send button enabled.

3. **`loadTasks()`, `loadAppointments()`, `loadReminders()` fire immediately** (lines 1633–1635). Each calls `authorizedFetch("/tasks")` which attaches `Authorization: Bearer <token>`.

4. **Server-side `get_current_user()`** (`auth_service.py` line 116) extracts the bearer token, hashes it, and queries:
   ```sql
   SELECT id, name, email, created_at, token_expires_at
   FROM users WHERE auth_token_hash = %s
     AND (token_expires_at IS NULL OR token_expires_at > %s)
   ```

5. **If this returns no rows** → 401 "Invalid or expired token" → `authorizedFetch` (app.js line 251) catches the 401, clears the token, calls `showLoginPanelForAuth()`, and shows the login panel again.

### Why the token can be invalid despite a fresh login

**Scenario A — Safari ITP / Private Browsing:** iPhone Safari may clear `localStorage` between sessions or in private mode. The token stored during login is gone on next visit. But `updateLoggedInUiState()` runs before any API call — if `localStorage.getItem` returns `null`, the UI correctly shows "Not logged in." This is not the P0 path.

**Scenario B — Token expiry (24h):** If the user logged in > 24h ago but didn't log out, the token is in `localStorage` but expired on the server. `get_current_user` returns 401. `authorizedFetch` clears the token and shows the login panel. The user sees "Session expired (HTTP 401) — please log in again." This is correct behavior, but the user perceives it as "I was logged in but Tasks returned 401."

**Scenario C — Multiple device login invalidation:** If the user logs in on a second device, the server generates a **new** token hash and overwrites `auth_token_hash` in the `users` table (user_routes.py lines 140–145). The **first device's token is now invalid** — its hash no longer matches any row. Every API call from the first device returns 401. The user sees the login panel but believes they were still logged in.

**Scenario D — Render redeploy / DB connection drop:** If the DB pool fails after the page loads, `get_current_user` catches the exception and returns 401 (the `except` in the cursor lookup bubbles up). But the real failure is a DB connectivity issue, not an auth failure — the user sees 401 instead of 503.

### Most Likely Root Cause (Given Field Facts)

The field facts state "iPhone still failed to keep a usable session" after `331b3bc`. The login flow itself is correct — the server properly returns a token and the client stores it. The most probable cause is **Scenario C (single active session)** combined with **no proactive token validation on page load**:

- The user logs in on iPhone → token stored.
- Later, the user (or a previous browser tab, or a re-login) causes the server to issue a **new** token, overwriting the hash.
- The iPhone's localStorage still has the **old** token.
- `loadTasks()` fires on page load → 401 → `authorizedFetch` clears the token and shows the login panel.
- The user sees the login panel and thinks "I was logged in but Tasks returned 401."

**The fix:** Either (a) support multiple active tokens per user (a `user_tokens` table with one-to-many), or (b) add a lightweight `/me` or `/validate-session` call on page load that proactively checks the token before firing data loads — if invalid, show the login panel immediately rather than letting every data call fail with 401.

---

## 7. Ordered Repair List (≤ 8 items, for the NEXT directive)

| # | File(s) | Repair (one sentence) |
| --- | --- | --- |
| 1 | `static/js/app.js` | Add a `validateSession()` call on page load that hits `/me` before data loads; if 401, clear token and show login panel immediately instead of letting every API call cascade-fail. |
| 2 | `routes/user_routes.py` | Support multiple active sessions: either add a `user_tokens` table (one-to-many) or return the existing token hash on re-login instead of overwriting it, so a second device login doesn't invalidate the first. |
| 3 | `static/js/app.js` (line 1185) | Set the uploaded filename extension to match the actual MIME type (use `voice.mp4` when `lastRecordedAudioMimeType` contains `mp4`), so Whisper receives a correctly-named file on iOS. |
| 4 | `routes/ai_routes.py` (lines 264, 363) | Move `check_and_increment` **after** `_ai_provider_configured()` check so a 503 (no API key) does not consume a quota unit. |
| 5 | `templates/index.html` (lines 96–103) | Replace the Home About key-value block with the brand panel (or link to the Account Author panel) to match the intended Amin Azimi / AI Architect / Azimi Innovation Lab branding. |
| 6 | `templates/index.html` (line 286) | Update the author bio test count from 802 to 838 (or make it dynamic from `/app-info`). |
| 7 | `routes/api_v1.py` (lines 144, 163) | Add `pro_plus` to the `Subscription` and `SubscriptionCreate` schema enums so the OpenAPI spec matches the DB CHECK constraint and `AccountQuota` schema. |
| 8 | `docs/assets/`, `README.md` (line 404) | Rename `bob-agent-portrait.svg` → `engineer-portrait.svg` (and `bob-engineering-agent.svg` → `engineering-workflow.svg`), update the README reference, to remove the coding-agent name from file paths. |

---

## 8. Owner Field Checks (After the Next Directive)

- Log in on iPhone Safari, close the tab, wait 30 minutes, reopen — session should still be valid (token not cleared by ITP).
- Log in on a second device — the first device should still work (or both should work if multi-token is implemented).
- Record voice on iPhone → transcript should appear in the message box.
- Check `/api/v1/openapi.json` — `Subscription` schema should list `["free", "pro", "pro_plus"]`.
- Home tab About section should show the Amin Azimi brand panel, not the old key-value block.

---

## 9. Explicit "Do Not Do Yet" List

- **Do NOT start M3** (no M3 directive exists; this audit feeds the next directive only).
- **Do NOT create an iOS / App Store project** (no Swift, no StoreKit, no screenshots).
- **Do NOT add payment keys** (no real Stripe API key, no live payment processor).
- **Do NOT rewrite README.md** (stale test count is a doc defect; the directive says do not rewrite now).
- **Do NOT commit `PROJECT_DIRECTIVE.txt`** (owner file — leave uncommitted).
- **Do NOT force-push, rebase, or amend** prior commits.
- **Do NOT modify application code in this run** (this audit is read-only; `docs/PROJECT_AUDIT.md` is the only file created).
