from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from tdd_agent_framework.agents.test_case_generation import (
    TestCaseGenerationAgentSettings,
    TestCaseGenerationInput,
)
from tdd_agent_framework.orchestrators import TestCaseGenerationOrchestrator


class StubService:
    def __init__(self, result):
        self._result = result
        self.called_with = None

    async def generate(self, generation_input, trace_id=None, metadata=None):
        self.called_with = (generation_input, trace_id, metadata)
        return self._result


class TestCaseGenerationOrchestratorTest(unittest.TestCase):
    def test_orchestrator_passes_metadata(self) -> None:
        settings = TestCaseGenerationAgentSettings.from_dict(
            {
                "enabled": True,
                "provider_kind": "openai_compatible",
                "provider_name": "openai",
                "model": "gpt-test",
                "api_base": "https://api.openai.com/v1",
                "api_key": "secret-key",
            },
        )
        generation_input = TestCaseGenerationInput.from_dict(
            {
                "task_id": "task_001",
                "story_units": [
                    {
                        "id": "story_a",
                        "title": "Story A",
                        "actor": "用户",
                        "goal": "目标",
                        "business_value": "价值",
                        "scope": ["scope_a"],
                        "out_of_scope": [],
                        "acceptance_criteria": ["行为 A 可验证", "结果 A 可验证", "失败 A 可验证"],
                        "dependencies": [],
                        "priority": "high",
                        "risk": "low",
                        "test_focus": ["A1", "A2", "A3"],
                        "implementation_hints": [],
                    }
                ],
            },
        )

        expected = object()
        stub = StubService(expected)
        orchestrator = TestCaseGenerationOrchestrator()

        with patch(
            "tdd_agent_framework.orchestrators.test_case_generation.build_test_case_generation_service",
            return_value=stub,
        ):
            result = asyncio.run(orchestrator.run(settings, generation_input))

        self.assertIs(result, expected)
        self.assertEqual(stub.called_with[2], {"orchestrator": "test_case_generation_orchestrator"})


if __name__ == "__main__":
    unittest.main()
