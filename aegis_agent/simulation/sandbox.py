from __future__ import annotations

from pydantic import BaseModel, Field

from aegis_agent.config.agent_modes import AgentMode, MODE_PROFILES


class SimulationResult(BaseModel):
    status: str
    success_probability: float = Field(..., ge=0.0, le=1.0)
    risk_score: float = Field(..., ge=0.0, le=1.0)
    recommendations: list[str]
    dry_run_notes: list[str]


class PredictiveSimulationSandbox:
    """Provides a dry-run simulation environment before any production execution."""

    def execute(self, objective: str, mode: AgentMode, agents: list[str], threshold: float = 0.82) -> SimulationResult:
        profile = MODE_PROFILES[mode]
        base_score = 0.72
        quality_bias = float(profile["quality_bias"])
        depth_bonus = 0.1 if profile["reasoning_depth"] in {"deep", "audit"} else 0.04
        agent_bonus = min(0.18, len(agents) * 0.03)
        score = min(0.99, base_score + quality_bias * 0.08 + depth_bonus + agent_bonus)

        success_probability = round(score, 4)
        risk_score = round(max(0.0, 1.0 - success_probability), 4)
        recommendations = [
            "Run validation gate before production deployment",
            "Log all simulated decisions for auditability",
            "Chek token efficiency under the current mode profile",
        ]
        dry_run_notes = [
            f"Objective: {objective}",
            f"Mode: {mode.value}",
            f"Execution threshold: {threshold}",
            f"Simulated agent set: {', '.join(agents)}",
        ]

        if success_probability < threshold:
            recommendations.append("Escalate to Shadow Audit mode for risk mitigation.")

        status = "approved" if success_probability >= threshold else "requires_review"
        return SimulationResult(
            status=status,
            success_probability=success_probability,
            risk_score=risk_score,
            recommendations=recommendations,
            dry_run_notes=dry_run_notes,
        )
