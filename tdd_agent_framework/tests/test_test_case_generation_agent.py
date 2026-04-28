from __future__ import annotations

import asyncio
import unittest

from tdd_agent_framework.agents.test_case_generation import (
    TestCaseGenerationAgent,
    TestCaseGenerationInput,
    TestCaseGenerationValidationError,
)
from tdd_agent_framework.core import AgentRunContext, ModelTarget, ProviderResponse


class FakeProvider:
    def __init__(self, payload):
        self.payload = payload
        self.last_request = None

    async def generate(self, request):
        self.last_request = request
        return ProviderResponse(raw_text=str(self.payload), parsed_json=self.payload)


def make_input() -> TestCaseGenerationInput:
    return TestCaseGenerationInput.from_dict(
        {
            "task_id": "task_001",
            "user_prompt": "根据 story 生成测试用例",
            "story_units": [
                {
                    "id": "story_refresh_success",
                    "title": "过期 token 自动刷新",
                    "actor": "已登录用户",
                    "goal": "在 token 过期后自动获取新 token",
                    "business_value": "减少登录中断",
                    "scope": ["token expiry detection"],
                    "out_of_scope": [],
                    "acceptance_criteria": [
                        "当 token 过期时系统会自动请求新 token",
                        "新 token 会写回存储",
                        "刷新后后续请求使用新 token",
                    ],
                    "dependencies": [],
                    "priority": "high",
                    "risk": "medium",
                    "test_focus": ["刷新成功路径", "token 持久化", "刷新后请求状态"],
                    "implementation_hints": [],
                }
            ],
            "execution_constraints": {
                "max_test_cases_per_story": 4,
                "require_boundary_cases": True,
                "require_negative_cases": True,
            },
        },
    )


class TestCaseGenerationAgentTest(unittest.TestCase):
    def test_returns_valid_result(self) -> None:
        payload = {
            "test_plan": "按 story 覆盖正向、边界和失败路径。",
            "test_cases": [
                {
                    "id": "tc_refresh_success_positive",
                    "story_id": "story_refresh_success",
                    "title": "refresh 正向成功",
                    "level": "unit",
                    "category": "positive",
                    "purpose": "验证 token 过期后可以成功刷新",
                    "preconditions": ["refresh token 有效"],
                    "test_input": {"access_token_expired": True, "refresh_token_valid": True},
                    "steps": ["触发请求", "执行刷新流程", "读取 token 存储"],
                    "expected_result": "返回新 token 并写回存储",
                    "acceptance_criteria_refs": ["新 token 会写回存储"],
                    "priority": "high",
                    "automatable": True,
                },
                {
                    "id": "tc_refresh_success_boundary",
                    "story_id": "story_refresh_success",
                    "title": "refresh 边界",
                    "level": "unit",
                    "category": "boundary",
                    "purpose": "验证临界过期时间仍可刷新",
                    "preconditions": ["token 即将过期"],
                    "test_input": {"access_token_expired": "near_expiry", "refresh_token_valid": True},
                    "steps": ["触发请求", "执行刷新流程"],
                    "expected_result": "刷新流程稳定完成",
                    "acceptance_criteria_refs": ["当 token 过期时系统会自动请求新 token"],
                    "priority": "medium",
                    "automatable": True,
                },
                {
                    "id": "tc_refresh_success_negative",
                    "story_id": "story_refresh_success",
                    "title": "refresh 失败",
                    "level": "integration",
                    "category": "negative",
                    "purpose": "验证 refresh token 无效时失败可观测",
                    "preconditions": ["refresh token 无效"],
                    "test_input": {"access_token_expired": True, "refresh_token_valid": False},
                    "steps": ["触发请求", "执行刷新流程", "观察返回状态"],
                    "expected_result": "返回失败并清理会话状态",
                    "acceptance_criteria_refs": ["刷新后后续请求使用新 token"],
                    "priority": "high",
                    "automatable": True,
                },
            ],
            "warnings": [],
        }
        provider = FakeProvider(payload)
        agent = TestCaseGenerationAgent(
            provider=provider,
            model_target=ModelTarget(provider="openai", model="gpt-5.4"),
        )

        result = asyncio.run(agent.run(make_input(), AgentRunContext(task_id="task_001")))

        self.assertEqual(provider.last_request.agent_name, "test_case_generation")
        self.assertEqual(result.coverage_summary.total_story_count, 1)
        self.assertEqual(result.coverage_summary.covered_story_count, 1)
        self.assertTrue(result.quality_checks.has_inputs_and_expected_results)
        self.assertTrue(result.quality_checks.has_boundary_cases)
        self.assertTrue(result.quality_checks.has_negative_cases)

    def test_rejects_missing_negative_case(self) -> None:
        payload = {
            "test_plan": "只有正向和边界",
            "test_cases": [
                {
                    "id": "tc_1",
                    "story_id": "story_refresh_success",
                    "title": "正向",
                    "level": "unit",
                    "category": "positive",
                    "purpose": "验证成功路径",
                    "preconditions": [],
                    "test_input": {"refresh_token_valid": True},
                    "steps": ["执行刷新", "检查结果"],
                    "expected_result": "刷新成功",
                    "acceptance_criteria_refs": [],
                    "priority": "high",
                    "automatable": True,
                },
                {
                    "id": "tc_2",
                    "story_id": "story_refresh_success",
                    "title": "边界",
                    "level": "unit",
                    "category": "boundary",
                    "purpose": "验证边界",
                    "preconditions": [],
                    "test_input": {"refresh_token_valid": True, "expiry_seconds": 0},
                    "steps": ["执行刷新", "检查结果"],
                    "expected_result": "刷新成功",
                    "acceptance_criteria_refs": [],
                    "priority": "medium",
                    "automatable": True,
                },
            ],
        }
        provider = FakeProvider(payload)
        agent = TestCaseGenerationAgent(
            provider=provider,
            model_target=ModelTarget(provider="openai", model="gpt-5.4"),
        )

        with self.assertRaisesRegex(TestCaseGenerationValidationError, "negative"):
            asyncio.run(agent.run(make_input(), AgentRunContext(task_id="task_001")))


if __name__ == "__main__":
    unittest.main()
