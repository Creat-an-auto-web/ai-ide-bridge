from __future__ import annotations

import unittest

from app.models.test_case_generation import TestCaseGenerationRunRequest
from app.services.test_case_generation_service import TestCaseGenerationBackendService
from tdd_agent_framework.agents.test_case_generation import (
    TestCaseGenerationResult,
    TestCaseQualityChecks,
    TestCoverageSummary,
)


class StubOrchestrator:
    def __init__(self, result):
        self.result = result
        self.called_args = None

    async def run(self, settings, generation_input):
        self.called_args = (settings, generation_input)
        return self.result


class TestCaseGenerationBackendServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_maps_payload_to_framework_and_returns_dict(self) -> None:
        payload = TestCaseGenerationRunRequest.model_validate(
            {
                "settings": {
                    "enabled": True,
                    "provider_kind": "openai_compatible",
                    "provider_name": "openai",
                    "model": "gpt-test",
                    "api_base": "https://api.openai.com/v1",
                    "api_key": "secret-key",
                },
                "input": {
                    "task_id": "task_001",
                    "user_prompt": "生成测试用例",
                    "story_units": [
                        {
                            "id": "story_1",
                            "title": "Story 1",
                            "actor": "用户",
                            "goal": "目标",
                            "business_value": "价值",
                            "scope": ["scope_1"],
                            "out_of_scope": [],
                            "acceptance_criteria": ["ac1", "ac2", "ac3"],
                            "dependencies": [],
                            "priority": "high",
                            "risk": "medium",
                            "test_focus": ["focus_1"],
                            "implementation_hints": [],
                        }
                    ],
                    "execution_constraints": {
                        "max_test_cases_per_story": 4,
                        "require_boundary_cases": True,
                        "require_negative_cases": True,
                    },
                },
            },
        )
        orchestrator = StubOrchestrator(
            TestCaseGenerationResult(
                test_plan="覆盖正向、边界、负向",
                test_cases=[],
                coverage_summary=TestCoverageSummary(
                    total_story_count=1,
                    covered_story_count=1,
                    uncovered_story_ids=[],
                    total_test_case_count=0,
                    per_story_case_count={"story_1": 0},
                ),
                warnings=[],
                quality_checks=TestCaseQualityChecks(
                    has_inputs_and_expected_results=True,
                    covers_all_stories=True,
                    has_boundary_cases=True,
                    has_negative_cases=True,
                    case_count_within_limit=True,
                ),
            ),
        )
        service = TestCaseGenerationBackendService(orchestrator=orchestrator)

        result = await service.run(payload)

        self.assertEqual(result["test_plan"], "覆盖正向、边界、负向")
        self.assertIsNotNone(orchestrator.called_args)
        self.assertEqual(orchestrator.called_args[1].task_id, "task_001")


if __name__ == "__main__":
    unittest.main()
