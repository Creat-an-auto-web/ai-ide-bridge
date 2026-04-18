from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    items: list[str] = []
    for item in value:
        items.append(_require_str(item, field_name))
    return items


def _optional_list_of_str(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    items: list[str] = []
    for item in value:
        items.append(_require_str(item, field_name))
    return items


def _optional_list_of_display_str(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    items: list[str] = []
    for item in value:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                items.append(stripped)
            continue
        items.append(str(item))
    return items


@dataclass(frozen=True)
class WorkspaceSummary:
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    key_modules: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "WorkspaceSummary":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("workspace_summary must be an object")
        return cls(
            languages=_optional_list_of_str(data.get("languages"), "workspace_summary.languages"),
            frameworks=_optional_list_of_str(
                data.get("frameworks"),
                "workspace_summary.frameworks",
            ),
            key_modules=_optional_list_of_str(
                data.get("key_modules"),
                "workspace_summary.key_modules",
            ),
        )


@dataclass(frozen=True)
class ExecutionConstraints:
    disallow_new_dependencies: bool = False
    preserve_public_api: bool = False
    max_story_units: int = 8

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ExecutionConstraints":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("execution_constraints must be an object")
        max_story_units = data.get("max_story_units", 8)
        if not isinstance(max_story_units, int) or max_story_units <= 0:
            raise ValueError("execution_constraints.max_story_units must be a positive integer")
        return cls(
            disallow_new_dependencies=bool(data.get("disallow_new_dependencies", False)),
            preserve_public_api=bool(data.get("preserve_public_api", False)),
            max_story_units=max_story_units,
        )


@dataclass(frozen=True)
class RequirementAnalysisInput:
    task_id: str
    mode: str
    user_prompt: str
    repo_root: str
    workspace_summary: WorkspaceSummary = field(default_factory=WorkspaceSummary)
    active_file: str | None = None
    selection: str | None = None
    open_files: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    recent_test_failures: list[str] = field(default_factory=list)
    git_diff_summary: str | None = None
    execution_constraints: ExecutionConstraints = field(default_factory=ExecutionConstraints)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RequirementAnalysisInput":
        if not isinstance(data, dict):
            raise ValueError("requirement analysis input must be an object")
        return cls(
            task_id=_require_str(data.get("task_id"), "task_id"),
            mode=_require_str(data.get("mode"), "mode"),
            user_prompt=_require_str(data.get("user_prompt"), "user_prompt"),
            repo_root=_require_str(data.get("repo_root"), "repo_root"),
            workspace_summary=WorkspaceSummary.from_dict(data.get("workspace_summary")),
            active_file=_optional_str(data.get("active_file"), "active_file"),
            selection=_optional_str(data.get("selection"), "selection"),
            open_files=_optional_list_of_str(data.get("open_files"), "open_files"),
            diagnostics=_optional_list_of_display_str(data.get("diagnostics"), "diagnostics"),
            recent_test_failures=_optional_list_of_display_str(
                data.get("recent_test_failures"),
                "recent_test_failures",
            ),
            git_diff_summary=_optional_str(data.get("git_diff_summary"), "git_diff_summary"),
            execution_constraints=ExecutionConstraints.from_dict(data.get("execution_constraints")),
        )


@dataclass(frozen=True)
class RequirementSpec:
    task_id: str
    version: int
    problem_statement: str
    product_goal: str
    scope: list[str]
    out_of_scope: list[str]
    constraints: list[str]
    assumptions: list[str]
    interfaces_or_contracts: list[str]
    acceptance_criteria: list[str]
    decomposition_strategy: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RequirementSpec":
        if not isinstance(data, dict):
            raise ValueError("requirement_spec must be an object")
        version = data.get("version", 1)
        if not isinstance(version, int) or version <= 0:
            raise ValueError("requirement_spec.version must be a positive integer")
        return cls(
            task_id=_require_str(data.get("task_id"), "requirement_spec.task_id"),
            version=version,
            problem_statement=_require_str(
                data.get("problem_statement"),
                "requirement_spec.problem_statement",
            ),
            product_goal=_require_str(data.get("product_goal"), "requirement_spec.product_goal"),
            scope=_require_list_of_str(data.get("scope"), "requirement_spec.scope"),
            out_of_scope=_optional_list_of_str(
                data.get("out_of_scope"),
                "requirement_spec.out_of_scope",
            ),
            constraints=_optional_list_of_str(
                data.get("constraints"),
                "requirement_spec.constraints",
            ),
            assumptions=_optional_list_of_str(
                data.get("assumptions"),
                "requirement_spec.assumptions",
            ),
            interfaces_or_contracts=_optional_list_of_str(
                data.get("interfaces_or_contracts"),
                "requirement_spec.interfaces_or_contracts",
            ),
            acceptance_criteria=_require_list_of_str(
                data.get("acceptance_criteria"),
                "requirement_spec.acceptance_criteria",
            ),
            decomposition_strategy=_require_str(
                data.get("decomposition_strategy"),
                "requirement_spec.decomposition_strategy",
            ),
        )


@dataclass(frozen=True)
class StoryUnit:
    id: str
    title: str
    actor: str
    goal: str
    business_value: str | None
    scope: list[str]
    out_of_scope: list[str]
    acceptance_criteria: list[str]
    dependencies: list[str]
    priority: str
    risk: str
    test_focus: list[str]
    implementation_hints: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryUnit":
        if not isinstance(data, dict):
            raise ValueError("story_unit must be an object")
        return cls(
            id=_require_str(data.get("id"), "story_unit.id"),
            title=_require_str(data.get("title"), "story_unit.title"),
            actor=_require_str(data.get("actor"), "story_unit.actor"),
            goal=_require_str(data.get("goal"), "story_unit.goal"),
            business_value=_optional_str(data.get("business_value"), "story_unit.business_value"),
            scope=_require_list_of_str(data.get("scope"), "story_unit.scope"),
            out_of_scope=_optional_list_of_str(data.get("out_of_scope"), "story_unit.out_of_scope"),
            acceptance_criteria=_require_list_of_str(
                data.get("acceptance_criteria"),
                "story_unit.acceptance_criteria",
            ),
            dependencies=_optional_list_of_str(data.get("dependencies"), "story_unit.dependencies"),
            priority=_require_str(data.get("priority"), "story_unit.priority").lower(),
            risk=_require_str(data.get("risk"), "story_unit.risk").lower(),
            test_focus=_require_list_of_str(data.get("test_focus"), "story_unit.test_focus"),
            implementation_hints=_optional_list_of_str(
                data.get("implementation_hints"),
                "story_unit.implementation_hints",
            ),
        )


@dataclass(frozen=True)
class AnalysisSummary:
    story_unit_count: int
    high_priority_count: int
    high_risk_count: int


@dataclass(frozen=True)
class QualityChecks:
    has_clear_scope: bool
    has_testable_ac: bool
    dependency_graph_valid: bool
    story_count_within_limit: bool


@dataclass(frozen=True)
class RequirementAnalysisResult:
    requirement_spec: RequirementSpec
    story_units: list[StoryUnit]
    analysis_summary: AnalysisSummary
    warnings: list[str]
    quality_checks: QualityChecks


def build_analysis_summary(story_units: list[StoryUnit]) -> AnalysisSummary:
    return AnalysisSummary(
        story_unit_count=len(story_units),
        high_priority_count=sum(1 for item in story_units if item.priority == "high"),
        high_risk_count=sum(1 for item in story_units if item.risk == "high"),
    )
