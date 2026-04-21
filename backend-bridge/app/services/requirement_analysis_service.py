from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
import sys
from time import monotonic

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
from tdd_agent_framework.core import RunProgressEvent  # noqa: E402
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

    async def stream_run(
        self,
        payload: RequirementAnalysisRunRequest,
        event_callback,
    ) -> dict:
        started_at = monotonic()
        heartbeat_active = True

        async def emit_progress(event: RunProgressEvent) -> None:
            await event_callback(
                {
                    "type": event.type,
                    "stage": event.stage,
                    "message": event.message,
                    "raw_text_delta": event.raw_text_delta,
                    "raw_text_preview": event.raw_text_preview,
                    "metadata": event.metadata,
                    "elapsed_ms": int((monotonic() - started_at) * 1000),
                }
            )

        async def heartbeat_loop() -> None:
            while heartbeat_active:
                await asyncio.sleep(2)
                if not heartbeat_active:
                    break
                await event_callback(
                    {
                        "type": "heartbeat",
                        "stage": "waiting_model",
                        "message": "第一环仍在运行，等待模型继续返回结果",
                        "elapsed_ms": int((monotonic() - started_at) * 1000),
                    }
                )

        heartbeat_task = asyncio.create_task(heartbeat_loop())

        try:
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
            result = await self.orchestrator.run(
                settings,
                analysis_input,
                progress_callback=emit_progress,
            )
            result_payload = asdict(result)
            await event_callback(
                {
                    "type": "result",
                    "stage": "completed",
                    "message": "第一环完成",
                    "data": result_payload,
                    "elapsed_ms": int((monotonic() - started_at) * 1000),
                }
            )
            return result_payload
        finally:
            heartbeat_active = False
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
