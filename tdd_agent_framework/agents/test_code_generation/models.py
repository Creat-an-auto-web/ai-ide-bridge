from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tdd_agent_framework.agents.requirement_analysis import StoryUnit
from tdd_agent_framework.agents.test_case_generation import GeneratedTestCase


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


@dataclass(frozen=True)
class TestCodeGenerationConstraints:
    max_test_files: int = 4
    prefer_existing_test_stack: bool = True
    include_fixtures: bool = True
    framework_hint: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TestCodeGenerationConstraints":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("execution_constraints must be an object")
        max_test_files = data.get("max_test_files", 4)
        if not isinstance(max_test_files, int) or max_test_files <= 0:
            raise ValueError("execution_constraints.max_test_files must be a positive integer")
        return cls(
            max_test_files=max_test_files,
            prefer_existing_test_stack=bool(data.get("prefer_existing_test_stack", True)),
            include_fixtures=bool(data.get("include_fixtures", True)),
            framework_hint=_optional_str(data.get("framework_hint"), "execution_constraints.framework_hint"),
        )


@dataclass(frozen=True)
class TestCodeGenerationInput:
    task_id: str
    user_prompt: str | None = None
    plan: str | None = None
    story_units: list[StoryUnit] = field(default_factory=list)
    test_plan: str = ""
    test_cases: list[GeneratedTestCase] = field(default_factory=list)
    execution_constraints: TestCodeGenerationConstraints = field(
        default_factory=TestCodeGenerationConstraints,
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestCodeGenerationInput":
        if not isinstance(data, dict):
            raise ValueError("test code generation input must be an object")
        raw_story_units = data.get("story_units")
        raw_test_cases = data.get("test_cases")
        if not isinstance(raw_story_units, list) or not raw_story_units:
            raise ValueError("story_units must be a non-empty list")
        if not isinstance(raw_test_cases, list) or not raw_test_cases:
            raise ValueError("test_cases must be a non-empty list")
        return cls(
            task_id=_require_str(data.get("task_id"), "task_id"),
            user_prompt=_optional_str(data.get("user_prompt"), "user_prompt"),
            plan=_optional_str(data.get("plan"), "plan"),
            story_units=[StoryUnit.from_dict(item) for item in raw_story_units],
            test_plan=_require_str(data.get("test_plan"), "test_plan"),
            test_cases=[GeneratedTestCase.from_dict(item) for item in raw_test_cases],
            execution_constraints=TestCodeGenerationConstraints.from_dict(
                data.get("execution_constraints"),
            ),
        )


@dataclass(frozen=True)
class GeneratedTestFile:
    path: str
    language: str
    framework: str
    purpose: str
    related_test_case_ids: list[str]
    content: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeneratedTestFile":
        if not isinstance(data, dict):
            raise ValueError("test_file must be an object")
        return cls(
            path=_require_str(data.get("path"), "test_file.path"),
            language=_require_str(data.get("language"), "test_file.language").lower(),
            framework=_require_str(data.get("framework"), "test_file.framework"),
            purpose=_require_str(data.get("purpose"), "test_file.purpose"),
            related_test_case_ids=_require_list_of_str(
                data.get("related_test_case_ids"),
                "test_file.related_test_case_ids",
            ),
            content=_require_str(data.get("content"), "test_file.content"),
        )


@dataclass(frozen=True)
class TestCodeGenerationQualityChecks:
    has_test_file_content: bool
    all_files_are_tests: bool
    covers_all_input_test_cases: bool
    changed_files_match_generated_files: bool


@dataclass(frozen=True)
class TestCodeGenerationResult:
    implementation_plan: list[str]
    test_files: list[GeneratedTestFile]
    changed_files: list[str]
    rationale: str
    warnings: list[str]
    quality_checks: TestCodeGenerationQualityChecks
