from __future__ import annotations

import asyncio
import unittest

from tdd_agent_framework.agents.requirement_analysis.agent import RequirementAnalysisAgent
from tdd_agent_framework.agents.requirement_analysis.models import (
    ExecutionConstraints,
    RequirementAnalysisInput,
    WorkspaceSummary,
)
from tdd_agent_framework.agents.requirement_analysis.quality_checker import (
    RequirementAnalysisValidationError,
)
from tdd_agent_framework.core import AgentRunContext, ModelTarget, ProviderResponse


class FakeProvider:
    def __init__(self, payload):
        self.payload = payload
        self.last_request = None

    async def generate(self, request):
        self.last_request = request
        return ProviderResponse(raw_text=str(self.payload), parsed_json=self.payload)


def make_input(max_story_units: int = 4) -> RequirementAnalysisInput:
    return RequirementAnalysisInput(
        task_id="task_001",
        mode="repo_chat",
        user_prompt="修复 token 刷新失效问题",
        repo_root="/workspace/project",
        workspace_summary=WorkspaceSummary(
            languages=["python"],
            frameworks=["fastapi", "pytest"],
            key_modules=["app/auth", "tests/auth"],
        ),
        active_file="app/auth/service.py",
        open_files=["app/auth/service.py", "tests/test_auth.py"],
        recent_test_failures=["test_refresh_success expected token but got None"],
        execution_constraints=ExecutionConstraints(max_story_units=max_story_units),
    )


