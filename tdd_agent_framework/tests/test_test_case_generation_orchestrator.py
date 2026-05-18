from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from tdd_agent_framework.agents.test_case_generation import (
    TestCaseCompletionCheck,
    TestCaseGenerationAgentSettings,
    TestCaseGenerationInput,
    TestCaseGenerationResult,
    TestCaseQualityChecks,
    TestCoverageSummary,
)
from tdd_agent_framework.orchestrators import TestCaseGenerationOrchestrator


class StubService:
    def __init__(self, result):
        self._result = result
        self.called_with = None

    async def generate(self, generation_input, trace_id=None, metadata=None):
        self.called_with = (generation_input, trace_id, metadata)
        return self._result


class StubVerificationService:
    def __init__(self, result):
        self._result = result
        self.called_with = None

    async def verify(self, verification_input, trace_id=None, metadata=None):
        self.called_with = (verification_input, trace_id, metadata)
        return self._result


def make_result() -> TestCaseGenerationResult:
    return TestCaseGenerationResult(
        test_plan="覆盖正向、边界、负向",
        test_cases=[],
        coverage_summary=TestCoverageSummary(
            total_story_count=1,
            covered_story_count=1,
            uncovered_story_ids=[],
            total_test_case_count=0,
            per_story_case_count={"story_a": 0},
        ),
        warnings=[],
        quality_checks=TestCaseQualityChecks(
            has_inputs_and_expected_results=True,
            covers_all_stories=True,
            has_boundary_cases=True,
            has_negative_cases=True,
            case_count_within_limit=True,
        ),
    )


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
                        "story_kind": "user_outcome",
                        "title": "Story A",
                        "as_a": "用户",
                        "when_context": "当执行流程 A 时",
                        "i_want": "完成目标 A",
                        "so_that": "获得价值 A",
                        "narrative": "作为用户，当执行流程 A 时，我想完成目标 A，以便获得价值 A。",
                        "actor": "用户",
                        "goal": "目标",
                        "business_value": "价值",
                        "business_outcome": "获得价值 A",
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

        expected = make_result()
        stub = StubService(expected)
        orchestrator = TestCaseGenerationOrchestrator()

        with patch(
            "tdd_agent_framework.orchestrators.test_case_generation.build_test_case_generation_service",
            return_value=stub,
        ):
            result = asyncio.run(orchestrator.run(settings, generation_input))

        self.assertIs(result, expected)
        self.assertEqual(stub.called_with[2], {"orchestrator": "test_case_generation_orchestrator"})

    def test_orchestrator_runs_completion_check_when_plan_present(self) -> None:
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
                "plan": "必须覆盖正向、边界和负向场景",
                "story_units": [
                    {
                        "id": "story_a",
                        "story_kind": "user_outcome",
                        "title": "Story A",
                        "as_a": "用户",
                        "when_context": "当执行流程 A 时",
                        "i_want": "完成目标 A",
                        "so_that": "获得价值 A",
                        "narrative": "作为用户，当执行流程 A 时，我想完成目标 A，以便获得价值 A。",
                        "actor": "用户",
                        "goal": "目标",
                        "business_value": "价值",
                        "business_outcome": "获得价值 A",
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
        generated = make_result()
        completion_check = TestCaseCompletionCheck(
            status="complete",
            is_complete=True,
            summary="已覆盖 plan 中的关键点",
            missing_items=[],
            notes=[],
        )
        generation_stub = StubService(generated)
        verifier_stub = StubVerificationService(completion_check)
        orchestrator = TestCaseGenerationOrchestrator()

        with patch(
            "tdd_agent_framework.orchestrators.test_case_generation.build_test_case_generation_service",
            return_value=generation_stub,
        ), patch(
            "tdd_agent_framework.orchestrators.test_case_generation.build_test_case_generation_verification_service",
            return_value=verifier_stub,
        ):
            result = asyncio.run(orchestrator.run(settings, generation_input))

        self.assertIsNot(result, generated)
        self.assertIsNotNone(result.completion_check)
        self.assertEqual(result.completion_check.status, "complete")
        self.assertIsNotNone(verifier_stub.called_with)
        self.assertEqual(verifier_stub.called_with[0].plan, "必须覆盖正向、边界和负向场景")
        self.assertEqual(
            verifier_stub.called_with[2],
            {
                "orchestrator": "test_case_generation_orchestrator",
                "stage": "completion_check",
            },
        )


if __name__ == "__main__":
    unittest.main()
