from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, field_name: str, *, required: bool = False) -> list[str]:
    if value is None and not required:
        return []
    if not isinstance(value, list) or (required and not value):
        raise ValueError(f"{field_name} must be a {'non-empty ' if required else ''}list")
    return [_required_text(item, field_name) for item in value]


@dataclass(frozen=True)
class GeneratedCodeFile:
    path: str
    language: str
    purpose: str
    content: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeneratedCodeFile":
        if not isinstance(data, dict):
            raise ValueError("generated file must be an object")
        path = _required_text(data.get("path"), "file.path").replace("\\", "/")
        pure_path = PurePosixPath(path)
        if pure_path.is_absolute() or ".." in pure_path.parts:
            raise ValueError(f"file.path must remain inside the repository: {path}")
        return cls(
            path=str(pure_path),
            language=_required_text(data.get("language", "text"), "file.language").lower(),
            purpose=_required_text(data.get("purpose"), "file.purpose"),
            content=_required_text(data.get("content"), "file.content"),
        )


@dataclass(frozen=True)
class CodeImplementationInput:
    task_id: str
    user_prompt: str
    requirement_spec: dict[str, Any]
    story_units: list[dict[str, Any]]
    test_plan: str
    test_cases: list[dict[str, Any]]
    test_files: list[dict[str, Any]]
    repository_context: dict[str, str]
    previous_files: list[GeneratedCodeFile] = field(default_factory=list)
    execution_result: dict[str, Any] | None = None
    iteration: int = 0


@dataclass(frozen=True)
class CodeImplementationQualityChecks:
    has_complete_file_content: bool
    keeps_test_baseline_immutable: bool
    changed_files_match_generated_files: bool
    paths_are_repository_relative: bool


@dataclass(frozen=True)
class CodeImplementationResult:
    implementation_plan: list[str]
    files: list[GeneratedCodeFile]
    changed_files: list[str]
    rationale: str
    test_command: list[str]
    warnings: list[str]
    quality_checks: CodeImplementationQualityChecks
