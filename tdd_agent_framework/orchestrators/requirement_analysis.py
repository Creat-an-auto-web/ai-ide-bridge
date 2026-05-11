from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from time import monotonic
from uuid import uuid4

from tdd_agent_framework.core import ProgressCallback, RunProgressEvent, emit_progress
from tdd_agent_framework.agents.requirement_analysis import (
    RequirementAnalysisIteration,
    RequirementAnalysisAgentSettings,
    RequirementAnalysisInput,
    RequirementAnalysisPackage,
    RequirementAnalysisResult,
    RequirementVerificationResult,
    build_requirement_analysis_service,
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
    stalled_repeat_threshold = 2
    min_score_delta_for_improvement = 3

    def __init__(self) -> None:
        self.name = "requirement_analysis_orchestrator"

    async def run(
        self,
        settings: RequirementAnalysisAgentSettings,
        analysis_input: RequirementAnalysisInput,
        progress_callback: ProgressCallback | None = None,
    ) -> RequirementAnalysisPackage:
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

        started_at = monotonic()
        configured_timeout_seconds = float(getattr(settings, "timeout_seconds", 60.0))
        runtime_budget_seconds = max(180.0, configured_timeout_seconds * 4)
        history: list[RequirementAnalysisIteration] = []
        working_input = enriched_input
        latest_result: RequirementAnalysisResult | None = None
        latest_verification: RequirementVerificationResult | None = None
        current_iteration = max(1, working_input.iteration)
        repeat_stall_count = 0
        last_signature: str | None = None
        best_score: int | None = None

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
            latest_result = await service.analyze(
                working_input,
                metadata={"orchestrator": self.name, "iteration": str(iteration)},
            )
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

            history.append(
                RequirementAnalysisIteration(
                    iteration=iteration,
                    analysis_summary=latest_result.requirement_spec.problem_statement,
                    verification_status=latest_verification.status,
                    issue_count=len(latest_verification.issues),
                    revision_guidance=list(latest_verification.revision_guidance),
                )
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
                return self._build_package(
                    task_id=working_input.task_id,
                    status="paused_converged",
                    result=latest_result,
                    verification=latest_verification,
                    history=history,
                )

            if latest_verification.status == "blocked":
                return self._build_package(
                    task_id=working_input.task_id,
                    status="paused_blocked",
                    result=latest_result,
                    verification=latest_verification,
                    history=history,
                )

            current_score = self._verification_score(latest_verification)
            current_signature = self._verification_signature(latest_verification)
            improved = best_score is None or current_score >= best_score + self.min_score_delta_for_improvement
            if improved:
                best_score = current_score
                repeat_stall_count = 0
            else:
                repeat_stall_count = repeat_stall_count + 1 if current_signature == last_signature else 1
            last_signature = current_signature

            if monotonic() - started_at >= runtime_budget_seconds:
                await emit_progress(
                    progress_callback,
                    RunProgressEvent(
                        type="status",
                        stage="analysis_runtime_budget_reached",
                        message=(
                            f"需求分析已达到运行预算 {int(runtime_budget_seconds)} 秒，"
                            "进入暂停待人工决策状态"
                        ),
                        metadata={
                            "iteration": iteration,
                            "runtime_budget_seconds": runtime_budget_seconds,
                            "verification_status": latest_verification.status,
                        },
                    ),
                )
                return self._build_package(
                    task_id=working_input.task_id,
                    status="paused_stalled",
                    result=latest_result,
                    verification=latest_verification,
                    history=history,
                )

            if repeat_stall_count >= self.stalled_repeat_threshold:
                await emit_progress(
                    progress_callback,
                    RunProgressEvent(
                        type="status",
                        stage="analysis_stalled",
                        message="连续多轮没有实质改进，需求分析已暂停，等待用户决定是否继续优化",
                        metadata={
                            "iteration": iteration,
                            "repeat_stall_count": repeat_stall_count,
                            "verification_status": latest_verification.status,
                        },
                    ),
                )
                return self._build_package(
                    task_id=working_input.task_id,
                    status="paused_stalled",
                    result=latest_result,
                    verification=latest_verification,
                    history=history,
                )

            await emit_progress(
                progress_callback,
                RunProgressEvent(
                    type="status",
                    stage="analysis_revision_requested",
                    message=f"第 {iteration} 轮需要修订，准备继续优化",
                    metadata={
                        "iteration": iteration,
                        "revision_guidance": latest_verification.revision_guidance,
                    },
                ),
            )
            working_input = replace(
                working_input,
                revision_focus=self._next_revision_focus(latest_verification),
                previous_verification_summary=latest_verification.summary,
            )
            current_iteration += 1

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
        history: list[RequirementAnalysisIteration],
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
            iteration_count=history[-1].iteration if history else 0,
            history=list(history),
        )

    def _verification_score(self, verification: RequirementVerificationResult) -> int:
        score = verification.quality_score
        issue_penalty = sum(
            12 if item.severity == "high" else 6 if item.severity == "medium" else 2
            for item in verification.issues
        )
        return (
            score.scope_clarity
            + score.testability
            + score.dependency_sanity
            + score.story_granularity
            - issue_penalty
        )

    def _verification_signature(self, verification: RequirementVerificationResult) -> str:
        issue_parts = [
            f"{item.severity}:{item.issue_type}:{item.message.strip()}"
            for item in verification.issues
        ]
        return "|".join([verification.status, verification.summary.strip(), *issue_parts])

    def _next_revision_focus(
        self,
        verification: RequirementVerificationResult,
    ) -> list[str]:
        if verification.revision_guidance:
            return list(verification.revision_guidance)
        if verification.issues:
            return [item.message for item in verification.issues]
        return ["在保持当前质量的前提下继续提升需求拆解的精度与一致性。"]
