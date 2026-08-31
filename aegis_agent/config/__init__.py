"""Configuration package for the AegisAgent platform."""

from .agent_modes import AgentMode, MODE_PROFILES
from .settings import Settings, get_settings

__all__ = ["AgentMode", "MODE_PROFILES", "Settings", "get_settings"]
