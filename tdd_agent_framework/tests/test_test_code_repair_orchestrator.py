from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from tdd_agent_framework.agents.test_code_generation import GeneratedTestFile
from tdd_agent_framework.agents.test_code_repair import (
    TestCodeRepairAgentSettings,
    TestCodeRepairInput,
    TestCodeRepairQualityChecks,
    TestCodeRepairResult,
)
from tdd_agent_framework.orchestrators import TestCodeRepairOrchestrator


class StubService:
    def __init__(self, result):
        self._result = result
        self.called_with = None

    async def repair(self, repair_input, trace_id=None, metadata=None):
        self.called_with = (repair_input, trace_id, metadata)
        return self._result


def make_result() -> TestCodeRepairResult:
    return TestCodeRepairResult(
        repair_plan=["先修复断言，再修复 fixture"],
        test_files=[
            GeneratedTestFile(
                path="tests/test_registration_flow.py",
                language="python",
                framework="pytest",
                purpose="覆盖注册成功路径",
                related_test_case_ids=["tc_story_a_001"],
                content="def test_registration_success():\n    assert True\n",
            )
        ],
        changed_files=["tests/test_registration_flow.py"],
        reasoning_summary="优先处理失败断言。",
        warnings=[],
        quality_checks=TestCodeRepairQualityChecks(
            has_test_file_content=True,
            covers_all_original_files=True,
            keeps_test_scope=True,
        ),
    )


class TestCodeRepairOrchestratorTest(unittest.TestCase):
    def test_orchestrator_passes_metadata(self) -> None:
        settings = TestCodeRepairAgentSettings.from_dict(
            {
                "enabled": True,
                "provider_kind": "openai_compatible",
                "provider_name": "openai",
                "model": "gpt-test",
                "api_base": "https://api.openai.com/v1",
                "api_key": "secret-key",
            },
        )
        repair_input = TestCodeRepairInput.from_dict(
            {
                "task_id": "task_001",
                "user_prompt": "修复失败的测试",
                "plan": "优先修复断言",
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
                "test_files": [
                    {
                        "path": "tests/test_registration_flow.py",
                        "language": "python",
                        "framework": "pytest",
                        "purpose": "覆盖注册成功路径",
                        "related_test_case_ids": ["tc_story_a_001"],
                        "content": "def test_registration_success():\n    assert False\n",
                    }
                ],
                "execution_result": {
                    "command": "python -m pytest tests/test_registration_flow.py",
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": "FAILED tests/test_registration_flow.py::test_registration_success",
                    "failed_tests": ["tests/test_registration_flow.py::test_registration_success"],
                    "workspace_diff": "diff --git a/tests/test_registration_flow.py b/tests/test_registration_flow.py",
                },
            },
        )

        expected = make_result()
        stub = StubService(expected)
        orchestrator = TestCodeRepairOrchestrator()

        with patch(
            "tdd_agent_framework.orchestrators.test_code_repair.build_test_code_repair_service",
            return_value=stub,
        ):
            result = asyncio.run(orchestrator.run(settings, repair_input))

        self.assertIs(result, expected)
        self.assertEqual(stub.called_with[2], {"orchestrator": "test_code_repair_orchestrator"})


if __name__ == "__main__":
    unittest.main()
