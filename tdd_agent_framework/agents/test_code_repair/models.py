from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tdd_agent_framework.agents.requirement_analysis import StoryUnit
from tdd_agent_framework.agents.test_case_generation import GeneratedTestCase
from tdd_agent_framework.agents.test_code_generation import GeneratedTestFile


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


@dataclass(frozen=True)
class TestExecutionSummary:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    failed_tests: list[str]
    workspace_diff: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestExecutionSummary":
        if not isinstance(data, dict):
            raise ValueError("execution_result must be an object")
        failed_tests = data.get("failed_tests", [])
        if not isinstance(failed_tests, list):
            raise ValueError("execution_result.failed_tests must be a list")
        exit_code = data.get("exit_code")
        if not isinstance(exit_code, int):
            raise ValueError("execution_result.exit_code must be an integer")
        return cls(
            command=_require_str(data.get("command"), "execution_result.command"),
            exit_code=exit_code,
            stdout=str(data.get("stdout", "")),
            stderr=str(data.get("stderr", "")),
            failed_tests=[str(item).strip() for item in failed_tests if str(item).strip()],
            workspace_diff=_optional_str(data.get("workspace_diff"), "execution_result.workspace_diff"),
        )


@dataclass(frozen=True)
class TestCodeRepairInput:
    task_id: str
    user_prompt: str | None = None
    plan: str | None = None
    story_units: list[StoryUnit] = field(default_factory=list)
    test_plan: str = ""
    test_cases: list[GeneratedTestCase] = field(default_factory=list)
    test_files: list[GeneratedTestFile] = field(default_factory=list)
    execution_result: TestExecutionSummary | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestCodeRepairInput":
        if not isinstance(data, dict):
            raise ValueError("test code repair input must be an object")
        raw_story_units = data.get("story_units")
        raw_test_cases = data.get("test_cases")
        raw_test_files = data.get("test_files")
        if not isinstance(raw_story_units, list) or not raw_story_units:
            raise ValueError("story_units must be a non-empty list")
        if not isinstance(raw_test_cases, list) or not raw_test_cases:
            raise ValueError("test_cases must be a non-empty list")
        if not isinstance(raw_test_files, list) or not raw_test_files:
            raise ValueError("test_files must be a non-empty list")
        return cls(
            task_id=_require_str(data.get("task_id"), "task_id"),
            user_prompt=_optional_str(data.get("user_prompt"), "user_prompt"),
            plan=_optional_str(data.get("plan"), "plan"),
            story_units=[StoryUnit.from_dict(item) for item in raw_story_units],
            test_plan=_require_str(data.get("test_plan"), "test_plan"),
            test_cases=[GeneratedTestCase.from_dict(item) for item in raw_test_cases],
            test_files=[GeneratedTestFile.from_dict(item) for item in raw_test_files],
            execution_result=TestExecutionSummary.from_dict(data.get("execution_result")),
        )


@dataclass(frozen=True)
class TestCodeRepairQualityChecks:
    has_test_file_content: bool
    covers_all_original_files: bool
    keeps_test_scope: bool


@dataclass(frozen=True)
class TestCodeRepairResult:
    repair_plan: list[str]
    test_files: list[GeneratedTestFile]
    changed_files: list[str]
    reasoning_summary: str
    warnings: list[str]
    quality_checks: TestCodeRepairQualityChecks
