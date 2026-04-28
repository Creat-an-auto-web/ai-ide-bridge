from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tdd_agent_framework.agents.requirement_analysis import StoryUnit


def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null")
    stripped = value.strip()
    return stripped or None


def _require_list_of_str(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field_name} must be a non-empty list of strings")
    return [_require_str(item, field_name) for item in value]


def _optional_list_of_str(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    return [_require_str(item, field_name) for item in value]


def _require_dict(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{field_name} must be a non-empty object")
    return value


@dataclass(frozen=True)
class TestCaseGenerationConstraints:
    max_test_cases_per_story: int = 6
    require_boundary_cases: bool = True
    require_negative_cases: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TestCaseGenerationConstraints":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("execution_constraints must be an object")
        max_test_cases_per_story = data.get("max_test_cases_per_story", 6)
        if not isinstance(max_test_cases_per_story, int) or max_test_cases_per_story <= 0:
            raise ValueError("execution_constraints.max_test_cases_per_story must be a positive integer")
        return cls(
            max_test_cases_per_story=max_test_cases_per_story,
            require_boundary_cases=bool(data.get("require_boundary_cases", True)),
            require_negative_cases=bool(data.get("require_negative_cases", True)),
        )


@dataclass(frozen=True)
class TestCaseGenerationInput:
    task_id: str
    user_prompt: str | None = None
    story_units: list[StoryUnit] = field(default_factory=list)
    execution_constraints: TestCaseGenerationConstraints = field(
        default_factory=TestCaseGenerationConstraints,
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestCaseGenerationInput":
        if not isinstance(data, dict):
            raise ValueError("test case generation input must be an object")
        raw_story_units = data.get("story_units")
        if not isinstance(raw_story_units, list) or not raw_story_units:
            raise ValueError("story_units must be a non-empty list")
        return cls(
            task_id=_require_str(data.get("task_id"), "task_id"),
            user_prompt=_optional_str(data.get("user_prompt"), "user_prompt"),
            story_units=[StoryUnit.from_dict(item) for item in raw_story_units],
            execution_constraints=TestCaseGenerationConstraints.from_dict(
                data.get("execution_constraints"),
            ),
        )


@dataclass(frozen=True)
class GeneratedTestCase:
    id: str
    story_id: str
    title: str
    level: str
    category: str
    purpose: str
    preconditions: list[str]
    test_input: dict[str, Any]
    steps: list[str]
    expected_result: str
    acceptance_criteria_refs: list[str]
    priority: str
    automatable: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeneratedTestCase":
        if not isinstance(data, dict):
            raise ValueError("test_case must be an object")
        return cls(
            id=_require_str(data.get("id"), "test_case.id"),
            story_id=_require_str(data.get("story_id"), "test_case.story_id"),
            title=_require_str(data.get("title"), "test_case.title"),
            level=_require_str(data.get("level"), "test_case.level").lower(),
            category=_require_str(data.get("category"), "test_case.category").lower(),
            purpose=_require_str(data.get("purpose"), "test_case.purpose"),
            preconditions=_optional_list_of_str(
                data.get("preconditions"),
                "test_case.preconditions",
            ),
            test_input=_require_dict(data.get("test_input"), "test_case.test_input"),
            steps=_require_list_of_str(data.get("steps"), "test_case.steps"),
            expected_result=_require_str(data.get("expected_result"), "test_case.expected_result"),
            acceptance_criteria_refs=_optional_list_of_str(
                data.get("acceptance_criteria_refs"),
                "test_case.acceptance_criteria_refs",
            ),
            priority=_require_str(data.get("priority"), "test_case.priority").lower(),
            automatable=bool(data.get("automatable", True)),
        )


@dataclass(frozen=True)
class TestCoverageSummary:
    total_story_count: int
    covered_story_count: int
    uncovered_story_ids: list[str]
    total_test_case_count: int
    per_story_case_count: dict[str, int]


@dataclass(frozen=True)
class TestCaseQualityChecks:
    has_inputs_and_expected_results: bool
    covers_all_stories: bool
    has_boundary_cases: bool
    has_negative_cases: bool
    case_count_within_limit: bool


@dataclass(frozen=True)
class TestCaseGenerationResult:
    test_plan: str
    test_cases: list[GeneratedTestCase]
    coverage_summary: TestCoverageSummary
    warnings: list[str]
    quality_checks: TestCaseQualityChecks


def build_coverage_summary(
    story_units: list[StoryUnit],
    test_cases: list[GeneratedTestCase],
) -> TestCoverageSummary:
    per_story_case_count: dict[str, int] = {story.id: 0 for story in story_units}
    for case in test_cases:
        if case.story_id in per_story_case_count:
            per_story_case_count[case.story_id] += 1
    uncovered = [story_id for story_id, count in per_story_case_count.items() if count == 0]
    return TestCoverageSummary(
        total_story_count=len(story_units),
        covered_story_count=len(per_story_case_count) - len(uncovered),
        uncovered_story_ids=sorted(uncovered),
        total_test_case_count=len(test_cases),
        per_story_case_count=per_story_case_count,
    )