class RequirementAnalysisAgentTest(unittest.TestCase):
    def test_returns_valid_result(self) -> None:
        payload = {
        "requirement_spec": {
            "task_id": "task_001",
            "version": 1,
            "problem_statement": "access token 过期后无法自动刷新，导致请求失败。",
            "product_goal": "恢复自动刷新能力并保证失败时安全退出。",
            "scope": ["token expiry detection", "refresh flow", "logout fallback"],
            "out_of_scope": ["login ui redesign"],
            "constraints": ["不引入新的外部依赖"],
            "assumptions": ["项目已有 refresh token 机制"],
            "interfaces_or_contracts": ["refresh_session(user_id, refresh_token) -> SessionResult"],
            "acceptance_criteria": [
                "access token 过期时会自动触发刷新流程",
                "刷新成功后新 token 会写回存储",
                "刷新失败时用户会被安全登出",
            ],
            "decomposition_strategy": "按成功刷新和失败处理拆分",
        },
        "story_units": [
            {
                "id": "story_refresh_success",
                "title": "过期 token 自动刷新",
                "actor": "已登录用户",
                "goal": "在 token 过期后自动获取新 token",
                "business_value": "减少登录中断",
                "scope": ["token expiry detection", "refresh session update"],
                "out_of_scope": ["login ui redesign"],
                "acceptance_criteria": [
                    "当 token 过期且 refresh token 有效时，系统会请求新 token",
                    "新 token 会写回本地存储",
                    "刷新后后续请求使用新 token",
                ],
                "dependencies": [],
                "priority": "high",
                "risk": "medium",
                "test_focus": ["刷新成功路径", "token 持久化", "刷新后请求状态"],
                "implementation_hints": ["优先检查 refresh_session 流程"],
            },
            {
                "id": "story_refresh_failure",
                "title": "刷新失败时安全登出",
                "actor": "已登录用户",
                "goal": "刷新失败时清理会话状态",
                "business_value": "避免错误状态持续存在",
                "scope": ["logout fallback"],
                "out_of_scope": ["permission redesign"],
                "acceptance_criteria": [
                    "当 refresh token 无效时，系统会终止当前会话",
                    "本地 token 状态会被清理",
                    "失败后的后续请求不再携带旧 token",
                ],
                "dependencies": ["story_refresh_success"],
                "priority": "medium",
                "risk": "high",
                "test_focus": ["刷新失败路径", "状态清理", "后续请求状态"],
                "implementation_hints": ["检查 logout fallback 逻辑"],
            },
        ],
        }
        provider = FakeProvider(payload)
        agent = RequirementAnalysisAgent(
            provider=provider,
            model_target=ModelTarget(provider="openai", model="gpt-5.4"),
        )

        result = asyncio.run(agent.run(make_input(), AgentRunContext(task_id="task_001")))

        self.assertEqual(provider.last_request.agent_name, "requirement_analysis")
        self.assertEqual(result.analysis_summary.story_unit_count, 2)
        self.assertEqual(result.analysis_summary.high_priority_count, 1)
        self.assertEqual(result.analysis_summary.high_risk_count, 1)
        self.assertTrue(result.quality_checks.has_clear_scope)
        self.assertTrue(result.quality_checks.has_testable_ac)
        self.assertTrue(result.quality_checks.dependency_graph_valid)
        self.assertTrue(result.quality_checks.story_count_within_limit)

    def test_rejects_cyclic_dependencies(self) -> None:
        payload = {
        "requirement_spec": {
            "task_id": "task_001",
            "version": 1,
            "problem_statement": "修复登录后刷新失败问题。",
            "product_goal": "恢复 token 刷新能力。",
            "scope": ["refresh flow"],
            "out_of_scope": ["ui redesign"],
            "constraints": ["保持现有接口不变"],
            "assumptions": ["已有 refresh token 机制"],
            "interfaces_or_contracts": ["refresh_session(user_id, refresh_token) -> SessionResult"],
            "acceptance_criteria": [
                "token 过期时系统会尝试刷新",
                "刷新成功后新 token 会写回存储",
                "刷新失败时会清理登录状态",
            ],
            "decomposition_strategy": "按行为阶段拆分",
        },
        "story_units": [
            {
                "id": "story_a",
                "title": "A",
                "actor": "用户",
                "goal": "目标 A 足够具体",
                "business_value": "价值 A",
                "scope": ["scope_a"],
                "out_of_scope": [],
                "acceptance_criteria": [
                    "系统会完成行为 A",
                    "结果会被正确保存",
                    "失败时会产生可观察状态",
                ],
                "dependencies": ["story_b"],
                "priority": "high",
                "risk": "medium",
                "test_focus": ["A path", "A state", "A failure"],
                "implementation_hints": [],
            },
            {
                "id": "story_b",
                "title": "B",
                "actor": "用户",
                "goal": "目标 B 足够具体",
                "business_value": "价值 B",
                "scope": ["scope_b"],
                "out_of_scope": [],
                "acceptance_criteria": [
                    "系统会完成行为 B",
                    "结果会被正确保存",
                    "失败时会产生可观察状态",
                ],
                "dependencies": ["story_a"],
                "priority": "medium",
                "risk": "low",
                "test_focus": ["B path", "B state", "B failure"],
                "implementation_hints": [],
            },
        ],
        }
        provider = FakeProvider(payload)
        agent = RequirementAnalysisAgent(
            provider=provider,
            model_target=ModelTarget(provider="anthropic", model="claude-test"),
        )

        with self.assertRaisesRegex(RequirementAnalysisValidationError, "cycle"):
            asyncio.run(agent.run(make_input(), AgentRunContext(task_id="task_001")))

    def test_rejects_story_count_limit(self) -> None:
        payload = {
        "requirement_spec": {
            "task_id": "task_001",
            "version": 1,
            "problem_statement": "需要拆出多个子需求。",
            "product_goal": "限制 story 数量。",
            "scope": ["scope_main"],
            "out_of_scope": [],
            "constraints": [],
            "assumptions": [],
            "interfaces_or_contracts": [],
            "acceptance_criteria": [
                "需求会被拆解",
                "每个 story 都会可测试",
                "story 数量不会失控",
            ],
            "decomposition_strategy": "按顺序拆分",
        },
        "story_units": [
            {
                "id": "story_1",
                "title": "Story 1",
                "actor": "用户",
                "goal": "目标 1 足够具体",
                "business_value": "价值 1",
                "scope": ["scope_1"],
                "out_of_scope": [],
                "acceptance_criteria": [
                    "行为 1 会被执行完成",
                    "结果 1 会被正确记录",
                    "失败 1 会有清晰反馈",
                ],
                "dependencies": [],
                "priority": "high",
                "risk": "low",
                "test_focus": ["1a", "1b", "1c"],
                "implementation_hints": [],
            },
            {
                "id": "story_2",
                "title": "Story 2",
                "actor": "用户",
                "goal": "目标 2 足够具体",
                "business_value": "价值 2",
                "scope": ["scope_2"],
                "out_of_scope": [],
                "acceptance_criteria": [
                    "行为 2 会被执行完成",
                    "结果 2 会被正确记录",
                    "失败 2 会有清晰反馈",
                ],
                "dependencies": [],
                "priority": "medium",
                "risk": "low",
                "test_focus": ["2a", "2b", "2c"],
                "implementation_hints": [],
            },
        ],
        }
        provider = FakeProvider(payload)
        agent = RequirementAnalysisAgent(
            provider=provider,
            model_target=ModelTarget(provider="openrouter", model="qwen-test"),
        )

        with self.assertRaisesRegex(RequirementAnalysisValidationError, "max_story_units"):
            asyncio.run(
                agent.run(
                    make_input(max_story_units=1),
                    AgentRunContext(task_id="task_001"),
                ),
            )


if __name__ == "__main__":
    unittest.main()
