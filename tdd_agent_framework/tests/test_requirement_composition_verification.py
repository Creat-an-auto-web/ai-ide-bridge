from __future__ import annotations

import asyncio
import unittest

from tdd_agent_framework.agents.requirement_analysis.models import (
    AnalysisSummary,
    CapabilityGroup,
    ExecutionConstraints,
    QualityChecks,
    RequirementAnalysisInput,
    RequirementAnalysisResult,
    RequirementSpec,
    StoryUnit,
    WorkspaceSummary,
)
from tdd_agent_framework.agents.requirement_composition_verification import (
    RequirementCompositionVerificationAgent,
    RequirementCompositionVerificationInput,
)
from tdd_agent_framework.agents.requirement_composition_verification.models import (
    RequirementCompositionVerificationResult,
)
from tdd_agent_framework.core import AgentRunContext, ModelTarget, ProviderResponse


class FakeProvider:
    def __init__(self, payload):
        self.payload = payload
        self.last_request = None

    async def generate(self, request):
        self.last_request = request
        return ProviderResponse(raw_text=str(self.payload), parsed_json=self.payload)


class RequirementCompositionVerificationAgentTest(unittest.TestCase):
    def test_returns_valid_composition_verdict(self) -> None:
        payload = {
            "status": "revise",
            "summary": "主路径已覆盖，但缺少权限和失败反馈相关 story。",
            "coverage_assessment": {
                "covers_primary_user_goal": True,
                "covers_permission_constraints": False,
                "covers_failure_handling": False,
                "covers_end_to_end_flow": False,
            },
            "composition_issues": [
                {
                    "id": "issue_missing_permission_guard",
                    "severity": "high",
                    "issue_type": "missing_story",
                    "message": "导出主流程存在，但缺少权限限制 story。",
                    "related_story_ids": ["story_export_selected_records"],
                    "related_capability_group_ids": ["capability_export_flow"],
                    "suggested_action": "add_story",
                }
            ],
            "integration_test_scenarios": [
                {
                    "id": "it_export_success",
                    "title": "管理员按当前筛选条件导出成功",
                    "covers_story_ids": ["story_export_selected_records"],
                    "covers_capability_group_ids": ["capability_export_flow"],
                    "expected_outcome": "下载结果与当前筛选条件一致",
                }
            ],
            "redundant_story_ids": [],
            "missing_story_topics": ["导出权限控制", "导出失败反馈"],
            "revision_guidance": [
                "补充一条导出权限控制 story",
                "补充一条导出失败反馈 story",
            ],
        }
        provider = FakeProvider(payload)
        agent = RequirementCompositionVerificationAgent(
            provider=provider,
            model_target=ModelTarget(provider="openai", model="gpt-5.4"),
        )

        result = asyncio.run(
            agent.run(
                RequirementCompositionVerificationInput(
                    analysis_input=self._make_analysis_input(),
                    analysis_result=self._make_analysis_result(),
                    iteration=1,
                    session_id="comp_verify_001",
                ),
                AgentRunContext(task_id="task_001"),
            )
        )

        self.assertEqual(provider.last_request.agent_name, "requirement_composition_verification")
        self.assertEqual(result.status, "revise")
        self.assertFalse(result.coverage_assessment.covers_permission_constraints)
        self.assertEqual(result.composition_issues[0].issue_type, "missing_story")
        self.assertEqual(result.integration_test_scenarios[0].id, "it_export_success")
        self.assertIn("导出失败反馈", result.missing_story_topics)

    def test_composition_result_accepts_type_alias_and_missing_summary(self) -> None:
        result = RequirementCompositionVerificationResult.from_dict(
            {
                "verdict": "revise",
                "coverage_assessment": {
                    "covers_primary_user_goal": True,
                    "covers_permission_constraints": False,
                    "covers_failure_handling": False,
                    "covers_end_to_end_flow": False,
                },
                "composition_issues": [
                    {
                        "id": "issue_1",
                        "severity": "high",
                        "type": "missing_permission_path",
                        "message": "缺少权限路径 story。",
                    }
                ],
                "integration_test_scenarios": [],
            }
        )

        self.assertEqual(result.status, "revise")
        self.assertEqual(result.composition_issues[0].issue_type, "missing_permission_path")
        self.assertTrue(result.summary)

    def _make_analysis_input(self) -> RequirementAnalysisInput:
        return RequirementAnalysisInput(
            task_id="task_001",
            mode="repo_chat",
            user_prompt="为任务列表增加 CSV 导出能力，并确保权限和失败反馈合理。",
            repo_root="/workspace/project",
            workspace_summary=WorkspaceSummary(
                languages=["typescript", "python"],
                frameworks=["react", "fastapi", "pytest"],
                key_modules=["frontend/tasks", "app/tasks", "tests/tasks"],
            ),
            execution_constraints=ExecutionConstraints(),
        )

    def _make_analysis_result(self) -> RequirementAnalysisResult:
        return RequirementAnalysisResult(
            requirement_spec=RequirementSpec(
                task_id="task_001",
                version=1,
                problem_statement="当前任务列表缺少导出能力，用户无法将当前筛选结果下载为 CSV。",
                product_goal="为任务列表提供 CSV 导出能力。",
                scope=["导出入口", "CSV 文件生成"],
                out_of_scope=["Excel 导出"],
                constraints=["不新增外部依赖"],
                assumptions=["当前已有筛选条件状态"],
                interfaces_or_contracts=["导出内容只覆盖当前筛选结果"],
                acceptance_criteria=[
                    "用户可以触发当前筛选结果的 CSV 导出",
                    "导出文件字段顺序稳定",
                    "现有列表接口行为保持不变",
                ],
                decomposition_strategy="按导出触发与导出生成拆分",
            ),
            story_units=[
                StoryUnit(
                    id="story_export_selected_records",
                    story_kind="admin_outcome",
                    title="仓库管理员可以按当前筛选条件导出任务记录 CSV",
                    as_a="仓库管理员",
                    when_context="我已经在任务记录列表中设置筛选条件",
                    i_want="导出当前筛选结果为 CSV 文件",
                    so_that="我可以将审计数据用于汇报和离线分析",
                    narrative="作为仓库管理员，当我已经在任务记录列表中设置筛选条件时，我希望导出当前筛选结果为 CSV 文件，从而我可以将审计数据用于汇报和离线分析。",
                    actor="仓库管理员",
                    goal="导出当前筛选结果为 CSV 文件",
                    business_value="我可以将审计数据用于汇报和离线分析",
                    business_outcome="用户得到与当前筛选结果一致的 CSV 文件",
                    scope=["导出按钮触发", "CSV 文件下载"],
                    out_of_scope=["Excel 格式导出"],
                    acceptance_criteria=[
                        "给定用户已设置筛选条件，当用户点击导出时，那么下载的 CSV 仅包含满足当前筛选条件的记录",
                        "给定导出成功，当文件生成完成时，那么字段顺序符合约定",
                        "给定当前列表为空，当用户点击导出时，那么系统提示无可导出数据",
                    ],
                    dependencies=[],
                    priority="high",
                    risk="medium",
                    test_focus=["导出成功路径", "字段顺序", "空结果提示"],
                    implementation_hints=["优先复用现有筛选逻辑"],
                )
            ],
            analysis_summary=AnalysisSummary(
                story_unit_count=1,
                high_priority_count=1,
                high_risk_count=0,
                capability_group_count=1,
            ),
            warnings=[],
            quality_checks=QualityChecks(
                has_clear_scope=True,
                has_testable_ac=True,
                dependency_graph_valid=True,
                story_count_within_limit=True,
            ),
            capability_groups=[
                CapabilityGroup(
                    id="capability_export_flow",
                    title="任务记录导出主流程",
                    goal="让仓库管理员可以完成当前筛选结果的导出",
                    scope=["导出触发", "CSV 文件下载"],
                    story_ids=["story_export_selected_records"],
                    priority="high",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
