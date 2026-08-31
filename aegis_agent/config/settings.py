from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .agent_modes import AgentMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    project_name: str = "AegisAgent AI"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    default_mode: AgentMode = AgentMode.BALANCED
    max_context_tokens: int = 128000
    enable_dry_run: bool = True
    enable_self_healing: bool = True
    simulation_threshold: float = Field(default=0.82, ge=0.0, le=1.0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
