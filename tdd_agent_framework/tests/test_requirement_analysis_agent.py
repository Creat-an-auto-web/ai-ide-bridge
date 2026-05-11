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
                "story_kind": "user_outcome",
                "title": "已登录用户可以在 access token 过期后自动恢复会话",
                "as_a": "已登录用户",
                "when_context": "我的 access token 已过期但 refresh token 仍有效",
                "i_want": "系统自动获取并写回新的 access token",
                "so_that": "我不需要重新登录也能继续完成当前操作",
                "narrative": "As a 已登录用户, when 我的 access token 已过期但 refresh token 仍有效, I want 系统自动获取并写回新的 access token, so that 我不需要重新登录也能继续完成当前操作。",
                "actor": "已登录用户",
                "goal": "系统自动获取并写回新的 access token",
                "business_value": "我不需要重新登录也能继续完成当前操作",
                "business_outcome": "用户在 token 过期后仍能继续使用当前会话",
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
                "story_kind": "system_feedback",
                "title": "已登录用户在刷新失败时会被安全登出并清理会话状态",
                "as_a": "已登录用户",
                "when_context": "我的 token 刷新流程失败或 refresh token 无效",
                "i_want": "系统终止当前会话并清理本地登录状态",
                "so_that": "我不会继续停留在错误的登录状态中",
                "narrative": "As a 已登录用户, when 我的 token 刷新流程失败或 refresh token 无效, I want 系统终止当前会话并清理本地登录状态, so that 我不会继续停留在错误的登录状态中。",
                "actor": "已登录用户",
                "goal": "系统终止当前会话并清理本地登录状态",
                "business_value": "我不会继续停留在错误的登录状态中",
                "business_outcome": "刷新失败后旧会话被清理且后续请求不再沿用失效 token",
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
        self.assertEqual(
            result.story_units[0].narrative,
            "As a 已登录用户, when 我的 access token 已过期但 refresh token 仍有效, I want 系统自动获取并写回新的 access token, so that 我不需要重新登录也能继续完成当前操作.",
        )

    def test_normalizes_narrative_from_structured_fields(self) -> None:
        payload = {
        "requirement_spec": {
            "task_id": "task_001",
            "version": 1,
            "problem_statement": "任务拆解需要保持结构字段一致。",
            "product_goal": "即使 narrative 被轻微改写，也能继续迭代。",
            "scope": ["story normalization"],
            "out_of_scope": [],
            "constraints": [],
            "assumptions": [],
            "interfaces_or_contracts": [],
            "acceptance_criteria": [
                "story 字段完整",
                "narrative 会被规范化重建",
                "结果可继续进入后续验证",
            ],
            "decomposition_strategy": "按单一 story 输出",
        },
        "story_units": [
            {
                "id": "S1",
                "story_kind": "user_outcome",
                "title": "仓库管理员可以导出当前筛选后的任务记录",
                "as_a": "仓库管理员",
                "when_context": "我已经在任务记录列表中设置筛选条件",
                "i_want": "导出当前筛选结果为 CSV 文件",
                "so_that": "我可以将审计数据用于汇报和离线分析",
                "narrative": "As a 仓库管理员, when 已设置筛选条件时, I want 把结果导出成 CSV, so that 后续方便分析。",
                "actor": "仓库管理员",
                "goal": "导出当前筛选结果为 CSV 文件",
                "business_value": "我可以将审计数据用于汇报和离线分析",
                "business_outcome": "管理员可以稳定导出当前筛选结果供后续分析",
                "scope": ["story normalization"],
                "out_of_scope": [],
                "acceptance_criteria": [
                    "可以导出当前筛选结果",
                    "导出文件格式正确",
                    "导出结果可被后续分析使用",
                ],
                "dependencies": [],
                "priority": "high",
                "risk": "medium",
                "test_focus": ["导出主路径", "文件格式", "筛选条件保留"],
                "implementation_hints": [],
            }
        ],
        }
        provider = FakeProvider(payload)
        agent = RequirementAnalysisAgent(
            provider=provider,
            model_target=ModelTarget(provider="openai", model="gpt-5.4"),
        )

        result = asyncio.run(agent.run(make_input(), AgentRunContext(task_id="task_001")))

        self.assertEqual(
            result.story_units[0].narrative,
            "As a 仓库管理员, when 我已经在任务记录列表中设置筛选条件, I want 导出当前筛选结果为 CSV 文件, so that 我可以将审计数据用于汇报和离线分析.",
        )

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
                "story_kind": "user_outcome",
                "title": "注册用户可以在有效登录态下完成目标 A",
                "as_a": "注册用户",
                "when_context": "我已经处于需要执行目标 A 的业务场景中",
                "i_want": "完成目标 A 对应的单一业务能力",
                "so_that": "我可以完成当前业务流程中的关键一步",
                "narrative": "As a 注册用户, when 我已经处于需要执行目标 A 的业务场景中, I want 完成目标 A 对应的单一业务能力, so that 我可以完成当前业务流程中的关键一步。",
                "actor": "注册用户",
                "goal": "完成目标 A 对应的单一业务能力",
                "business_value": "我可以完成当前业务流程中的关键一步",
                "business_outcome": "用户可以稳定完成目标 A 对应的业务动作",
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
                "story_kind": "user_outcome",
                "title": "注册用户可以在有效登录态下完成目标 B",
                "as_a": "注册用户",
                "when_context": "我已经处于需要执行目标 B 的业务场景中",
                "i_want": "完成目标 B 对应的单一业务能力",
                "so_that": "我可以推进当前业务流程的后续步骤",
                "narrative": "As a 注册用户, when 我已经处于需要执行目标 B 的业务场景中, I want 完成目标 B 对应的单一业务能力, so that 我可以推进当前业务流程的后续步骤。",
                "actor": "注册用户",
                "goal": "完成目标 B 对应的单一业务能力",
                "business_value": "我可以推进当前业务流程的后续步骤",
                "business_outcome": "用户可以稳定完成目标 B 对应的业务动作",
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
                "story_kind": "user_outcome",
                "title": "注册用户可以完成目标 1 对应的业务动作",
                "as_a": "注册用户",
                "when_context": "我正在执行需要目标 1 的业务流程",
                "i_want": "完成目标 1 对应的业务能力",
                "so_that": "我可以推进当前流程",
                "narrative": "As a 注册用户, when 我正在执行需要目标 1 的业务流程, I want 完成目标 1 对应的业务能力, so that 我可以推进当前流程。",
                "actor": "注册用户",
                "goal": "完成目标 1 对应的业务能力",
                "business_value": "我可以推进当前流程",
                "business_outcome": "用户可以稳定完成目标 1",
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
                "story_kind": "user_outcome",
                "title": "注册用户可以完成目标 2 对应的业务动作",
                "as_a": "注册用户",
                "when_context": "我正在执行需要目标 2 的业务流程",
                "i_want": "完成目标 2 对应的业务能力",
                "so_that": "我可以推进当前流程的下一步",
                "narrative": "As a 注册用户, when 我正在执行需要目标 2 的业务流程, I want 完成目标 2 对应的业务能力, so that 我可以推进当前流程的下一步。",
                "actor": "注册用户",
                "goal": "完成目标 2 对应的业务能力",
                "business_value": "我可以推进当前流程的下一步",
                "business_outcome": "用户可以稳定完成目标 2",
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
