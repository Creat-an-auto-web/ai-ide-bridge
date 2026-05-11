from __future__ import annotations

import json

from tdd_agent_framework.core import ProviderResponse

from .models import (
    CapabilityGroup,
    QualityChecks,
    RequirementAnalysisResult,
    RequirementSpec,
    StoryUnit,
    build_analysis_summary,
)


class RequirementAnalysisParser:
    def parse(self, response: ProviderResponse) -> RequirementAnalysisResult:
        payload = response.parsed_json
        if payload is None:
            payload = json.loads(response.raw_text)
        if not isinstance(payload, dict):
            raise ValueError("provider output must be a JSON object")

        requirement_spec = RequirementSpec.from_dict(payload.get("requirement_spec"))
        raw_story_units = payload.get("story_units")
        if not isinstance(raw_story_units, list) or not raw_story_units:
            raise ValueError("story_units must be a non-empty list")
        story_units = [StoryUnit.from_dict(item) for item in raw_story_units]
        capability_groups = self._parse_capability_groups(payload, story_units)

        warnings = payload.get("warnings", [])
        if not isinstance(warnings, list):
            raise ValueError("warnings must be a list of strings")

        return RequirementAnalysisResult(
            requirement_spec=requirement_spec,
            story_units=story_units,
            analysis_summary=build_analysis_summary(story_units, capability_groups),
            warnings=[str(item) for item in warnings],
            quality_checks=QualityChecks(
                has_clear_scope=False,
                has_testable_ac=False,
                dependency_graph_valid=False,
                story_count_within_limit=False,
            ),
            capability_groups=capability_groups,
        )

    def _parse_capability_groups(
        self,
        payload: dict,
        story_units: list[StoryUnit],
    ) -> list[CapabilityGroup]:
        raw_groups = payload.get("capability_groups")
        if isinstance(raw_groups, list) and raw_groups:
            return [CapabilityGroup.from_dict(item) for item in raw_groups]

        return [
            CapabilityGroup(
                id="capability_group_1",
                title="整体需求分组",
                goal="在缺少显式 capability_groups 时保留最小分层结构",
                scope=sorted({scope for story in story_units for scope in story.scope})[:8] or ["core_scope"],
                story_ids=[story.id for story in story_units],
                priority="high" if any(story.priority == "high" for story in story_units) else "medium",
            )
        ]
