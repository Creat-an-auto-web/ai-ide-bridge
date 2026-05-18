from __future__ import annotations

import unittest

from app.models.test_code_generation import TestCodeGenerationRunRequest
from app.services.test_code_generation_service import TestCodeGenerationBackendService
from tdd_agent_framework.agents.test_code_generation import (
    GeneratedTestFile,
    TestCodeGenerationQualityChecks,
    TestCodeGenerationResult,
)


class StubOrchestrator:
    def __init__(self, result):
        self.result = result
        self.called_args = None

    async def run(self, settings, generation_input):
        self.called_args = (settings, generation_input)
        return self.result


class TestCodeGenerationBackendServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_maps_payload_to_framework_and_returns_dict(self) -> None:
        payload = TestCodeGenerationRunRequest.model_validate(
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
                    "user_prompt": "把测试用例转换为测试代码",
                    "plan": "优先生成 pytest 文件",
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
                    "execution_constraints": {
                        "max_test_files": 2,
                        "prefer_existing_test_stack": True,
                        "include_fixtures": True,
                        "framework_hint": "pytest",
                    },
                },
            },
        )
        orchestrator = StubOrchestrator(
            TestCodeGenerationResult(
                implementation_plan=["先生成 pytest 文件"],
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
                rationale="pytest 与当前后端测试栈一致。",
                warnings=[],
                quality_checks=TestCodeGenerationQualityChecks(
                    has_test_file_content=True,
                    all_files_are_tests=True,
                    covers_all_input_test_cases=True,
                    changed_files_match_generated_files=True,
                ),
            ),
        )
        service = TestCodeGenerationBackendService(orchestrator=orchestrator)

        result = await service.run(payload)

        self.assertEqual(result["changed_files"], ["tests/test_registration_flow.py"])
        self.assertIsNotNone(orchestrator.called_args)
        self.assertEqual(orchestrator.called_args[1].task_id, "task_001")
        self.assertEqual(orchestrator.called_args[1].test_plan, "覆盖注册成功和失败路径")


if __name__ == "__main__":
    unittest.main()
