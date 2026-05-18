from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from tdd_agent_framework.core import ProgressCallback, RunProgressEvent, emit_progress
from tdd_agent_framework.agents.requirement_analysis import (
    RequirementAnalysisIteration,
    RequirementAnalysisAgentSettings,
    RequirementAnalysisInput,
    RequirementAnalysisPackage,
    RequirementAnalysisResult,
    RequirementSpec,
    RequirementVerificationResult,
    StoryUnit,
    QualityChecks,
    AnalysisSummary,
    CapabilityGroup,
    VerificationQualityScore,
    build_requirement_analysis_service,
)
from tdd_agent_framework.agents.requirement_composition_verification import (
    RequirementCompositionVerificationInput,
    RequirementCompositionVerificationResult,
    build_requirement_composition_verification_service,
)
from tdd_agent_framework.agents.requirement_verification import (
    RequirementVerificationInput,
    build_requirement_verification_service,
)


KNOWN_FRAMEWORK_MARKERS = {
    "package.json": "node",
    "pnpm-lock.yaml": "pnpm",
    "package-lock.json": "npm",
    "yarn.lock": "yarn",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "pytest.ini": "pytest",
    "manage.py": "django",
    "Cargo.toml": "rust",
    "go.mod": "go",
}

KNOWN_DIR_FRAMEWORKS = {
    "app": "fastapi",
    "src": "typescript",
    "tests": "pytest",
}

EXTENSION_LANGUAGES = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
}


