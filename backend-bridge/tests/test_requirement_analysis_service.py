from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock

TEST_ROOT = Path(__file__).resolve().parents[1]
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from app.models.requirement_analysis import RequirementAnalysisRunRequest
from app.services.requirement_analysis_service import RequirementAnalysisBackendService


@dataclass(frozen=True)
class FakeResult:
    status: str = "paused_converged"


class RequirementAnalysisBackendServiceTest(unittest.TestCase):
    def test_stream_run_preserves_feedback_and_nullable_limits(self) -> None:
        orchestrator = AsyncMock()
        orchestrator.run = AsyncMock(return_value=FakeResult())
        service = RequirementAnalysisBackendService(orchestrator=orchestrator)
        payload = RequirementAnalysisRunRequest.model_validate(
            {
                "settings": {
                    "enabled": True,
                    "provider_kind": "openai_compatible",
                    "provider_name": "openai",
                    "model": "gpt-5.4",
                    "api_base": "https://api.openai.com/v1",
                    "api_key": "secret",
                    "first_round_max_capability_groups": 4,
                    "first_round_max_story_units": 12,
                    "second_round_max_capability_groups": 6,
                    "second_round_max_story_units": 24,
                    "later_round_max_capability_groups": None,
                    "later_round_max_story_units": None,
                },
                "input": {
                    "task_id": "task_001",
                    "mode": "repo_chat",
                    "user_prompt": "继续优化当前需求分析。",
                    "repo_root": "/workspace/project",
                    "workspace_summary": {},
                    "global_feedback": {
                        "feedback_id": "gfb_1",
                        "task_id": "task_001",
                        "feedback_type": "scope_adjustment",
                        "feedback_text": "补充权限控制范围",
                    },
                    "story_feedback": {
                        "feedback_id": "sfb_1",
                        "task_id": "task_001",
                        "story_id": "S1",
                        "feedback_type": "wording_issue",
                        "feedback_text": "把 story 改成更贴近真实业务场景",
                    },
                    "analysis_goal": "composition_review",
                    "previous_analysis_result": {
                        "requirement_spec": {"task_id": "task_001"},
                        "story_units": [{"id": "S1"}],
                        "capability_groups": [{"id": "CG1"}],
                    },
                    "execution_constraints": {
                        "disallow_new_dependencies": True,
                        "preserve_public_api": True,
                        "max_capability_groups": None,
                        "max_story_units": None,
                    },
                },
            }
        )

        events: list[dict] = []

        async def collect_event(event: dict) -> None:
            events.append(event)

        result = asyncio.run(service.stream_run(payload, collect_event))

        self.assertTrue(orchestrator.run.await_count >= 1)
        analysis_input = orchestrator.run.await_args.args[1]
        self.assertIsNotNone(analysis_input.global_feedback)
        self.assertIsNotNone(analysis_input.story_feedback)
        self.assertEqual(analysis_input.global_feedback.package_id, "task_001")
        self.assertEqual(analysis_input.story_feedback.package_id, "task_001")
        self.assertEqual(analysis_input.analysis_goal, "composition_review")
        self.assertEqual(analysis_input.previous_analysis_result["story_units"][0]["id"], "S1")
        self.assertIsNone(analysis_input.execution_constraints.max_capability_groups)
        self.assertIsNone(analysis_input.execution_constraints.max_story_units)
        self.assertEqual(result["status"], "paused_converged")
        self.assertTrue(any(event.get("type") == "result" for event in events))
