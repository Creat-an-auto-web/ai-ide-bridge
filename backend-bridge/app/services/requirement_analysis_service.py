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
from tdd_agent_framework.agents.requirement_feedback import (  # noqa: E402
    GlobalFeedback,
    StoryFeedback,
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
            global_feedback=(
                GlobalFeedback.from_dict(self._normalize_global_feedback(payload))
                if payload.input.global_feedback is not None
                else None
            ),
            story_feedback=(
                StoryFeedback.from_dict(self._normalize_story_feedback(payload))
                if payload.input.story_feedback is not None
                else None
            ),
            revision_focus=list(payload.input.revision_focus),
            previous_verification_summary=payload.input.previous_verification_summary,
            iteration=payload.input.iteration,
            analysis_goal=payload.input.analysis_goal,
            previous_analysis_result=payload.input.previous_analysis_result,
            execution_constraints=ExecutionConstraints.from_dict(
                payload.input.execution_constraints.model_dump()
            ),
        )
        result = await self.orchestrator.run(settings, analysis_input)
        return self._normalize_result_payload(asdict(result))

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
                        "message": "需求分析仍在运行，等待模型继续返回结果",
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
                global_feedback=(
                    GlobalFeedback.from_dict(self._normalize_global_feedback(payload))
                    if payload.input.global_feedback is not None
                    else None
                ),
                story_feedback=(
                    StoryFeedback.from_dict(self._normalize_story_feedback(payload))
                    if payload.input.story_feedback is not None
                    else None
                ),
                revision_focus=list(payload.input.revision_focus),
                previous_verification_summary=payload.input.previous_verification_summary,
                iteration=payload.input.iteration,
                analysis_goal=payload.input.analysis_goal,
                previous_analysis_result=payload.input.previous_analysis_result,
                execution_constraints=ExecutionConstraints.from_dict(
                    payload.input.execution_constraints.model_dump()
                ),
            )
            result = await self.orchestrator.run(
                settings,
                analysis_input,
                progress_callback=emit_progress,
            )
            result_payload = self._normalize_result_payload(asdict(result))
            result_message = {
                "paused_content_verified": "需求内容验证已通过，等待用户审核后进入组合验证",
                "paused_converged": "需求分析已收敛，等待用户决定是否接受或继续优化",
                "paused_stalled": "需求分析已暂停，等待用户决定是否继续优化",
                "paused_blocked": "需求分析已阻塞，等待用户提供更多信息或人工介入",
                "paused_format_invalid": "需求分析格式校验失败，等待用户选择重试或人工介入",
            }.get(result.status, "需求分析完成")
            await event_callback(
                {
                    "type": "result",
                    "stage": result.status,
                    "message": result_message,
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

    def _normalize_global_feedback(self, payload: RequirementAnalysisRunRequest) -> dict:
        feedback = payload.input.global_feedback
        if feedback is None:
            raise ValueError("global_feedback is required")
        data = feedback.model_dump()
        if not data.get("package_id"):
            data["package_id"] = payload.input.task_id
        if not data.get("author_role"):
            data["author_role"] = "user"
        return data

    def _normalize_story_feedback(self, payload: RequirementAnalysisRunRequest) -> dict:
        feedback = payload.input.story_feedback
        if feedback is None:
            raise ValueError("story_feedback is required")
        data = feedback.model_dump()
        if not data.get("package_id"):
            data["package_id"] = payload.input.task_id
        if not data.get("author_role"):
            data["author_role"] = "user"
        return data

    def _normalize_result_payload(self, payload: dict) -> dict:
        story_units = payload.get("story_units")
        if not isinstance(story_units, list):
            story_units = []
            payload["story_units"] = story_units

        capability_groups = payload.get("capability_groups")
        if not isinstance(capability_groups, list):
            capability_groups = []

        story_ids = [
            story.get("id")
            for story in story_units
            if isinstance(story, dict) and isinstance(story.get("id"), str) and story.get("id")
        ]
        valid_story_ids = set(story_ids)
        normalized_groups: list[dict] = []
        for index, group in enumerate(capability_groups):
            if not isinstance(group, dict):
                continue
            raw_group_story_ids = group.get("story_ids")
            raw_story_id_values = raw_group_story_ids if isinstance(raw_group_story_ids, list) else []
            group_story_ids = [
                story_id
                for story_id in raw_story_id_values
                if isinstance(story_id, str) and story_id in valid_story_ids
            ]
            if not group_story_ids:
                continue
            normalized_groups.append(
                {
                    "id": str(group.get("id") or f"capability_group_{index + 1}"),
                    "title": str(group.get("title") or f"功能组 {index + 1}"),
                    "goal": str(group.get("goal") or "覆盖当前需求中的一组相关 user story。"),
                    "scope": group.get("scope") if isinstance(group.get("scope"), list) else [],
                    "story_ids": group_story_ids,
                    "priority": str(group.get("priority") or "medium"),
                }
            )

        covered_story_ids = {
            story_id
            for group in normalized_groups
            for story_id in group["story_ids"]
        }
        uncovered_story_ids = [story_id for story_id in story_ids if story_id not in covered_story_ids]
        if uncovered_story_ids:
            normalized_groups.append(
                {
                    "id": "capability_group_unassigned",
                    "title": "未分组 Story",
                    "goal": "兜底承载尚未归入显式功能组的 user story，保证前端始终可以按组展示。",
                    "scope": [],
                    "story_ids": uncovered_story_ids,
                    "priority": "high"
                    if any(
                        isinstance(story, dict)
                        and story.get("id") in uncovered_story_ids
                        and story.get("priority") == "high"
                        for story in story_units
                    )
                    else "medium",
                }
            )
        if not normalized_groups and story_ids:
            normalized_groups.append(
                {
                    "id": "capability_group_1",
                    "title": "整体需求分组",
                    "goal": "在缺少显式功能组明细时保留最小分层结构，保证前端可以按功能组展示。",
                    "scope": [],
                    "story_ids": story_ids,
                    "priority": "high"
                    if any(isinstance(story, dict) and story.get("priority") == "high" for story in story_units)
                    else "medium",
                }
            )

        payload["capability_groups"] = normalized_groups
        analysis_summary = payload.get("analysis_summary")
        if isinstance(analysis_summary, dict):
            analysis_summary["capability_group_count"] = len(normalized_groups)
            analysis_summary["story_unit_count"] = len(story_units)
        else:
            payload["analysis_summary"] = {
                "story_unit_count": len(story_units),
                "high_priority_count": sum(
                    1 for story in story_units if isinstance(story, dict) and story.get("priority") == "high"
                ),
                "high_risk_count": sum(
                    1 for story in story_units if isinstance(story, dict) and story.get("risk") == "high"
                ),
                "capability_group_count": len(normalized_groups),
            }
        return payload
