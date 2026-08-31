from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from aegis_agent.config.agent_modes import AgentMode, MODE_PROFILES
from aegis_agent.config.settings import get_settings
from aegis_agent.core.token_efficiency import TokenEfficiencyEngine
from aegis_agent.simulation.sandbox import PredictiveSimulationSandbox


class AgentTask(BaseModel):
    task: str = Field(..., min_length=1)
    mode: AgentMode = AgentMode.BALANCED
    agent_names: list[str] = Field(default_factory=lambda: ["Hermes", "Alina", "Kiyan", "Beta", "Aylin"])


def create_app() -> FastAPI:
    settings = get_settings()
    engine = TokenEfficiencyEngine()
    sandbox = PredictiveSimulationSandbox()
    app = FastAPI(
        title=settings.project_name,
        version="0.1.0",
        description="Sovereign Autonomous Multi-Agent Platform",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parents[1] / "static"), name="static")

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "project": settings.project_name,
            "environment": settings.environment,
            "mode": settings.default_mode.value,
            "dry_run": settings.enable_dry_run,
        }

    @app.get("/modes")
    async def modes() -> dict[str, object]:
        return {
            "modes": [
                {"name": mode.value, "profile": MODE_PROFILES[mode]}
                for mode in AgentMode
            ]
        }

    @app.post("/api/v1/agents/plan")
    async def plan_task(task: AgentTask) -> dict[str, object]:
        optimization = engine.optimize_prompt(task.task)
        dry_run = sandbox.execute(
            objective=task.task,
            mode=task.mode,
            agents=task.agent_names,
            threshold=settings.simulation_threshold,
        )

        return {
            "status": "accepted",
            "mode": task.mode.value,
            "mode_profile": MODE_PROFILES[task.mode],
            "optimization": optimization,
            "dry_run": dry_run.model_dump(),
            "agents": task.agent_names,
        }

    @app.get("/dashboard")
    async def dashboard() -> FileResponse:
        template_path = Path(__file__).resolve().parents[1] / "templates" / "aegis_dashboard.html"
        return FileResponse(template_path)

    @app.websocket("/ws/telemetry")
    async def telemetry(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                payload = {
                    "project": settings.project_name,
                    "mode": settings.default_mode.value,
                    "status": "online",
                    "agents": {
                        "Hermes": "orchestrating",
                        "Alina": "coordinating",
                        "Kiyan": "executing",
                        "Beta": "rendering",
                        "Aylin": "auditing",
                    },
                    "cache_hit_rate": engine.compute_cache_hit_rate(),
                }
                await websocket.send_json(payload)
                await asyncio.sleep(2)
        except WebSocketDisconnect:
            return

    return app
