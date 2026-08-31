from __future__ import annotations

from enum import Enum


class AgentMode(str, Enum):
    ULTRA = "Ultra"
    BALANCED = "Balanced"
    ECO = "Eco"
    SHADOW_AUDIT = "Shadow Audit"


MODE_PROFILES = {
    AgentMode.ULTRA: {
        "label": "Ultra",
        "latency": "low",
        "token_budget": 95,
        "quality_bias": 1.0,
        "reasoning_depth": "deep",
    },
    AgentMode.BALANCED: {
        "label": "Balanced",
        "latency": "medium",
        "token_budget": 75,
        "quality_bias": 0.8,
        "reasoning_depth": "standard",
    },
    AgentMode.ECO: {
        "label": "Eco",
        "latency": "high",
        "token_budget": 45,
        "quality_bias": 0.6,
        "reasoning_depth": "efficient",
    },
    AgentMode.SHADOW_AUDIT: {
        "label": "Shadow Audit",
        "latency": "medium",
        "token_budget": 70,
        "quality_bias": 1.1,
        "reasoning_depth": "audit",
    },
}
