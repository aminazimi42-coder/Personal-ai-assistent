<div align="center">

<img src="docs/personal-ai-assistant-hero.png" alt="Personal AI Assistant — intelligent productivity platform" width="100%" />

# 🧠 Personal AI Assistant

### An AI-assisted productivity workspace for tasks, appointments, reminders, voice interaction, and real-time daily context.

[![Live App](https://img.shields.io/badge/🌐_Live_App-Open-00C7B7?style=for-the-badge)](https://personal-ai-assistent.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.11.9-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-111827?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Ready-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-Integration-412991?style=for-the-badge&logo=openai&logoColor=white)](https://platform.openai.com/)
[![Render](https://img.shields.io/badge/Render-Deployed-46E3B7?style=for-the-badge&logo=render&logoColor=111827)](https://render.com/)

**Deployed Advanced MVP · Responsive Web Application · REST API · AI Workflow**

[🌐 Live Demo](https://personal-ai-assistent.onrender.com) ·
[✨ Features](#-product-capabilities) ·
[🏗️ Architecture](#️-architecture) ·
[🚀 Quick Start](#-quick-start) ·
[🗺️ Roadmap](#️-roadmap)

</div>

---

## 🌟 Product Vision

> **Reduce daily cognitive load by bringing planning, contextual information, reminders, and AI-assisted actions into one focused workspace.**

Personal AI Assistant is a mobile-friendly productivity application built as a deployed, full-stack MVP. It combines structured task and appointment workflows with browser capabilities, live contextual data, authentication, and an AI command layer.

The project demonstrates product thinking across the complete delivery path: frontend interaction design, Flask API architecture, PostgreSQL persistence, external-service integration, browser APIs, authentication, and cloud deployment.

---

## 🚦 Current Release

| 🧭 Area | 📊 Status | 📝 Current scope |
|---|---|---|
| 🏠 Home dashboard | ✅ Operational | Time-aware greeting, date and time, weather, live location, exchange-rate summary, and application information |
| 📍 Live location | ✅ Operational | Browser permission flow, coordinates, and resolved location context |
| 🌦️ Weather | ✅ Operational | Location-aware weather information in the Home workspace |
| 💱 Exchange rates | 🟡 Demonstration scope | A deliberately limited set of currencies is connected for demonstration; additional visible options are placeholders |
| 🔐 User accounts | ✅ Implemented | Signup, login, logout, hashed passwords, and bearer-token access |
| 🎙️ Voice capture | 🟡 Partially operational | Recording and playback work; the complete voice-to-AI response path is not currently reliable |
| ✅ Task management | 🟡 Incomplete in current deployment | CRUD foundations and UI are implemented; end-to-end behavior is not considered release-complete |
| 🤖 AI assistant | 🟡 Incomplete in current deployment | The workflow previously produced AI replies and AI-created tasks; final submission currently encounters backend/database connectivity errors |
| 👤 Account view | ✅ Operational | Application name, version, author, and product description |

> [!IMPORTANT]
> This repository represents a **deployed advanced MVP / functional prototype**. It is intentionally documented without claiming production, enterprise, or end-to-end readiness for incomplete flows.

---

## ✨ Product Capabilities

### 🏠 Context-aware Home

- 🕒 Live clock, date, and time-sensitive welcome message
- 🌦️ Weather details based on the user’s loaded location
- 📍 Browser-powered live geolocation with permission handling
- 💱 USD-based exchange-rate information for supported demonstration currencies
- 🔎 Custom supported-currency lookup
- ℹ️ Runtime application metadata
- 🎭 Interactive ALINA companion/avatar presentation

### 📋 Productivity Workspace

- ✅ Create, retrieve, update, complete, and delete task foundations
- 🎯 Task priority, description, status, and optional due date
- 📅 Appointment creation and lifecycle foundations
- ⏰ Reminder aggregation for tasks and appointments
- 🔔 Browser notification and reminder-sound foundations
- 👤 User-scoped records through authenticated API access

### 🤖 AI & Voice Experience

- 🎙️ Browser microphone recording controls
- ▶️ Recorded-audio playback
- 💬 Text command input
- 🧠 AI intent flow designed to choose between a direct reply and task creation
- 📆 Optional due-date and due-time enrichment
- ⚠️ Transparent documentation of the currently interrupted end-to-end AI response stage

### 🔐 Identity & Access

- 🧾 User registration
- 🔑 Login and logout flows
- 🛡️ Password hashing with `bcrypt`
- 🎟️ Bearer-token authentication
- 🗂️ User-isolated task and appointment queries

---

## 🧭 Application Experience

| 🧩 Navigation | 🎯 Purpose |
|---|---|
| 🏠 **Home** | Daily context, ALINA interaction, weather, location, currency data, and product information |
| ✅ **Tasks** | Task, appointment, and reminder workflows |
| 🤖 **AI** | Voice capture, text input, AI reply, and AI-to-task experience |
| 👤 **Account** | Authentication controls and application metadata |

The interface is implemented as a responsive single-page experience using server-rendered HTML plus modular CSS and browser-side JavaScript.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    U["👤 User / Mobile Browser"] --> UI["🎨 Responsive Web UI"]
    UI --> API["⚡ Flask REST API"]
    API --> AUTH["🔐 Authentication"]
    API --> CORE["📋 Tasks · Appointments · Reminders"]
    API --> AI["🧠 OpenAI Workflow"]
    API --> EXT["🌍 Context APIs"]
    AUTH --> DB[("🐘 PostgreSQL")]
    CORE --> DB
    AI --> DB
    EXT --> WX["🌦️ Weather / Location"]
    EXT --> FX["💱 Frankfurter Rates"]
```

### 🧱 Architectural Layers

| 🧩 Layer | 🛠️ Responsibility |
|---|---|
| 🎨 `templates/` + `static/` | Responsive UI, navigation, voice controls, browser integrations, and API consumption |
| 🛣️ `routes/` | HTTP endpoints, request validation, authentication checks, and response orchestration |
| ⚙️ `services/` | Domain payload construction, parsing, serialization, AI logic, and user operations |
| 🐘 PostgreSQL | Persistent users, tasks, and appointments |
| 🚀 Gunicorn + Render | Production-style WSGI serving and cloud deployment |

---

## 🛠️ Technology Stack

| 🧭 Category | ⚙️ Technology | 🎯 Role |
|---|---|---|
| 🐍 Runtime | Python `3.11.9` | Application runtime |
| ⚡ Backend | Flask `3.0.3` | HTTP routing, rendering, and REST API |
| 🦄 Server | Gunicorn `21.2.0` | WSGI application server |
| 🐘 Database | PostgreSQL | Persistent relational storage |
| 🔌 DB driver | psycopg2-binary `2.9.9` | PostgreSQL connectivity |
| 🧠 AI | OpenAI Python SDK `1.30.1` | AI response and intent workflow |
| 🔐 Security | bcrypt `4.1.2` | Password hashing |
| 🌐 HTTP | Requests `2.31.0` + HTTPX `0.27.2` | External API communication |
| 🎨 Frontend | HTML5 · CSS3 · Vanilla JavaScript | Responsive application experience |
| 📍 Browser APIs | Geolocation · MediaRecorder · Notifications | Location, voice, and reminder capabilities |
| 💱 External data | Frankfurter API | Demonstration exchange rates |
| ☁️ Deployment | Render | Hosted web service |

---

## 🔌 API Surface

### 🩺 Platform

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Serve the application |
| `GET` | `/health` | Lightweight service health response |
| `GET` | `/app-info` | Return version and author metadata |
| `GET` | `/db-check` | Check database connectivity |
| `POST` | `/init-db` | Initialize application tables |
| `GET` | `/exchange-rates` | Return supported demonstration rates |

### 👤 Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/signup` | Create a user account |
| `POST` | `/login` | Authenticate and return an access token |
| `POST` | `/logout` | End the active token session |

### ✅ Tasks & Scheduling

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/tasks` | List authenticated user tasks |
| `POST` | `/tasks` | Create a task |
| `PUT` | `/tasks/{task_id}` | Update a task |
| `DELETE` | `/tasks/{task_id}` | Delete a task |
| `GET` | `/appointments` | List authenticated user appointments |
| `POST` | `/appointments` | Create an appointment |
| `PUT` | `/appointments/{appointment_id}` | Update an appointment |
| `DELETE` | `/appointments/{appointment_id}` | Delete an appointment |
| `GET` | `/reminders` | Aggregate due tasks and appointments |

### 🤖 AI Commands

The backend includes AI reply, quick-add, AI-to-task, and smart intent routes, including browser-friendly variants. These endpoints are part of the active development surface and should be treated as partially operational in the current deployment.

---

## 📁 Project Structure

```text
Personal-ai-assistent/
├── main.py                   # Flask application entry point
├── requirements.txt          # Python dependencies
├── runtime.txt               # Runtime declaration
├── .python-version           # Python version pin
├── routes/
│   ├── ai_routes.py          # AI and intent endpoints
│   ├── calendar_routes.py    # Appointment API
│   ├── reminder_routes.py    # Reminder aggregation
│   ├── task_routes.py        # Task API
│   └── user_routes.py        # Authentication API
├── services/
│   ├── ai_service.py         # AI-domain logic
│   ├── calendar_service.py   # Appointment parsing and serialization
│   ├── task_service.py       # Task parsing and serialization
│   └── user_service.py       # User persistence and authentication
├── templates/
│   └── index.html            # Application shell
└── static/
    ├── css/style.css         # Responsive visual system
    ├── js/app.js             # Client-side application logic
    └── ...                   # Application imagery and icons
```

---

## 🚀 Quick Start

### 1️⃣ Clone the repository

```bash
git clone https://github.com/aminazimi42-coder/Personal-ai-assistent.git
cd Personal-ai-assistent
```

### 2️⃣ Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

> 🪟 On Windows, activate with `.venv\Scripts\activate`.

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Configure environment variables

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
export OPENAI_API_KEY="your-openai-api-key"
```

> 🔒 Never commit production credentials or local `.env` files.

### 5️⃣ Start the application

```bash
gunicorn main:app
```

Open:

```text
http://127.0.0.1:8000
```

### 6️⃣ Confirm service health

```text
http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

---

## ☁️ Deployment

The current application is deployed as a Render web service.

| ⚙️ Setting | 📌 Value |
|---|---|
| 🐍 Runtime | Python `3.11.9` |
| 📦 Build command | `pip install -r requirements.txt` |
| 🚀 Start command | `gunicorn main:app` |
| 🐘 Required database variable | `DATABASE_URL` |
| 🧠 Required AI variable | `OPENAI_API_KEY` |

🌐 Live application:

```text
https://personal-ai-assistent.onrender.com
```

> [!NOTE]
> Free-tier cloud instances may require a short warm-up period after inactivity.

---

## ⚠️ Known Limitations

### 🤖 AI Assistant & Voice Workflow

- 🎙️ Voice recording and playback remain available.
- 🧠 The workflow previously supported speech-to-text followed by an AI-generated reply or AI-created task.
- ⚠️ In the current deployment, final message submission and response generation encounter a backend/database connectivity error.
- 🛠️ The complete AI interaction is therefore classified as **partially implemented**, not currently end-to-end operational.

### ✅ Task Management

- 🧱 The authenticated API, database schema, CRUD logic, and interface components are implemented.
- ⚠️ The complete user workflow is not considered release-complete in the current deployment.
- 🛠️ Task management remains inside the active stabilization scope.

### 💱 Exchange-rate Scope

- ✅ EUR, GBP, CAD, AUD, and JPY are requested by the backend for functional demonstration.
- 🧪 Additional currencies visible in the interface are placeholders unless returned by the configured data source.
- 📌 The limited scope is intentional and is not presented as comprehensive market-data coverage.

### 🏢 Production Readiness

- 🧪 Automated test coverage is not yet documented.
- 🔐 Token lifecycle, CORS policy, secrets management, observability, and rate limiting require production hardening.
- 📱 Responsive behavior is implemented, with further mobile safe-area and navigation refinement planned.
- 📄 A formal project license has not yet been published.

---

## 🗺️ Roadmap

### 🔧 Phase 1 — Stabilization

- 🐘 Restore reliable database connectivity across task and AI workflows
- 🤖 Revalidate AI reply and AI-to-task execution
- 🎙️ Revalidate complete voice-to-text-to-AI behavior
- ✅ Add backend and browser-flow tests
- 📱 Refine mobile safe-area behavior

### 🛡️ Phase 2 — Production Hardening

- 🔑 Replace persistent raw auth tokens with expiring, revocable sessions
- 🌐 Restrict CORS to approved origins
- 🚦 Add rate limiting and abuse protection
- 📊 Add structured logs, metrics, tracing, and alerting
- 🧬 Introduce managed database migrations
- 🔄 Add CI quality gates and deployment checks

### 🧠 Phase 3 — Intelligent Productivity

- 🗓️ Calendar-provider integrations
- 🔔 Multi-channel reminders and notifications
- 🎯 AI prioritization and workload analysis
- 🧩 Tool-based AI actions with explicit user confirmation
- 🗣️ More reliable multilingual speech workflows
- 📱 Installable PWA and native-mobile exploration

---

## 🔒 Security Notes

- 🔐 Passwords are hashed with `bcrypt`.
- 🎟️ Protected data routes require a bearer token.
- 👤 Task and appointment queries are scoped to the authenticated user.
- 🗝️ Secrets are expected through environment variables.
- 🚫 Credentials, private database URLs, and real user location data must never be committed.

> [!WARNING]
> The current authentication and CORS design is suitable for MVP development, not for an internet-scale production system without the hardening work listed above.

---

## 🤝 Contributing

1. 🍴 Fork the repository.
2. 🌿 Create a focused feature branch.
3. 🧪 Add or update tests for behavioral changes.
4. 📝 Keep documentation aligned with real behavior.
5. 🔀 Open a pull request with a clear problem statement and verification notes.

---

## 👨‍💻 Author

**Amin Azimi**  
AI Architect & AI Product Engineer  
Azimi Innovation Lab

🔗 Repository:

```text
https://github.com/aminazimi42-coder/Personal-ai-assistent
```

---

<div align="center">

### 🧠 Built to turn daily context into focused action.

⭐ If this project is useful or interesting, consider starring the repository.

</div>