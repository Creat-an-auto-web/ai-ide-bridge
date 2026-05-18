from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from tdd_agent_framework.agents.test_code_generation import (
    TestCodeGenerationAgentSettings,
    TestCodeGenerationInput,
    TestCodeGenerationQualityChecks,
    TestCodeGenerationResult,
)
from tdd_agent_framework.orchestrators import TestCodeGenerationOrchestrator


class StubService:
    def __init__(self, result):
        self._result = result
        self.called_with = None

    async def generate(self, generation_input, trace_id=None, metadata=None):
        self.called_with = (generation_input, trace_id, metadata)
        return self._result


def make_result() -> TestCodeGenerationResult:
    return TestCodeGenerationResult(
        implementation_plan=["先写 pytest 文件，再补 fixture"],
        test_files=[],
        changed_files=["tests/test_registration_flow.py"],
        rationale="优先按 story 对齐测试文件结构。",
        warnings=[],
        quality_checks=TestCodeGenerationQualityChecks(
            has_test_file_content=True,
            all_files_are_tests=True,
            covers_all_input_test_cases=True,
            changed_files_match_generated_files=True,
        ),
    )


class TestCodeGenerationOrchestratorTest(unittest.TestCase):
    def test_orchestrator_passes_metadata(self) -> None:
        settings = TestCodeGenerationAgentSettings.from_dict(
            {
                "enabled": True,
                "provider_kind": "openai_compatible",
                "provider_name": "openai",
                "model": "gpt-test",
                "api_base": "https://api.openai.com/v1",
                "api_key": "secret-key",
            },
        )
        generation_input = TestCodeGenerationInput.from_dict(
            {
                "task_id": "task_001",
                "user_prompt": "把测试用例转换为测试代码",
                "plan": "优先生成 pytest 文件",
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
                "test_plan": "覆盖注册成功与失败路径",
                "test_cases": [
                    {
                        "id": "tc_story_a_001",
                        "story_id": "story_a",
                        "title": "Story A 正向路径",
                        "level": "integration",
                        "category": "positive",
                        "purpose": "验证主路径",
                        "preconditions": ["数据已准备"],
                        "test_input": {"field": "value"},
                        "steps": ["step 1", "step 2"],
                        "expected_result": "返回成功",
                        "acceptance_criteria_refs": ["行为 A 可验证"],
                        "priority": "high",
                        "automatable": True,
                    }
                ],
            },
        )

        expected = make_result()
        stub = StubService(expected)
        orchestrator = TestCodeGenerationOrchestrator()

        with patch(
            "tdd_agent_framework.orchestrators.test_code_generation.build_test_code_generation_service",
            return_value=stub,
        ):
            result = asyncio.run(orchestrator.run(settings, generation_input))

        self.assertIs(result, expected)
        self.assertEqual(stub.called_with[2], {"orchestrator": "test_code_generation_orchestrator"})


if __name__ == "__main__":
    unittest.main()
