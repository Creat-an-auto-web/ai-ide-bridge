from __future__ import annotations

import unittest

from tdd_agent_framework.agents.requirement_analysis.agent import RequirementAnalysisAgent
from tdd_agent_framework.core import ModelTarget, ProviderResponse
from tdd_agent_framework.registry import AgentRegistry


class FakeProvider:
    async def generate(self, request):
        return ProviderResponse(raw_text="{}", parsed_json={})


class AgentRegistryTest(unittest.TestCase):
    def test_register_and_get_agent(self) -> None:
        registry = AgentRegistry()
        agent = RequirementAnalysisAgent(
            provider=FakeProvider(),
            model_target=ModelTarget(provider="openai", model="gpt-test"),
        )

        registry.register(agent)

        self.assertTrue(registry.has("requirement_analysis"))
        self.assertIs(registry.get("requirement_analysis"), agent)
        self.assertEqual(registry.list_names(), ["requirement_analysis"])


if __name__ == "__main__":
    unittest.main()
