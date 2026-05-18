from __future__ import annotations

import unittest

from app.models.test_code_repair import TestCodeRepairRunRequest
from app.services.test_code_repair_service import TestCodeRepairBackendService
from tdd_agent_framework.agents.test_code_repair import (
    TestCodeRepairQualityChecks,
    TestCodeRepairResult,
)
from tdd_agent_framework.agents.test_code_generation import GeneratedTestFile


class StubOrchestrator:
    def __init__(self, result):
        self.result = result
        self.called_args = None

    async def run(self, settings, repair_input):
        self.called_args = (settings, repair_input)
        return self.result


class TestCodeRepairBackendServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_maps_payload_to_framework_and_returns_dict(self) -> None:
        payload = TestCodeRepairRunRequest.model_validate(
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
                    "user_prompt": "修复失败的测试文件",
                    "plan": "优先修复断言和 fixture 问题",
                    "story_units": [
                        {
                            "id": "story_1",
                            "story_kind": "user_outcome",
                            "title": "Story 1",
                            "as_a": "用户",
                            "when_context": "当触发关键流程时",
                            "i_want": "完成目标",
                            "so_that": "获得价值",
                            "narrative": "作为用户，当触发关键流程时，我想完成目标，以便获得价值。",
                            "actor": "用户",
                            "goal": "目标",
                            "business_value": "价值",
                            "business_outcome": "获得价值",
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
                    "test_plan": "覆盖注册成功和失败路径",
                    "test_cases": [
                        {
                            "id": "tc_story_1_001",
                            "story_id": "story_1",
                            "title": "注册成功",
                            "level": "integration",
                            "category": "positive",
                            "purpose": "验证主路径",
                            "preconditions": ["数据准备完毕"],
                            "test_input": {"email": "demo@example.com"},
                            "steps": ["提交表单", "检查结果"],
                            "expected_result": "注册成功",
                            "acceptance_criteria_refs": ["ac1"],
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
                            "related_test_case_ids": ["tc_story_1_001"],
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
            },
        )
        orchestrator = StubOrchestrator(
            TestCodeRepairResult(
                repair_plan=["先修复断言，再补足 fixture"],
                test_files=[
                    GeneratedTestFile(
                        path="tests/test_registration_flow.py",
                        language="python",
                        framework="pytest",
                        purpose="覆盖注册成功路径",
                        related_test_case_ids=["tc_story_1_001"],
                        content="def test_registration_success():\n    assert True\n",
                    )
                ],
                changed_files=["tests/test_registration_flow.py"],
                reasoning_summary="根据失败断言修复测试期望。",
                warnings=[],
                quality_checks=TestCodeRepairQualityChecks(
                    has_test_file_content=True,
                    covers_all_original_files=True,
                    keeps_test_scope=True,
                ),
            ),
        )
        service = TestCodeRepairBackendService(orchestrator=orchestrator)

        result = await service.run(payload)

        self.assertEqual(result["changed_files"], ["tests/test_registration_flow.py"])
        self.assertIsNotNone(orchestrator.called_args)
        self.assertEqual(orchestrator.called_args[1].task_id, "task_001")
        self.assertEqual(orchestrator.called_args[1].execution_result.exit_code, 1)


if __name__ == "__main__":
    unittest.main()
