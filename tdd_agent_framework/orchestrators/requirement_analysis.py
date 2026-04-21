from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tdd_agent_framework.core import ProgressCallback, RunProgressEvent, emit_progress
from tdd_agent_framework.agents.requirement_analysis import (
    RequirementAnalysisAgentSettings,
    RequirementAnalysisInput,
    RequirementAnalysisResult,
    build_requirement_analysis_service,
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
    def __init__(self) -> None:
        self.name = "requirement_analysis_orchestrator"

    async def run(
        self,
        settings: RequirementAnalysisAgentSettings,
        analysis_input: RequirementAnalysisInput,
        progress_callback: ProgressCallback | None = None,
    ) -> RequirementAnalysisResult:
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
        result = await service.analyze(
            enriched_input,
            metadata={"orchestrator": self.name},
        )
        await emit_progress(
            progress_callback,
            RunProgressEvent(
                type="status",
                stage="analysis_completed",
                message="需求分析已完成，正在返回结果",
                metadata={"story_unit_count": len(result.story_units)},
            ),
        )
        return result

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