class RequirementAnalysisOrchestrator:
    max_auto_revision_iterations = 2

    def __init__(self) -> None:
        self.name = "requirement_analysis_orchestrator"

    async def run(
        self,
        settings: RequirementAnalysisAgentSettings,
        analysis_input: RequirementAnalysisInput,
        progress_callback: ProgressCallback | None = None,
    ) -> RequirementAnalysisPackage:
        if analysis_input.analysis_goal == "composition_review":
            return await self._run_composition_review_only(settings, analysis_input, progress_callback)
        if analysis_input.analysis_goal == "composition_revision":
            return await self._run_composition_revision(settings, analysis_input, progress_callback)

        await emit_progress(
            progress_callback,
            RunProgressEvent(
                type="status",
                stage="building_workspace_summary",
                message="正在整理工作区摘要和上下文",
                metadata={"repo_root": analysis_input.repo_root},
            ),
        )
        enriched_input = replace(
            analysis_input,
            workspace_summary=self._build_workspace_summary(analysis_input),
        )
        await emit_progress(
            progress_callback,
            RunProgressEvent(
                type="status",
                stage="workspace_summary_ready",
                message="工作区摘要已就绪，开始请求需求分析模型",
                metadata={
                    "languages": enriched_input.workspace_summary.languages,
                    "frameworks": enriched_input.workspace_summary.frameworks,
                    "key_modules": enriched_input.workspace_summary.key_modules,
                },
            ),
        )
        service = build_requirement_analysis_service(
            settings,
            progress_callback=progress_callback,
        )
        verification_service = build_requirement_verification_service(
            settings,
            progress_callback=progress_callback,
        )

        history: list[RequirementAnalysisIteration] = []
        working_input = enriched_input
        latest_result: RequirementAnalysisResult | None = None
        latest_verification: RequirementVerificationResult | None = None
        current_iteration = max(1, working_input.iteration)

        while True:
            iteration = current_iteration
            working_input = replace(working_input, iteration=iteration)
            await emit_progress(
                progress_callback,
                RunProgressEvent(
                    type="status",
                    stage="analysis_iteration_started",
                    message=f"开始第 {iteration} 轮需求分析",
                    metadata={"iteration": iteration},
                ),
            )
            try:
                latest_result = await service.analyze(
                    working_input,
                    metadata={"orchestrator": self.name, "iteration": str(iteration)},
                )
            except ValueError as error:
                return self._build_format_invalid_package(working_input, error)
            await emit_progress(
                progress_callback,
                RunProgressEvent(
                    type="status",
                    stage="verification_iteration_started",
                    message=f"开始第 {iteration} 轮需求验证",
                    metadata={"iteration": iteration, "story_unit_count": len(latest_result.story_units)},
                ),
            )
            latest_verification = await verification_service.verify(
                RequirementVerificationInput(
                    analysis_input=working_input,
                    analysis_result=latest_result,
                    iteration=iteration,
                ),
                metadata={"orchestrator": self.name, "iteration": str(iteration)},
            )

            await emit_progress(
                progress_callback,
                RunProgressEvent(
                    type="status",
                    stage="verification_iteration_completed",
                    message=f"第 {iteration} 轮验证结果：{latest_verification.status}",
                    metadata={
                        "iteration": iteration,
                        "verification_status": latest_verification.status,
                        "issue_count": len(latest_verification.issues),
                    },
                ),
            )

            if latest_verification.status == "pass":
                history.append(
                    RequirementAnalysisIteration(
                        iteration=iteration,
                        analysis_summary=latest_result.requirement_spec.problem_statement,
                        verification_status=latest_verification.status,
                        issue_count=len(latest_verification.issues),
                        revision_guidance=list(latest_verification.revision_guidance),
                    )
                )
                return self._build_package(
                    task_id=working_input.task_id,
                    status="paused_content_verified",
                    result=latest_result,
                    verification=latest_verification,
                    composition_verification=None,
                    history=history,
                    analysis_input=working_input,
                )

            history.append(
                RequirementAnalysisIteration(
                    iteration=iteration,
                    analysis_summary=latest_result.requirement_spec.problem_statement,
                    verification_status=latest_verification.status,
                    issue_count=len(latest_verification.issues),
                    revision_guidance=list(latest_verification.revision_guidance),
                )
            )

            if latest_verification.status == "blocked":
                return self._build_package(
                    task_id=working_input.task_id,
                    status="paused_blocked",
                    result=latest_result,
                    verification=latest_verification,
                    composition_verification=None,
                    history=history,
                    analysis_input=working_input,
                )

            if len(history) >= self.max_auto_revision_iterations:
                await emit_progress(
                    progress_callback,
                    RunProgressEvent(
                        type="status",
                        stage="analysis_revision_paused",
                        message=f"第 {iteration} 轮仍需修订，已暂停等待用户审核或继续优化",
                        metadata={
                            "iteration": iteration,
                            "revision_guidance": self._next_revision_focus(latest_verification),
                        },
                    ),
                )
                return self._build_package(
                    task_id=working_input.task_id,
                    status="paused_stalled",
                    result=latest_result,
                    verification=latest_verification,
                    composition_verification=None,
                    history=history,
                    analysis_input=working_input,
                )

            await emit_progress(
                progress_callback,
                RunProgressEvent(
                    type="status",
                    stage="analysis_revision_requested",
                    message=f"第 {iteration} 轮需要修订，准备继续优化",
                    metadata={
                        "iteration": iteration,
                        "revision_guidance": self._next_revision_focus(
                            latest_verification,
                        ),
                    },
                ),
            )
            working_input = replace(
                working_input,
                revision_focus=self._next_revision_focus(
                    latest_verification,
                ),
                previous_verification_summary=self._overall_feedback_summary(
                    latest_verification,
                ),
            )
            current_iteration += 1

    async def _run_composition_review_only(
        self,
        settings: RequirementAnalysisAgentSettings,
        analysis_input: RequirementAnalysisInput,
        progress_callback: ProgressCallback | None = None,
    ) -> RequirementAnalysisPackage:
        latest_result = self._analysis_result_from_input_snapshot(analysis_input)
        latest_verification = self._content_review_passed_verification()
        iteration = max(1, analysis_input.iteration)
        latest_composition_verification = await self._verify_composition(
            settings,
            analysis_input,
            latest_result,
            iteration,
            progress_callback,
        )
        history = [
            RequirementAnalysisIteration(
                iteration=iteration,
                analysis_summary=latest_result.requirement_spec.problem_statement,
                verification_status=latest_verification.status,
                issue_count=0,
                revision_guidance=[],
                composition_verification_status=latest_composition_verification.status,
                composition_issue_count=len(latest_composition_verification.composition_issues),
                composition_revision_guidance=list(latest_composition_verification.revision_guidance),
            )
        ]
        if latest_composition_verification.status == "pass":
            status = "paused_converged"
        elif latest_composition_verification.status == "blocked":
            status = "paused_blocked"
        else:
            status = "paused_stalled"
        return self._build_package(
            task_id=analysis_input.task_id,
            status=status,
            result=latest_result,
            verification=latest_verification,
            composition_verification=latest_composition_verification,
            history=history,
            analysis_input=analysis_input,
        )

    async def _run_composition_revision(
        self,
        settings: RequirementAnalysisAgentSettings,
        analysis_input: RequirementAnalysisInput,
        progress_callback: ProgressCallback | None = None,
    ) -> RequirementAnalysisPackage:
        if not isinstance(analysis_input.previous_analysis_result, dict):
            raise ValueError("previous_analysis_result is required for composition_revision")

        await emit_progress(
            progress_callback,
            RunProgressEvent(
                type="status",
                stage="building_workspace_summary",
                message="正在整理工作区摘要和组合修订上下文",
                metadata={"repo_root": analysis_input.repo_root},
            ),
        )
        enriched_input = replace(
            analysis_input,
            workspace_summary=self._build_workspace_summary(analysis_input),
        )
        service = build_requirement_analysis_service(
            settings,
            progress_callback=progress_callback,
        )
        verification_service = build_requirement_verification_service(
            settings,
            progress_callback=progress_callback,
        )
        iteration = max(1, enriched_input.iteration)
        await emit_progress(
            progress_callback,
            RunProgressEvent(
                type="status",
                stage="composition_revision_started",
                message=f"开始第 {iteration} 轮组合问题驱动的需求修订",
                metadata={"iteration": iteration, "revision_focus": enriched_input.revision_focus},
            ),
        )
        try:
            latest_result = await service.analyze(
                enriched_input,
                metadata={"orchestrator": self.name, "iteration": str(iteration), "analysis_goal": "composition_revision"},
            )
        except ValueError as error:
            return self._build_format_invalid_package(enriched_input, error)

        await emit_progress(
            progress_callback,
            RunProgressEvent(
                type="status",
                stage="verification_iteration_started",
                message=f"开始第 {iteration} 轮组合修订后的单条 story 验证",
                metadata={"iteration": iteration, "story_unit_count": len(latest_result.story_units)},
            ),
        )
        latest_verification = await verification_service.verify(
            RequirementVerificationInput(
                analysis_input=enriched_input,
                analysis_result=latest_result,
                iteration=iteration,
            ),
            metadata={"orchestrator": self.name, "iteration": str(iteration), "analysis_goal": "composition_revision"},
        )
        await emit_progress(
            progress_callback,
            RunProgressEvent(
                type="status",
                stage="verification_iteration_completed",
                message=f"第 {iteration} 轮组合修订后的单条验证结果：{latest_verification.status}",
                metadata={
                    "iteration": iteration,
                    "verification_status": latest_verification.status,
                    "issue_count": len(latest_verification.issues),
                },
            ),
        )
        if latest_verification.status != "pass":
            history = [
                RequirementAnalysisIteration(
                    iteration=iteration,
                    analysis_summary=latest_result.requirement_spec.problem_statement,
                    verification_status=latest_verification.status,
                    issue_count=len(latest_verification.issues),
                    revision_guidance=list(latest_verification.revision_guidance),
                )
            ]
            return self._build_package(
                task_id=enriched_input.task_id,
                status="paused_blocked" if latest_verification.status == "blocked" else "paused_stalled",
                result=latest_result,
                verification=latest_verification,
                composition_verification=None,
                history=history,
                analysis_input=enriched_input,
            )

        latest_composition_verification = await self._verify_composition(
            settings,
            enriched_input,
            latest_result,
            iteration,
            progress_callback,
        )
        history = [
            RequirementAnalysisIteration(
                iteration=iteration,
                analysis_summary=latest_result.requirement_spec.problem_statement,
                verification_status=latest_verification.status,
                issue_count=len(latest_verification.issues),
                revision_guidance=list(latest_verification.revision_guidance),
                composition_verification_status=latest_composition_verification.status,
                composition_issue_count=len(latest_composition_verification.composition_issues),
                composition_revision_guidance=list(latest_composition_verification.revision_guidance),
            )
        ]
        if latest_composition_verification.status == "pass":
            status = "paused_converged"
        elif latest_composition_verification.status == "blocked":
            status = "paused_blocked"
        else:
            status = "paused_stalled"
        return self._build_package(
            task_id=enriched_input.task_id,
            status=status,
            result=latest_result,
            verification=latest_verification,
            composition_verification=latest_composition_verification,
            history=history,
            analysis_input=enriched_input,
        )

    async def _verify_composition(
        self,
        settings: RequirementAnalysisAgentSettings,
        analysis_input: RequirementAnalysisInput,
        latest_result: RequirementAnalysisResult,
        iteration: int,
        progress_callback: ProgressCallback | None,
    ) -> RequirementCompositionVerificationResult:
        composition_verification_service = build_requirement_composition_verification_service(
            settings,
            progress_callback=progress_callback,
        )
        await emit_progress(
            progress_callback,
            RunProgressEvent(
                type="status",
                stage="composition_verification_started",
                message=f"开始第 {iteration} 轮组合合理性验证",
                metadata={"iteration": iteration, "story_unit_count": len(latest_result.story_units)},
            ),
        )
        latest_composition_verification = await composition_verification_service.verify(
            RequirementCompositionVerificationInput(
                analysis_input=analysis_input,
                analysis_result=latest_result,
                iteration=iteration,
                session_id=f"{analysis_input.task_id}_composition_{iteration}",
            ),
            metadata={"orchestrator": self.name, "iteration": str(iteration)},
        )
        await emit_progress(
            progress_callback,
            RunProgressEvent(
                type="status",
                stage="composition_verification_completed",
                message=f"第 {iteration} 轮组合验证结果：{latest_composition_verification.status}",
                metadata={
                    "iteration": iteration,
                    "composition_verification_status": latest_composition_verification.status,
                    "composition_issue_count": len(latest_composition_verification.composition_issues),
                },
            ),
        )
        return latest_composition_verification

    def _build_workspace_summary(
        self,
        analysis_input: RequirementAnalysisInput,
    ):
        repo_root = Path(analysis_input.repo_root)
        existing = analysis_input.workspace_summary
        languages = set(existing.languages)
        frameworks = set(existing.frameworks)
        key_modules = set(existing.key_modules)

        if not repo_root.exists() or not repo_root.is_dir():
            return existing

        candidate_dirs = []
        try:
            candidate_dirs = [child for child in repo_root.iterdir() if child.is_dir()]
        except OSError:
            return existing

        for child in candidate_dirs:
            framework = KNOWN_DIR_FRAMEWORKS.get(child.name)
            if framework:
                frameworks.add(framework)
            if len(key_modules) < 8 and not child.name.startswith("."):
                key_modules.add(child.name)

        try:
            for child in repo_root.iterdir():
                framework = KNOWN_FRAMEWORK_MARKERS.get(child.name)
                if framework:
                    frameworks.add(framework)
        except OSError:
            pass

        try:
            for file_path in repo_root.rglob("*"):
                if not file_path.is_file():
                    continue
                language = EXTENSION_LANGUAGES.get(file_path.suffix)
                if language:
                    languages.add(language)
                if len(key_modules) >= 8 and len(languages) >= 6:
                    break
        except OSError:
            pass

        workspace_summary_type = type(existing)
        return workspace_summary_type(
            languages=sorted(languages),
            frameworks=sorted(frameworks),
            key_modules=sorted(key_modules)[:8],
        )

    def _build_package(
        self,
        task_id: str,
        status: str,
        result: RequirementAnalysisResult,
        verification: RequirementVerificationResult,
        composition_verification: RequirementCompositionVerificationResult | None,
        history: list[RequirementAnalysisIteration],
        analysis_input: RequirementAnalysisInput | None = None,
    ) -> RequirementAnalysisPackage:
        return RequirementAnalysisPackage(
            package_id=f"ra_pkg_{uuid4().hex[:8]}",
            task_id=task_id,
            status=status,
            requirement_spec=result.requirement_spec,
            story_units=result.story_units,
            analysis_summary=result.analysis_summary,
            warnings=result.warnings,
            quality_checks=result.quality_checks,
            verification=verification,
            composition_verification=composition_verification,
            iteration_count=history[-1].iteration if history else 0,
            history=list(history),
            verification_gate_summary=self._build_verification_gate_summary(
                analysis_input,
                status,
                result,
                verification,
            ),
            user_review_guidance=self._build_user_review_guidance(
                analysis_input,
                status,
                result,
                verification,
            ),
        )

    def _build_verification_gate_summary(
        self,
        analysis_input: RequirementAnalysisInput | None,
        status: str,
        result: RequirementAnalysisResult,
        verification: RequirementVerificationResult,
    ) -> dict[str, object]:
        blocking_issues = [issue for issue in verification.issues if self._is_blocking_issue(issue.severity, issue.issue_type)]
        nonblocking_issue_count = max(0, len(verification.issues) - len(blocking_issues))
        coverage = self._explicit_capability_coverage(analysis_input, result)
        if status in {"paused_content_verified", "paused_converged"}:
            decision_reason = "阻塞问题已清零，显式能力覆盖达到门槛，当前结果适合进入用户审核。"
        elif status == "paused_stalled":
            decision_reason = "已达到自动修订轮数上限，仍有待确认问题，暂停等待用户判断或补充答案。"
        elif status == "paused_blocked":
            decision_reason = "存在阻塞问题或缺少关键前提，需用户补充后再继续。"
        elif status == "paused_format_invalid":
            decision_reason = "模型输出未通过格式校验，需重试或人工补充说明。"
        else:
            decision_reason = "当前需求分析已生成，建议结合门禁摘要进行审核。"
        return {
            "blocking_issue_count": len(blocking_issues),
            "nonblocking_suggestion_count": nonblocking_issue_count + len(verification.revision_guidance),
            "explicit_capability_coverage": coverage,
            "decision_reason": decision_reason,
        }

    def _build_user_review_guidance(
        self,
        analysis_input: RequirementAnalysisInput | None,
        status: str,
        result: RequirementAnalysisResult,
        verification: RequirementVerificationResult,
    ) -> dict[str, list[str]]:
        summary_points = [
            f"目标：{result.requirement_spec.product_goal}",
            f"范围：{ '、'.join(result.requirement_spec.scope[:4]) }",
            f"当前拆分为 {len(result.capability_groups)} 个能力组、{len(result.story_units)} 条 user story。",
        ]
        suggestions = list(verification.revision_guidance[:3])
        if not suggestions and status in {"paused_content_verified", "paused_converged"}:
            suggestions = [
                "快速确认 story 是否覆盖你最关心的主流程。",
                "重点看是否有必须第一期完成但被放到范围外的能力。",
                "如果角色、权限或失败场景有特殊规则，可以直接补充说明。",
            ]
        return {
            "summary_points": summary_points,
            "suggestions": suggestions,
            "clarification_questions": self._build_clarification_questions(analysis_input, result, verification)
            if status == "paused_stalled"
            else [],
        }

    def _build_clarification_questions(
        self,
        analysis_input: RequirementAnalysisInput | None,
        result: RequirementAnalysisResult,
        verification: RequirementVerificationResult,
    ) -> list[str]:
        questions: list[str] = []
        coverage = self._explicit_capability_coverage(analysis_input, result)
        missing = coverage.get("missing", [])
        if isinstance(missing, list) and missing:
            questions.append(f"这些明确提到但尚未覆盖的能力，哪些必须第一期完成：{'、'.join(str(item) for item in missing[:5])}？")
        if any(issue.issue_type == "untestable_ac" for issue in verification.issues):
            questions.append("你最希望哪些关键操作具备明确的成功、失败和异常反馈判定标准？")
        if any(issue.issue_type in {"over_scoped", "under_scoped"} for issue in verification.issues):
            questions.append("当前 story 粒度你希望更偏按完整用户流程拆，还是按单个业务能力拆？")
        if any(issue.issue_type == "missing_story" for issue in verification.issues):
            questions.append("除了已列出的 story，还有哪些业务能力你认为不能遗漏？")
        questions.append("如果只做第一版 MVP，你希望优先保留哪些能力，哪些可以延后？")
        return questions[:4]

    def _explicit_capability_coverage(
        self,
        analysis_input: RequirementAnalysisInput | None,
        result: RequirementAnalysisResult,
    ) -> dict[str, object]:
        required = self._extract_explicit_capabilities(analysis_input.user_prompt if analysis_input else "")
        story_text = " ".join(
            [result.requirement_spec.product_goal]
            + result.requirement_spec.scope
            + [story.title for story in result.story_units]
            + [story.when_context for story in result.story_units]
            + [story.i_want for story in result.story_units]
            + [story.business_outcome for story in result.story_units]
            + [criterion for story in result.story_units for criterion in story.acceptance_criteria]
        )
        covered = [capability for capability in required if capability in story_text]
        missing = [capability for capability in required if capability not in story_text]
        return {
            "required": required,
            "covered": covered,
            "missing": missing,
            "covered_count": len(covered),
            "required_count": len(required),
        }

    def _is_blocking_issue(self, severity: str, issue_type: str) -> bool:
        return severity == "high" or (
            severity == "medium"
            and issue_type
            in {
                "missing_scope",
                "untestable_ac",
                "dependency_conflict",
                "over_scoped",
                "under_scoped",
                "missing_story",
                "blocked_dependency",
            }
        )

    def _extract_explicit_capabilities(self, user_prompt: str) -> list[str]:
        segments: list[str] = []
        for marker in ("具备", "包括", "包含", "支持", "实现", "提供"):
            marker_index = user_prompt.find(marker)
            if marker_index >= 0:
                segments.append(user_prompt[marker_index + len(marker):])
        candidates: list[str] = []
        for segment in segments or [user_prompt]:
            bounded_segment = re.split(r"[。；;\n]", segment, maxsplit=1)[0]
            for item in re.split(r"[、,，/]", bounded_segment):
                candidate = self._normalize_capability_candidate(item)
                if candidate:
                    candidates.append(candidate)
        required: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                required.append(candidate)
        return required

    def _normalize_capability_candidate(self, value: str) -> str | None:
        candidate = re.sub(r"^(和|及|以及|等|的|并|与|还有)", "", value.strip())
        candidate = re.sub(r"(等功能|等能力|功能|能力|模块|系统)$", "", candidate).strip()
        if not candidate or len(candidate) > 16:
            return None
        if candidate in {"网站", "应用", "平台", "系统", "一个", "等"}:
            return None
        return candidate

    def _build_format_invalid_package(
        self,
        analysis_input: RequirementAnalysisInput,
        error: ValueError,
    ) -> RequirementAnalysisPackage:
        requirement_spec = RequirementSpec(
            task_id=analysis_input.task_id,
            version=1,
            problem_statement=analysis_input.user_prompt,
            product_goal="等待用户重试或人工补充后重新生成标准需求分析结果。",
            scope=["格式校验失败后的人工介入"],
            out_of_scope=[],
            constraints=[f"上一次需求分析输出未通过格式校验：{error}"],
            assumptions=["当前结果不是可接受的需求分析产物，仅用于承载暂停状态。"],
            interfaces_or_contracts=[],
            acceptance_criteria=[
                "用户可以查看格式错误原因。",
                "用户可以选择重试需求分析。",
                "用户可以追加说明后再次生成需求分析结果。",
            ],
            decomposition_strategy="格式校验失败，暂不进行 story 拆分。",
        )
        story_unit = StoryUnit(
            id="format_invalid_placeholder",
            story_kind="system_feedback",
            title="用户可以在需求分析格式失败后查看错误并选择重试",
            as_a="需求分析用户",
            when_context="需求分析模型返回结果无法通过格式校验",
            i_want="看到明确错误原因并选择重试或补充说明",
            so_that="我可以恢复需求分析流程而不是停留在不可操作错误中",
            narrative="作为需求分析用户，当需求分析模型返回结果无法通过格式校验时，我希望看到明确错误原因并选择重试或补充说明，从而我可以恢复需求分析流程而不是停留在不可操作错误中。",
            actor="需求分析用户",
            goal="看到明确错误原因并选择重试或补充说明",
            business_value="我可以恢复需求分析流程而不是停留在不可操作错误中",
            business_outcome="用户明确知道当前输出不可用，并拥有下一步操作入口。",
            scope=["格式错误展示", "重试入口"],
            out_of_scope=[],
            acceptance_criteria=[
                "给定模型输出格式无效，当需求分析失败时，那么系统会展示格式错误原因。",
                "给定格式校验失败，当用户决定继续处理时，那么用户可以选择重试需求分析。",
                "给定用户补充说明后重试，当下一轮开始时，那么系统会保留原始需求上下文。",
            ],
            dependencies=[],
            priority="high",
            risk="medium",
            test_focus=["格式错误展示", "重试入口", "上下文保留"],
            implementation_hints=[],
        )
        verification = RequirementVerificationResult(
            status="blocked",
            summary=f"需求分析输出未通过格式校验：{error}",
            issues=[],
            revision_guidance=["请重试需求分析，或补充更明确的需求说明后再生成。"],
            quality_score=VerificationQualityScore(
                scope_clarity=0,
                testability=0,
                dependency_sanity=0,
                story_granularity=0,
            ),
        )
        result = RequirementAnalysisResult(
            requirement_spec=requirement_spec,
            story_units=[story_unit],
            analysis_summary=AnalysisSummary(
                story_unit_count=1,
                high_priority_count=1,
                high_risk_count=0,
                capability_group_count=1,
            ),
            warnings=["需求分析模型输出格式无效，当前包仅用于暂停和人工介入。"],
            quality_checks=QualityChecks(
                has_clear_scope=False,
                has_testable_ac=False,
                dependency_graph_valid=False,
                story_count_within_limit=False,
            ),
            capability_groups=[
                CapabilityGroup(
                    id="format_invalid_group",
                    title="格式校验失败处理",
                    goal="让用户可以从格式错误中恢复需求分析流程",
                    scope=["格式错误展示", "重试入口"],
                    story_ids=["format_invalid_placeholder"],
                    priority="high",
                )
            ],
        )
        return self._build_package(
            task_id=analysis_input.task_id,
            status="paused_format_invalid",
            result=result,
            verification=verification,
            composition_verification=None,
            history=[
                RequirementAnalysisIteration(
                    iteration=max(1, analysis_input.iteration),
                    analysis_summary=requirement_spec.problem_statement,
                    verification_status="blocked",
                    issue_count=1,
                    revision_guidance=list(verification.revision_guidance),
                )
            ],
            analysis_input=analysis_input,
        )

    def _analysis_result_from_input_snapshot(
        self,
        analysis_input: RequirementAnalysisInput,
    ) -> RequirementAnalysisResult:
        snapshot = analysis_input.previous_analysis_result
        if not isinstance(snapshot, dict):
            raise ValueError("previous_analysis_result is required for composition_review")
        raw_story_units = snapshot.get("story_units")
        if not isinstance(raw_story_units, list) or not raw_story_units:
            raise ValueError("previous_analysis_result.story_units must be a non-empty list")
        requirement_spec = RequirementSpec.from_dict(snapshot.get("requirement_spec"))
        story_units = [StoryUnit.from_dict(item) for item in raw_story_units]
        capability_groups, capability_group_warnings = self._capability_groups_from_snapshot(
            snapshot,
            requirement_spec,
            story_units,
        )
        quality_checks_payload = snapshot.get("quality_checks")
        quality_checks = QualityChecks(
            has_clear_scope=bool(getattr(quality_checks_payload, "get", lambda _key, _default=None: _default)("has_clear_scope", True)),
            has_testable_ac=bool(getattr(quality_checks_payload, "get", lambda _key, _default=None: _default)("has_testable_ac", True)),
            dependency_graph_valid=bool(getattr(quality_checks_payload, "get", lambda _key, _default=None: _default)("dependency_graph_valid", True)),
            story_count_within_limit=bool(getattr(quality_checks_payload, "get", lambda _key, _default=None: _default)("story_count_within_limit", True)),
        )
        warnings = [str(item) for item in snapshot.get("warnings", [])] if isinstance(snapshot.get("warnings"), list) else []
        warnings.extend(capability_group_warnings)
        return RequirementAnalysisResult(
            requirement_spec=requirement_spec,
            story_units=story_units,
            analysis_summary=AnalysisSummary(
                story_unit_count=len(story_units),
                high_priority_count=sum(1 for story in story_units if story.priority == "high"),
                high_risk_count=sum(1 for story in story_units if story.risk == "high"),
                capability_group_count=len(capability_groups),
            ),
            warnings=warnings,
            quality_checks=quality_checks,
            capability_groups=capability_groups,
        )

    def _capability_groups_from_snapshot(
        self,
        snapshot: dict[str, object],
        requirement_spec: RequirementSpec,
        story_units: list[StoryUnit],
    ) -> tuple[list[CapabilityGroup], list[str]]:
        warnings: list[str] = []
        raw_capability_groups = snapshot.get("capability_groups")
        if not isinstance(raw_capability_groups, list) or not raw_capability_groups:
            raw_capability_groups = snapshot.get("capabilityGroups")
        if isinstance(raw_capability_groups, list) and raw_capability_groups:
            try:
                capability_groups = [CapabilityGroup.from_dict(item) for item in raw_capability_groups]
            except ValueError as error:
                warnings.append(
                    f"previous_analysis_result.capability_groups 无法解析，已根据 story_units 自动生成兜底分组：{error}"
                )
            else:
                if capability_groups:
                    return capability_groups, warnings
        else:
            warnings.append("previous_analysis_result.capability_groups 缺失，已根据 story_units 自动生成兜底分组。")
        return [self._fallback_capability_group(requirement_spec, story_units)], warnings

    def _fallback_capability_group(
        self,
        requirement_spec: RequirementSpec,
        story_units: list[StoryUnit],
    ) -> CapabilityGroup:
        scope = self._unique_non_empty_strings(
            item for story in story_units for item in story.scope
        ) or self._unique_non_empty_strings(requirement_spec.scope) or ["当前需求范围"]
        story_ids = self._unique_non_empty_strings(story.id for story in story_units)
        return CapabilityGroup(
            id="capability_group_1",
            title="整体需求分组",
            goal="基于当前已通过的 user story 组合进入组合验证",
            scope=scope,
            story_ids=story_ids,
            priority="high" if any(story.priority == "high" for story in story_units) else "medium",
        )

    @staticmethod
    def _unique_non_empty_strings(values) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    def _content_review_passed_verification(self) -> RequirementVerificationResult:
        return RequirementVerificationResult(
            status="pass",
            summary="用户已确认逐一内容审核通过，继续进入组合验证。",
            issues=[],
            revision_guidance=[],
            quality_score=VerificationQualityScore(
                scope_clarity=100,
                testability=100,
                dependency_sanity=100,
                story_granularity=100,
            ),
        )

    def _next_revision_focus(
        self,
        verification: RequirementVerificationResult,
        composition_verification: RequirementCompositionVerificationResult | None = None,
    ) -> list[str]:
        if composition_verification is not None and composition_verification.status == "revise":
            if composition_verification.revision_guidance:
                return list(composition_verification.revision_guidance)
            if composition_verification.missing_story_topics:
                return list(composition_verification.missing_story_topics)
            if composition_verification.composition_issues:
                return [item.message for item in composition_verification.composition_issues]
        if verification.revision_guidance:
            return list(verification.revision_guidance)
        if verification.issues:
            return [item.message for item in verification.issues]
        return ["在保持当前质量的前提下继续提升需求拆解的精度与一致性。"]

    def _overall_feedback_summary(
        self,
        verification: RequirementVerificationResult,
        composition_verification: RequirementCompositionVerificationResult | None = None,
    ) -> str:
        if verification.status != "pass" or composition_verification is None:
            return verification.summary
        return composition_verification.summary
