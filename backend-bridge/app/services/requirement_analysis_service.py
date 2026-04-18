from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys

from app.models.requirement_analysis import RequirementAnalysisRunRequest


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tdd_agent_framework.agents.requirement_analysis import (  # noqa: E402
    RequirementAnalysisAgentSettings,
    RequirementAnalysisInput,
    WorkspaceSummary,
    ExecutionConstraints,
)
from tdd_agent_framework.orchestrators import RequirementAnalysisOrchestrator  # noqa: E402


class RequirementAnalysisBackendService:
    def __init__(self, orchestrator: RequirementAnalysisOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or RequirementAnalysisOrchestrator()

    async def run(self, payload: RequirementAnalysisRunRequest) -> dict:
        settings = RequirementAnalysisAgentSettings.from_dict(payload.settings.model_dump())
        analysis_input = RequirementAnalysisInput(
            task_id=payload.input.task_id,
            mode=payload.input.mode,
            user_prompt=payload.input.user_prompt,
            repo_root=payload.input.repo_root,
            workspace_summary=WorkspaceSummary.from_dict(payload.input.workspace_summary.model_dump()),
            active_file=payload.input.active_file,
            selection=payload.input.selection,
            open_files=list(payload.input.open_files),
            diagnostics=list(payload.input.diagnostics),
            recent_test_failures=list(payload.input.recent_test_failures),
            git_diff_summary=payload.input.git_diff_summary,
            execution_constraints=ExecutionConstraints.from_dict(
                payload.input.execution_constraints.model_dump()
            ),
        )
        result = await self.orchestrator.run(settings, analysis_input)
        return asdict(result)
