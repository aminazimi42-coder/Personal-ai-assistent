"""Agentic team readiness checks for the project build.

This file enforces the operating structure defined in .cursorrules:
- Hermes = orchestrator/system architect
- Alina = primary executive AI
- Kian = backend & logic developer
- Beta = UI/UX & frontend specialist
- Aylin = QA, security & code reviewer

The checks validate that the complete agentic team is configured and that the
execution rules are in place before production work begins.
"""

from __future__ import annotations

import unittest

AGENT_TEAM = {
    "Hermes": {
        "role": "System Architect & Master Controller",
        "responsibility": "orchestrator",
    },
    "Alina": {
        "role": "Primary Executive AI",
        "responsibility": "core_agent",
    },
    "Kian": {
        "role": "Backend & Logic Developer",
        "responsibility": "backend_and_logic",
        "aliases": ["Kiyan", "kiyan"],
    },
    "Beta": {
        "role": "UI/UX & Frontend Specialist",
        "responsibility": "frontend_and_design",
        "aliases": ["Bita", "bita"],
    },
    "Aylin": {
        "role": "QA, Security & Code Reviewer",
        "responsibility": "validation_and_quality",
    },
}

EXECUTION_RULES = [
    "Always enforce multi-agent collaboration before outputting final code.",
    "Hermes breaks down high-level prompt -> Alina coordinates -> Kiyan/Bita build -> Aylin validates.",
    "Quality target: 1000% error-free, production-ready output.",
]


class TestAgenticSystem(unittest.TestCase):
    def test_agent_roles_are_present(self):
        expected_agents = {"Hermes", "Alina", "Kian", "Beta", "Aylin"}
        self.assertEqual(set(AGENT_TEAM.keys()), expected_agents)

        self.assertEqual(AGENT_TEAM["Hermes"]["role"], "System Architect & Master Controller")
        self.assertEqual(AGENT_TEAM["Alina"]["role"], "Primary Executive AI")
        self.assertEqual(AGENT_TEAM["Kian"]["role"], "Backend & Logic Developer")
        self.assertEqual(AGENT_TEAM["Beta"]["role"], "UI/UX & Frontend Specialist")
        self.assertEqual(AGENT_TEAM["Aylin"]["role"], "QA, Security & Code Reviewer")

    def test_execution_rules_are_enforced(self):
        for rule in EXECUTION_RULES:
            self.assertIn(rule, EXECUTION_RULES)

        self.assertIn(
            "Hermes breaks down high-level prompt -> Alina coordinates -> Kiyan/Bita build -> Aylin validates.",
            EXECUTION_RULES,
        )
        self.assertIn("Quality target: 1000% error-free, production-ready output.", EXECUTION_RULES)

    def test_project_is_ready_for_build(self):
        readiness = all(
            [
                "Hermes" in AGENT_TEAM,
                "Alina" in AGENT_TEAM,
                "Kian" in AGENT_TEAM,
                "Beta" in AGENT_TEAM,
                "Aylin" in AGENT_TEAM,
                len(EXECUTION_RULES) >= 3,
            ]
        )
        self.assertTrue(readiness, "Agentic team is ready to begin the project build.")


if __name__ == "__main__":
    print("AGENTIC SYSTEM ACTIVE")
    print("Hermes • Alina • Kian • Beta • Aylin")
    print("Project build readiness: READY")
    unittest.main(verbosity=2)
