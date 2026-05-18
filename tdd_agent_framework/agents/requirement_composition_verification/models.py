from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tdd_agent_framework.agents.requirement_analysis.models import (
    CapabilityGroup,
    RequirementAnalysisInput,
    RequirementAnalysisResult,
    StoryUnit,
    _optional_list_of_display_str,
    _optional_list_of_str,
    _require_str,
)


@dataclass(frozen=True)
class RequirementCompositionVerificationInput:
    analysis_input: RequirementAnalysisInput
    analysis_result: RequirementAnalysisResult
    iteration: int = 1
    session_id: str | None = None


@dataclass(frozen=True)
class CompositionCoverageAssessment:
    covers_primary_user_goal: bool
    covers_permission_constraints: bool
    covers_failure_handling: bool
    covers_end_to_end_flow: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CompositionCoverageAssessment":
        if data is None:
            return cls(
                covers_primary_user_goal=False,
                covers_permission_constraints=False,
                covers_failure_handling=False,
                covers_end_to_end_flow=False,
            )
        if not isinstance(data, dict):
            raise ValueError("coverage_assessment must be an object")
        return cls(
            covers_primary_user_goal=bool(data.get("covers_primary_user_goal", False)),
            covers_permission_constraints=bool(data.get("covers_permission_constraints", False)),
            covers_failure_handling=bool(data.get("covers_failure_handling", False)),
            covers_end_to_end_flow=bool(data.get("covers_end_to_end_flow", False)),
        )


@dataclass(frozen=True)
class CompositionIssue:
    id: str
    severity: str
    issue_type: str
    message: str
    related_story_ids: list[str] = field(default_factory=list)
    related_capability_group_ids: list[str] = field(default_factory=list)
    suggested_action: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompositionIssue":
        if not isinstance(data, dict):
            raise ValueError("composition_issue must be an object")
        return cls(
            id=_require_str(data.get("id"), "composition_issue.id"),
            severity=_require_str(data.get("severity"), "composition_issue.severity").lower(),
            issue_type=_require_str(
                data.get("issue_type") if data.get("issue_type") is not None else data.get("type"),
                "composition_issue.issue_type",
            ),
            message=_require_str(data.get("message"), "composition_issue.message"),
            related_story_ids=_optional_list_of_str(
                data.get("related_story_ids"),
                "composition_issue.related_story_ids",
            ),
            related_capability_group_ids=_optional_list_of_str(
                data.get("related_capability_group_ids"),
                "composition_issue.related_capability_group_ids",
            ),
            suggested_action=_require_str(data.get("suggested_action"), "composition_issue.suggested_action")
            if data.get("suggested_action") is not None
            else None,
        )


@dataclass(frozen=True)
class IntegrationTestScenario:
    id: str
    title: str
    covers_story_ids: list[str]
    covers_capability_group_ids: list[str]
    expected_outcome: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntegrationTestScenario":
        if not isinstance(data, dict):
            raise ValueError("integration_test_scenario must be an object")
        return cls(
            id=_require_str(data.get("id"), "integration_test_scenario.id"),
            title=_require_str(data.get("title"), "integration_test_scenario.title"),
            covers_story_ids=_optional_list_of_str(
                data.get("covers_story_ids"),
                "integration_test_scenario.covers_story_ids",
            ),
            covers_capability_group_ids=_optional_list_of_str(
                data.get("covers_capability_group_ids"),
                "integration_test_scenario.covers_capability_group_ids",
            ),
            expected_outcome=_require_str(
                data.get("expected_outcome"),
                "integration_test_scenario.expected_outcome",
            ),
        )


@dataclass(frozen=True)
class RequirementCompositionVerificationResult:
    status: str
    summary: str
    coverage_assessment: CompositionCoverageAssessment
    composition_issues: list[CompositionIssue]
    integration_test_scenarios: list[IntegrationTestScenario]
    redundant_story_ids: list[str]
    missing_story_topics: list[str]
    revision_guidance: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RequirementCompositionVerificationResult":
        if not isinstance(data, dict):
            raise ValueError("requirement composition verification result must be an object")
        raw_issues = data.get("composition_issues", [])
        raw_scenarios = data.get("integration_test_scenarios", [])
        if not isinstance(raw_issues, list):
            raise ValueError("composition_issues must be a list")
        if not isinstance(raw_scenarios, list):
            raise ValueError("integration_test_scenarios must be a list")
        normalized_issues = []
        for index, item in enumerate(raw_issues, start=1):
            if isinstance(item, dict):
                normalized_issues.append(item)
                continue
            normalized_issues.append(
                {
                    "id": f"composition_issue_{index}",
                    "severity": "medium",
                    "issue_type": "unspecified_issue",
                    "message": str(item),
                    "related_story_ids": [],
                    "related_capability_group_ids": [],
                }
            )
        status_value = data.get("status") if data.get("status") is not None else data.get("verdict")
        normalized_status = str(status_value).strip().lower() if status_value is not None else ""
        if normalized_status not in {"pass", "revise", "blocked"}:
            normalized_status = "revise" if normalized_issues else "pass"
        summary_value = data.get("summary")
        if not isinstance(summary_value, str) or not summary_value.strip():
            summary_value = (
                "当前 story 组合存在需要修订的闭环问题。"
                if normalized_issues
                else "当前 story 组合已经形成可验证闭环。"
            )
        return cls(
            status=normalized_status,
            summary=_require_str(summary_value, "composition_verification.summary"),
            coverage_assessment=CompositionCoverageAssessment.from_dict(
                data.get("coverage_assessment")
            ),
            composition_issues=[CompositionIssue.from_dict(item) for item in normalized_issues],
            integration_test_scenarios=[
                IntegrationTestScenario.from_dict(item)
                for item in raw_scenarios
            ],
            redundant_story_ids=_optional_list_of_str(
                data.get("redundant_story_ids"),
                "composition_verification.redundant_story_ids",
            ),
            missing_story_topics=_optional_list_of_display_str(
                data.get("missing_story_topics"),
                "composition_verification.missing_story_topics",
            ),
            revision_guidance=_optional_list_of_display_str(
                data.get("revision_guidance"),
                "composition_verification.revision_guidance",
            ),
        )


def story_units_to_payload(story_units: list[StoryUnit]) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "story_kind": item.story_kind,
            "title": item.title,
            "as_a": item.as_a,
            "when_context": item.when_context,
            "i_want": item.i_want,
            "so_that": item.so_that,
            "narrative": item.narrative,
            "actor": item.actor,
            "goal": item.goal,
            "business_value": item.business_value,
            "business_outcome": item.business_outcome,
            "scope": item.scope,
            "out_of_scope": item.out_of_scope,
            "acceptance_criteria": item.acceptance_criteria,
            "dependencies": item.dependencies,
            "priority": item.priority,
            "risk": item.risk,
            "test_focus": item.test_focus,
            "implementation_hints": item.implementation_hints,
        }
        for item in story_units
    ]


def capability_groups_to_payload(groups: list[CapabilityGroup]) -> list[dict[str, Any]]:
    return [
        {
            "id": group.id,
            "title": group.title,
            "goal": group.goal,
            "scope": group.scope,
            "story_ids": group.story_ids,
            "priority": group.priority,
        }
        for group in groups
    ]
