import unittest

from aegis_agent.config.agent_modes import AgentMode, MODE_PROFILES
from aegis_agent.config.settings import get_settings
from aegis_agent.core.token_efficiency import TokenEfficiencyEngine
from aegis_agent.simulation.sandbox import PredictiveSimulationSandbox


class TestAegisAgentPhaseOne(unittest.TestCase):
    def test_agent_modes_are_configured(self):
        self.assertEqual(set(AgentMode), set(MODE_PROFILES.keys()))
        self.assertIn(AgentMode.ULTRA, MODE_PROFILES)
        self.assertIn(AgentMode.BALANCED, MODE_PROFILES)
        self.assertIn(AgentMode.ECO, MODE_PROFILES)
        self.assertIn(AgentMode.SHADOW_AUDIT, MODE_PROFILES)

    def test_settings_load(self):
        settings = get_settings()
        self.assertEqual(settings.project_name, "AegisAgent AI")
        self.assertTrue(settings.enable_dry_run)
        self.assertTrue(settings.enable_self_healing)

    def test_token_efficiency_engine_compresses_payload(self):
        engine = TokenEfficiencyEngine()
        result = engine.optimize_prompt("def x():\n    return 123\n")
        self.assertTrue(result["success"])
        self.assertIn("compressed_tokens", result)
        self.assertIn("compression_ratio", result)

    def test_simulation_sandbox_outputs_success_metrics(self):
        sandbox = PredictiveSimulationSandbox()
        result = sandbox.execute(
            objective="Deploy sovereign orchestrator",
            mode=AgentMode.BALANCED,
            agents=["Hermes", "Alina", "Kiyan", "Beta", "Aylin"],
        )
        self.assertGreaterEqual(result.success_probability, 0.0)
        self.assertLessEqual(result.success_probability, 1.0)
        self.assertIn("dry_run_notes", result.model_dump())


if __name__ == "__main__":
    unittest.main(verbosity=2)
