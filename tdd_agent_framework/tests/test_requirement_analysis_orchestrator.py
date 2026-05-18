from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tdd_agent_framework.agents.requirement_analysis import (
    AnalysisSummary,
    CapabilityGroup,
    ExecutionConstraints,
    RequirementAnalysisAgent,
    RequirementAnalysisInput,
    QualityChecks,
    RequirementAnalysisResult,
    RequirementSpec,
    RequirementVerificationResult,
    StoryUnit,
    VerificationIssue,
    VerificationQualityScore,
    WorkspaceSummary,
)
from tdd_agent_framework.agents.requirement_composition_verification import (
    CompositionCoverageAssessment,
    CompositionIssue,
    RequirementCompositionVerificationResult,
)
from tdd_agent_framework.core import ModelTarget, ProviderResponse
from tdd_agent_framework.orchestrators import RequirementAnalysisOrchestrator


class StaticProvider:
    def __init__(self, payload):
        self.payload = payload

    async def generate(self, request):
        return ProviderResponse(raw_text="{}", parsed_json=self.payload)


class RequirementAnalysisOrchestratorTest(unittest.TestCase):
    def test_orchestrator_enriches_workspace_summary_from_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_demo.py").write_text("def test_demo():\n    assert True\n", encoding="utf-8")
            (root / "app").mkdir()
            (root / "app" / "service.py").write_text("print('ok')\n", encoding="utf-8")

            payload = {
                "requirement_spec": {
                    "task_id": "task_001",
                    "version": 1,
                    "problem_statement": "需要修复某个问题并拆解需求。",
                    "product_goal": "产出结构化需求结果。",
                    "scope": ["scope_a"],
                    "out_of_scope": [],
                    "constraints": [],
                    "assumptions": [],
                    "interfaces_or_contracts": [],
                    "acceptance_criteria": [
                        "产出 requirement spec",
                        "产出 story units",
                        "story units 可被测试消费"
                    ],
                    "decomposition_strategy": "按职责拆分",
                },
                "story_units": [
                    {
                        "id": "story_a",
                        "story_kind": "user_outcome",
                        "title": "注册用户可以完成需求拆解中的目标 A",
                        "as_a": "注册用户",
                        "when_context": "我正在执行与目标 A 相关的业务场景",
                        "i_want": "完成目标 A 对应的单一业务能力",
                        "so_that": "我可以推进当前业务流程",
                        "narrative": "作为注册用户，当我正在执行与目标 A 相关的业务场景时，我希望完成目标 A 对应的单一业务能力，从而我可以推进当前业务流程。",
                        "actor": "注册用户",
                        "goal": "完成目标 A 对应的单一业务能力",
                        "business_value": "我可以推进当前业务流程",
                        "business_outcome": "用户可以稳定完成目标 A 对应的业务动作",
                        "scope": ["scope_a"],
                        "out_of_scope": [],
                        "acceptance_criteria": [
                            "行为 A 会被执行",
                            "结果 A 可被验证",
                            "失败 A 可被观测"
                        ],
                        "dependencies": [],
                        "priority": "high",
                        "risk": "medium",
                        "test_focus": ["A", "B", "C"],
                        "implementation_hints": [],
                    }
                ],
            }
            orchestrator = RequirementAnalysisOrchestrator()
            settings = type("SettingsProxy", (), {})()
            # Reuse the real factory path through the orchestrator's service builder.
            from tdd_agent_framework.agents.requirement_analysis import RequirementAnalysisAgentSettings

            runtime_settings = RequirementAnalysisAgentSettings.from_dict(
                {
                    "enabled": True,
                    "provider_kind": "openai_compatible",
                    "provider_name": "openai",
                    "model": "gpt-test",
                    "api_base": "https://api.openai.com/v1",
                    "api_key": "secret-key",
                }
            )

            # Replace the built agent with a static provider by monkeypatching the factory target.
            agent = RequirementAnalysisAgent(
                provider=StaticProvider(payload),
                model_target=ModelTarget(provider="openai", model="gpt-test"),
            )

            async def fake_run(settings, analysis_input):
                enriched = orchestrator._build_workspace_summary(analysis_input)
                result = await agent.run(
                    RequirementAnalysisInput(
                        task_id=analysis_input.task_id,
                        mode=analysis_input.mode,
                        user_prompt=analysis_input.user_prompt,
                        repo_root=analysis_input.repo_root,
                        workspace_summary=enriched,
                        active_file=analysis_input.active_file,
                        selection=analysis_input.selection,
                        open_files=analysis_input.open_files,
                        diagnostics=analysis_input.diagnostics,
                        recent_test_failures=analysis_input.recent_test_failures,
                        git_diff_summary=analysis_input.git_diff_summary,
                        execution_constraints=analysis_input.execution_constraints,
                    ),
                    context=type("Ctx", (), {"task_id": analysis_input.task_id, "trace_id": None, "metadata": {}})(),
                )
                return result, enriched

            analysis_input = RequirementAnalysisInput(
                task_id="task_001",
                mode="repo_chat",
                user_prompt="修复并拆解需求",
                repo_root=str(root),
                workspace_summary=WorkspaceSummary(),
                execution_constraints=ExecutionConstraints(),
            )

            result, enriched = asyncio.run(fake_run(runtime_settings, analysis_input))

            self.assertIn("python", enriched.languages)
            self.assertIn("pytest", enriched.frameworks)
            self.assertIn("app", enriched.key_modules)
            self.assertEqual(result.analysis_summary.story_unit_count, 1)

    def test_orchestrator_revises_once_before_approval(self) -> None:
        orchestrator = RequirementAnalysisOrchestrator()

        analysis_result_first = self._make_analysis_result("初稿问题陈述", "story_draft")
        analysis_result_second = self._make_analysis_result("修订后问题陈述", "story_final")
        verification_revise = RequirementVerificationResult(
            status="revise",
            summary="初稿缺少可交付边界，需要收缩 story 范围。",
            issues=[
                VerificationIssue(
                    id="issue_001",
                    severity="high",
                    issue_type="over_scoped",
                    message="story 颗粒度过大，难以直接交给测试生成环节。",
                    affected_story_ids=["story_draft"],
                )
            ],
            revision_guidance=["将功能拆成单一可测试的最小 story 单元。"],
            quality_score=VerificationQualityScore(
                scope_clarity=62,
                testability=58,
                dependency_sanity=80,
                story_granularity=40,
            ),
        )
        verification_pass = RequirementVerificationResult(
            status="pass",
            summary="story 已收敛到可测试粒度，可以进入下一环。",
            issues=[],
            revision_guidance=[],
            quality_score=VerificationQualityScore(
                scope_clarity=90,
                testability=92,
                dependency_sanity=94,
                story_granularity=88,
            ),
        )

        class FakeAnalysisService:
            def __init__(self) -> None:
                self.calls = 0

            async def analyze(self, analysis_input, trace_id=None, metadata=None):
                self.calls += 1
                if self.calls == 1:
                    return analysis_result_first
                self.last_input = analysis_input
                return analysis_result_second

        class FakeVerificationService:
            def __init__(self) -> None:
                self.calls = 0

            async def verify(self, verification_input, trace_id=None, metadata=None):
                self.calls += 1
                if self.calls == 1:
                    return verification_revise
                return verification_pass

        class FakeCompositionVerificationService:
            def __init__(self) -> None:
                self.calls = 0

            async def verify(self, verification_input, trace_id=None, metadata=None):
                self.calls += 1
                return RequirementCompositionVerificationResult(
                    status="pass",
                    summary="story 组合已形成完整闭环。",
                    coverage_assessment=CompositionCoverageAssessment(
                        covers_primary_user_goal=True,
                        covers_permission_constraints=True,
                        covers_failure_handling=True,
                        covers_end_to_end_flow=True,
                    ),
                    composition_issues=[],
                    integration_test_scenarios=[],
                    redundant_story_ids=[],
                    missing_story_topics=[],
                    revision_guidance=[],
                )

        analysis_service = FakeAnalysisService()
        verification_service = FakeVerificationService()
        composition_verification_service = FakeCompositionVerificationService()

        analysis_input = RequirementAnalysisInput(
            task_id="task_001",
            mode="repo_chat",
            user_prompt="拆解 todo-list app 需求",
            repo_root="/workspace/project",
            workspace_summary=WorkspaceSummary(),
            execution_constraints=ExecutionConstraints(),
        )
        settings = object()

        with (
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_analysis_service",
                return_value=analysis_service,
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_verification_service",
                return_value=verification_service,
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_composition_verification_service",
                return_value=composition_verification_service,
            ),
        ):
            package = asyncio.run(orchestrator.run(settings, analysis_input))

        self.assertEqual(package.status, "paused_content_verified")
        self.assertEqual(package.iteration_count, 2)
        self.assertEqual(package.history[0].verification_status, "revise")
        self.assertEqual(package.history[1].verification_status, "pass")
        self.assertEqual(package.story_units[0].id, "story_final")
        self.assertEqual(analysis_service.calls, 2)
        self.assertEqual(verification_service.calls, 2)
        self.assertEqual(composition_verification_service.calls, 0)
        self.assertIsNone(package.composition_verification)
        self.assertEqual(
            analysis_service.last_input.revision_focus,
            ["将功能拆成单一可测试的最小 story 单元。"],
        )
        self.assertEqual(
            analysis_service.last_input.previous_verification_summary,
            "初稿缺少可交付边界，需要收缩 story 范围。",
        )

    def test_orchestrator_pauses_on_format_invalid_analysis_output(self) -> None:
        orchestrator = RequirementAnalysisOrchestrator()

        class FakeAnalysisService:
            async def analyze(self, analysis_input, trace_id=None, metadata=None):
                raise ValueError("story_units must be a non-empty list")

        class FakeVerificationService:
            async def verify(self, verification_input, trace_id=None, metadata=None):
                raise AssertionError("verification should not run after format validation fails")

        analysis_input = RequirementAnalysisInput(
            task_id="task_001",
            mode="repo_chat",
            user_prompt="拆解任务导出需求",
            repo_root="/workspace/project",
            workspace_summary=WorkspaceSummary(),
            execution_constraints=ExecutionConstraints(),
        )

        with (
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_analysis_service",
                return_value=FakeAnalysisService(),
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_verification_service",
                return_value=FakeVerificationService(),
            ),
        ):
            package = asyncio.run(orchestrator.run(object(), analysis_input))

        self.assertEqual(package.status, "paused_format_invalid")
        self.assertEqual(package.verification.status, "blocked")
        self.assertIn("story_units must be a non-empty list", package.verification.summary)
        self.assertEqual(package.story_units[0].id, "format_invalid_placeholder")

    def test_orchestrator_pauses_when_revision_never_converges(self) -> None:
        orchestrator = RequirementAnalysisOrchestrator()
        revise_result = RequirementVerificationResult(
            status="revise",
            summary="仍有中等严重度问题未收敛。",
            issues=[
                VerificationIssue(
                    id="issue_retry",
                    severity="medium",
                    issue_type="untestable_ac",
                    message="验收标准仍不够单义。",
                    affected_story_ids=["story_draft"],
                )
            ],
            revision_guidance=["进一步收敛 AC 语义，确保唯一预期结果。"],
            quality_score=VerificationQualityScore(
                scope_clarity=76,
                testability=64,
                dependency_sanity=90,
                story_granularity=72,
            ),
        )

        class FakeAnalysisService:
            def __init__(self) -> None:
                self.calls = 0

            async def analyze(self, analysis_input, trace_id=None, metadata=None):
                self.calls += 1
                return self._make_result()

            def _make_result(self):
                return RequirementAnalysisResult(
                    requirement_spec=RequirementSpec(
                        task_id="task_001",
                        version=1,
                        problem_statement="需要收敛 AC",
                        product_goal="让 story 变得可测试",
                        scope=["scope_a"],
                        out_of_scope=[],
                        constraints=[],
                        assumptions=[],
                        interfaces_or_contracts=[],
                        acceptance_criteria=[
                            "系统会完成行为",
                            "测试可以验证行为结果",
                            "失败路径有清晰输出",
                        ],
                        decomposition_strategy="按最小行为拆分",
                    ),
                    story_units=[
                        StoryUnit(
                            id="story_draft",
                            story_kind="user_outcome",
                            title="注册用户可以完成当前收敛后的单一业务目标",
                            as_a="注册用户",
                            when_context="我正在执行需要收敛 AC 的业务流程",
                            i_want="完成当前收敛后的单一业务目标",
                            so_that="我可以继续推进当前流程",
                            narrative="作为注册用户，当我正在执行需要收敛 AC 的业务流程时，我希望完成当前收敛后的单一业务目标，从而我可以继续推进当前流程。",
                            actor="注册用户",
                            goal="完成当前收敛后的单一业务目标",
                            business_value="我可以继续推进当前流程",
                            business_outcome="用户可以稳定完成当前单一业务目标",
                            scope=["scope_a"],
                            out_of_scope=[],
                            acceptance_criteria=[
                                "行为会被执行",
                                "结果会被验证",
                                "失败会被观测",
                            ],
                            dependencies=[],
                            priority="high",
                            risk="medium",
                            test_focus=["A", "B", "C"],
                            implementation_hints=[],
                        )
                    ],
                    analysis_summary=AnalysisSummary(
                        story_unit_count=1,
                        high_priority_count=1,
                        high_risk_count=0,
                    ),
                    warnings=[],
                    quality_checks=QualityChecks(
                        has_clear_scope=True,
                        has_testable_ac=True,
                        dependency_graph_valid=True,
                        story_count_within_limit=True,
                    ),
                )

        class FakeVerificationService:
            def __init__(self) -> None:
                self.calls = 0

            async def verify(self, verification_input, trace_id=None, metadata=None):
                self.calls += 1
                return revise_result

        class FakeCompositionVerificationService:
            def __init__(self) -> None:
                self.calls = 0

            async def verify(self, verification_input, trace_id=None, metadata=None):
                self.calls += 1
                raise AssertionError("composition verification should not run before requirement verification passes")

        analysis_service = FakeAnalysisService()
        verification_service = FakeVerificationService()
        composition_verification_service = FakeCompositionVerificationService()

        analysis_input = RequirementAnalysisInput(
            task_id="task_001",
            mode="repo_chat",
            user_prompt="拆解论坛系统需求",
            repo_root="/workspace/project",
            workspace_summary=WorkspaceSummary(),
            execution_constraints=ExecutionConstraints(),
        )

        with (
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_analysis_service",
                return_value=analysis_service,
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_verification_service",
                return_value=verification_service,
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_composition_verification_service",
                return_value=composition_verification_service,
            ),
        ):
            package = asyncio.run(orchestrator.run(object(), analysis_input))

        self.assertEqual(package.status, "paused_stalled")
        self.assertEqual(package.iteration_count, orchestrator.max_auto_revision_iterations)
        self.assertEqual(package.verification.status, "revise")
        self.assertEqual(analysis_service.calls, orchestrator.max_auto_revision_iterations)
        self.assertEqual(verification_service.calls, orchestrator.max_auto_revision_iterations)
        self.assertEqual(composition_verification_service.calls, 0)
        self.assertGreater(package.verification_gate_summary["blocking_issue_count"], 0)
        self.assertTrue(package.user_review_guidance["clarification_questions"])

    def test_orchestrator_runs_composition_review_from_previous_result_snapshot(self) -> None:
        orchestrator = RequirementAnalysisOrchestrator()

        previous_result = self._make_analysis_result("已通过内容审核的问题陈述", "story_final")
        composition_pass = RequirementCompositionVerificationResult(
            status="pass",
            summary="story 组合已形成完整闭环。",
            coverage_assessment=CompositionCoverageAssessment(
                covers_primary_user_goal=True,
                covers_permission_constraints=True,
                covers_failure_handling=True,
                covers_end_to_end_flow=True,
            ),
            composition_issues=[],
            integration_test_scenarios=[],
            redundant_story_ids=[],
            missing_story_topics=[],
            revision_guidance=[],
        )

        class FakeAnalysisService:
            def __init__(self) -> None:
                self.calls = 0

        class FakeVerificationService:
            def __init__(self) -> None:
                self.calls = 0

        class FakeCompositionVerificationService:
            def __init__(self) -> None:
                self.calls = 0
                self.last_input = None

            async def verify(self, verification_input, trace_id=None, metadata=None):
                self.calls += 1
                self.last_input = verification_input
                return composition_pass

        analysis_service = FakeAnalysisService()
        verification_service = FakeVerificationService()
        composition_verification_service = FakeCompositionVerificationService()

        analysis_input = RequirementAnalysisInput(
            task_id="task_001",
            mode="repo_chat",
            user_prompt="拆解任务导出需求",
            repo_root="/workspace/project",
            workspace_summary=WorkspaceSummary(),
            analysis_goal="composition_review",
            iteration=2,
            previous_analysis_result={
                "requirement_spec": previous_result.requirement_spec.__dict__,
                "story_units": [story.__dict__ for story in previous_result.story_units],
                "capability_groups": [group.__dict__ for group in previous_result.capability_groups],
                "warnings": previous_result.warnings,
                "quality_checks": previous_result.quality_checks.__dict__,
            },
            execution_constraints=ExecutionConstraints(),
        )

        with (
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_analysis_service",
                return_value=analysis_service,
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_verification_service",
                return_value=verification_service,
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_composition_verification_service",
                return_value=composition_verification_service,
            ),
        ):
            package = asyncio.run(orchestrator.run(object(), analysis_input))

        self.assertEqual(package.status, "paused_converged")
        self.assertEqual(package.iteration_count, 2)
        self.assertEqual(analysis_service.calls, 0)
        self.assertEqual(verification_service.calls, 0)
        self.assertEqual(composition_verification_service.calls, 1)
        self.assertIsNotNone(package.composition_verification)
        self.assertEqual(package.composition_verification.status, "pass")
        self.assertEqual(composition_verification_service.last_input.analysis_result.story_units[0].id, "story_final")

    def test_composition_review_synthesizes_missing_capability_groups_from_snapshot(self) -> None:
        orchestrator = RequirementAnalysisOrchestrator()

        previous_result = self._make_analysis_result("已通过内容审核的问题陈述", "story_final")
        composition_pass = RequirementCompositionVerificationResult(
            status="pass",
            summary="story 组合已形成完整闭环。",
            coverage_assessment=CompositionCoverageAssessment(
                covers_primary_user_goal=True,
                covers_permission_constraints=True,
                covers_failure_handling=True,
                covers_end_to_end_flow=True,
            ),
            composition_issues=[],
            integration_test_scenarios=[],
            redundant_story_ids=[],
            missing_story_topics=[],
            revision_guidance=[],
        )

        class FakeAnalysisService:
            def __init__(self) -> None:
                self.calls = 0

        class FakeVerificationService:
            def __init__(self) -> None:
                self.calls = 0

        class FakeCompositionVerificationService:
            def __init__(self) -> None:
                self.calls = 0
                self.last_input = None

            async def verify(self, verification_input, trace_id=None, metadata=None):
                self.calls += 1
                self.last_input = verification_input
                return composition_pass

        analysis_service = FakeAnalysisService()
        verification_service = FakeVerificationService()
        composition_verification_service = FakeCompositionVerificationService()

        analysis_input = RequirementAnalysisInput(
            task_id="task_001",
            mode="repo_chat",
            user_prompt="拆解任务导出需求",
            repo_root="/workspace/project",
            workspace_summary=WorkspaceSummary(),
            analysis_goal="composition_review",
            iteration=2,
            previous_analysis_result={
                "requirement_spec": previous_result.requirement_spec.__dict__,
                "story_units": [story.__dict__ for story in previous_result.story_units],
                "warnings": previous_result.warnings,
                "quality_checks": previous_result.quality_checks.__dict__,
            },
            execution_constraints=ExecutionConstraints(),
        )

        with (
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_analysis_service",
                return_value=analysis_service,
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_verification_service",
                return_value=verification_service,
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_composition_verification_service",
                return_value=composition_verification_service,
            ),
        ):
            package = asyncio.run(orchestrator.run(object(), analysis_input))

        self.assertEqual(package.status, "paused_converged")
        self.assertEqual(analysis_service.calls, 0)
        self.assertEqual(verification_service.calls, 0)
        self.assertEqual(composition_verification_service.calls, 1)
        fallback_groups = composition_verification_service.last_input.analysis_result.capability_groups
        self.assertEqual(len(fallback_groups), 1)
        self.assertEqual(fallback_groups[0].story_ids, ["story_final"])
        self.assertIn("capability_groups 缺失", package.warnings[0])

    def test_composition_revision_updates_stories_then_runs_content_and_composition_checks(self) -> None:
        orchestrator = RequirementAnalysisOrchestrator()

        previous_result = self._make_analysis_result("组合验证前的问题陈述", "story_before")
        revised_result = self._make_analysis_result("组合修订后的问题陈述", "story_after")
        verification_pass = RequirementVerificationResult(
            status="pass",
            summary="组合修订后的单条 story 质量已达标。",
            issues=[],
            revision_guidance=[],
            quality_score=VerificationQualityScore(
                scope_clarity=92,
                testability=92,
                dependency_sanity=92,
                story_granularity=90,
            ),
        )
        composition_pass = RequirementCompositionVerificationResult(
            status="pass",
            summary="组合修订后已形成完整闭环。",
            coverage_assessment=CompositionCoverageAssessment(
                covers_primary_user_goal=True,
                covers_permission_constraints=True,
                covers_failure_handling=True,
                covers_end_to_end_flow=True,
            ),
            composition_issues=[],
            integration_test_scenarios=[],
            redundant_story_ids=[],
            missing_story_topics=[],
            revision_guidance=[],
        )

        class FakeAnalysisService:
            def __init__(self) -> None:
                self.calls = 0
                self.last_input = None

            async def analyze(self, analysis_input, trace_id=None, metadata=None):
                self.calls += 1
                self.last_input = analysis_input
                return revised_result

        class FakeVerificationService:
            def __init__(self) -> None:
                self.calls = 0
                self.last_input = None

            async def verify(self, verification_input, trace_id=None, metadata=None):
                self.calls += 1
                self.last_input = verification_input
                return verification_pass

        class FakeCompositionVerificationService:
            def __init__(self) -> None:
                self.calls = 0
                self.last_input = None

            async def verify(self, verification_input, trace_id=None, metadata=None):
                self.calls += 1
                self.last_input = verification_input
                return composition_pass

        analysis_service = FakeAnalysisService()
        verification_service = FakeVerificationService()
        composition_verification_service = FakeCompositionVerificationService()
        previous_composition_verification = RequirementCompositionVerificationResult(
            status="revise",
            summary="缺少完整端到端闭环。",
            coverage_assessment=CompositionCoverageAssessment(
                covers_primary_user_goal=True,
                covers_permission_constraints=False,
                covers_failure_handling=False,
                covers_end_to_end_flow=False,
            ),
            composition_issues=[
                CompositionIssue(
                    id="composition_issue_001",
                    severity="medium",
                    issue_type="missing_story",
                    message="缺少失败反馈 story。",
                    related_story_ids=["story_before"],
                    related_capability_group_ids=["capability_group_1"],
                    suggested_action="补充失败反馈闭环",
                )
            ],
            integration_test_scenarios=[],
            redundant_story_ids=[],
            missing_story_topics=["失败反馈"],
            revision_guidance=["补充失败反馈闭环"],
        )

        analysis_input = RequirementAnalysisInput(
            task_id="task_001",
            mode="repo_chat",
            user_prompt="拆解任务导出需求",
            repo_root="/workspace/project",
            workspace_summary=WorkspaceSummary(),
            analysis_goal="composition_revision",
            iteration=3,
            previous_verification_summary=previous_composition_verification.summary,
            revision_focus=list(previous_composition_verification.revision_guidance),
            previous_analysis_result={
                "requirement_spec": previous_result.requirement_spec.__dict__,
                "story_units": [story.__dict__ for story in previous_result.story_units],
                "capability_groups": [group.__dict__ for group in previous_result.capability_groups],
                "warnings": previous_result.warnings,
                "quality_checks": previous_result.quality_checks.__dict__,
                "composition_verification": previous_composition_verification.__dict__,
            },
            execution_constraints=ExecutionConstraints(),
        )

        with (
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_analysis_service",
                return_value=analysis_service,
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_verification_service",
                return_value=verification_service,
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_composition_verification_service",
                return_value=composition_verification_service,
            ),
        ):
            package = asyncio.run(orchestrator.run(object(), analysis_input))

        self.assertEqual(package.status, "paused_converged")
        self.assertEqual(analysis_service.calls, 1)
        self.assertEqual(verification_service.calls, 1)
        self.assertEqual(composition_verification_service.calls, 1)
        self.assertEqual(analysis_service.last_input.analysis_goal, "composition_revision")
        self.assertEqual(analysis_service.last_input.revision_focus, ["补充失败反馈闭环"])
        self.assertEqual(composition_verification_service.last_input.analysis_result.story_units[0].id, "story_after")
        self.assertEqual(package.composition_verification.status, "pass")

    def test_content_verified_package_includes_review_summary(self) -> None:
        orchestrator = RequirementAnalysisOrchestrator()
        analysis_result = self._make_analysis_result("已通过内容审核的问题陈述", "story_final")
        verification_pass = RequirementVerificationResult(
            status="pass",
            summary="单条 story 质量已达标。",
            issues=[],
            revision_guidance=[],
            quality_score=VerificationQualityScore(
                scope_clarity=90,
                testability=92,
                dependency_sanity=94,
                story_granularity=88,
            ),
        )

        class FakeAnalysisService:
            async def analyze(self, analysis_input, trace_id=None, metadata=None):
                return analysis_result

        class FakeVerificationService:
            async def verify(self, verification_input, trace_id=None, metadata=None):
                return verification_pass

        analysis_input = RequirementAnalysisInput(
            task_id="task_001",
            mode="repo_chat",
            user_prompt="拆解任务导出需求",
            repo_root="/workspace/project",
            workspace_summary=WorkspaceSummary(),
            execution_constraints=ExecutionConstraints(),
        )

        with (
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_analysis_service",
                return_value=FakeAnalysisService(),
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_verification_service",
                return_value=FakeVerificationService(),
            ),
        ):
            package = asyncio.run(orchestrator.run(object(), analysis_input))

        self.assertEqual(package.status, "paused_content_verified")
        self.assertEqual(package.verification_gate_summary["blocking_issue_count"], 0)
        self.assertTrue(package.user_review_guidance["summary_points"])
        self.assertTrue(package.user_review_guidance["suggestions"])

    def test_continuation_keeps_same_task_id(self) -> None:
        orchestrator = RequirementAnalysisOrchestrator()
        analysis_result_first = self._make_analysis_result("初稿问题陈述", "story_draft")
        analysis_result_second = self._make_analysis_result("修订后问题陈述", "story_final")

        verification_revise = RequirementVerificationResult(
            status="revise",
            summary="需要继续优化。",
            issues=[
                VerificationIssue(
                    id="issue_001",
                    severity="medium",
                    issue_type="over_scoped",
                    message="需要继续收敛。",
                    affected_story_ids=["story_draft"],
                )
            ],
            revision_guidance=["继续收敛范围"],
            quality_score=VerificationQualityScore(
                scope_clarity=70,
                testability=70,
                dependency_sanity=80,
                story_granularity=70,
            ),
        )
        verification_pass = RequirementVerificationResult(
            status="pass",
            summary="已通过。",
            issues=[],
            revision_guidance=[],
            quality_score=VerificationQualityScore(
                scope_clarity=90,
                testability=90,
                dependency_sanity=90,
                story_granularity=90,
            ),
        )

        class FakeAnalysisService:
            def __init__(self) -> None:
                self.calls = 0
                self.task_ids: list[str] = []

            async def analyze(self, analysis_input, trace_id=None, metadata=None):
                self.calls += 1
                self.task_ids.append(analysis_input.task_id)
                return analysis_result_first if self.calls == 1 else analysis_result_second

        class FakeVerificationService:
            def __init__(self) -> None:
                self.calls = 0

            async def verify(self, verification_input, trace_id=None, metadata=None):
                self.calls += 1
                return verification_revise if self.calls == 1 else verification_pass

        class FakeCompositionVerificationService:
            async def verify(self, verification_input, trace_id=None, metadata=None):
                return RequirementCompositionVerificationResult(
                    status="pass",
                    summary="通过。",
                    coverage_assessment=CompositionCoverageAssessment(
                        covers_primary_user_goal=True,
                        covers_permission_constraints=True,
                        covers_failure_handling=True,
                        covers_end_to_end_flow=True,
                    ),
                    composition_issues=[],
                    integration_test_scenarios=[],
                    redundant_story_ids=[],
                    missing_story_topics=[],
                    revision_guidance=[],
                )

        analysis_service = FakeAnalysisService()
        verification_service = FakeVerificationService()
        composition_verification_service = FakeCompositionVerificationService()
        analysis_input = RequirementAnalysisInput(
            task_id="task_001",
            mode="repo_chat",
            user_prompt="拆解任务导出需求",
            repo_root="/workspace/project",
            workspace_summary=WorkspaceSummary(),
            execution_constraints=ExecutionConstraints(),
        )

        with (
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_analysis_service",
                return_value=analysis_service,
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_verification_service",
                return_value=verification_service,
            ),
            patch(
                "tdd_agent_framework.orchestrators.requirement_analysis.build_requirement_composition_verification_service",
                return_value=composition_verification_service,
            ),
        ):
            asyncio.run(orchestrator.run(object(), analysis_input))

        self.assertEqual(analysis_service.task_ids, ["task_001", "task_001"])

    def _make_analysis_result(self, problem_statement: str, story_id: str) -> RequirementAnalysisResult:
        return RequirementAnalysisResult(
            requirement_spec=RequirementSpec(
                task_id="task_001",
                version=1,
                problem_statement=problem_statement,
                product_goal="产出可测试 story",
                scope=["scope_a"],
                out_of_scope=[],
                constraints=[],
                assumptions=[],
                interfaces_or_contracts=[],
                acceptance_criteria=[
                    "系统会产出结构化 story",
                    "story 可被测试环节消费",
                    "范围边界明确可验证",
                ],
                decomposition_strategy="按最小可测试单元拆分",
            ),
            story_units=[
                StoryUnit(
                    id=story_id,
                    story_kind="user_outcome",
                    title="注册用户可以完成当前版本的单一业务目标",
                    as_a="注册用户",
                    when_context="我正在执行当前版本需要覆盖的业务流程",
                    i_want="完成当前版本的单一业务目标",
                    so_that="我可以继续推进当前业务流程",
                    narrative="作为注册用户，当我正在执行当前版本需要覆盖的业务流程时，我希望完成当前版本的单一业务目标，从而我可以继续推进当前业务流程。",
                    actor="注册用户",
                    goal="完成当前版本的单一业务目标",
                    business_value="我可以继续推进当前业务流程",
                    business_outcome="用户可以稳定完成当前版本的单一业务动作",
                    scope=["scope_a"],
                    out_of_scope=[],
                    acceptance_criteria=[
                        "行为会被执行",
                        "结果会被验证",
                        "失败会被观测",
                    ],
                    dependencies=[],
                    priority="high",
                    risk="medium",
                    test_focus=["A", "B", "C"],
                    implementation_hints=[],
                )
            ],
            analysis_summary=AnalysisSummary(
                story_unit_count=1,
                high_priority_count=1,
                high_risk_count=0,
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
                    id="capability_group_1",
                    title="整体需求分组",
                    goal="保留最小能力分层结构",
                    scope=["scope_a"],
                    story_ids=[story_id],
                    priority="high",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
