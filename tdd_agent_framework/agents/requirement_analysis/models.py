from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from tdd_agent_framework.agents.requirement_feedback import GlobalFeedback, StoryFeedback

if TYPE_CHECKING:
    from tdd_agent_framework.agents.requirement_composition_verification.models import (
        RequirementCompositionVerificationResult,
    )


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


def _truncate_text(value: str | None, max_chars: int) -> str | None:
    if value is None or len(value) <= max_chars:
        return value
    return value[-max_chars:]


def _truncate_list(values: list[str], max_items: int, max_item_chars: int) -> list[str]:
    truncated: list[str] = []
    for item in values[:max_items]:
        if len(item) <= max_item_chars:
            truncated.append(item)
        else:
            truncated.append(item[:max_item_chars])
    return truncated


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
    max_story_units: int | None = 24
    max_capability_groups: int | None = 6

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ExecutionConstraints":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("execution_constraints must be an object")
        max_story_units = cls._nullable_positive_int(
            data.get("max_story_units", 24),
            "execution_constraints.max_story_units",
        )
        max_capability_groups = cls._nullable_positive_int(
            data.get("max_capability_groups", 6),
            "execution_constraints.max_capability_groups",
        )
        return cls(
            disallow_new_dependencies=bool(data.get("disallow_new_dependencies", False)),
            preserve_public_api=bool(data.get("preserve_public_api", False)),
            max_story_units=max_story_units,
            max_capability_groups=max_capability_groups,
        )

    @staticmethod
    def _nullable_positive_int(value: Any, field_name: str) -> int | None:
        if value is None:
            return None
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"{field_name} must be a positive integer or null")
        return value


@dataclass(frozen=True)
class RequirementAnalysisInput:
    max_open_files = 8
    max_diagnostics = 8
    max_recent_test_failures = 8
    max_revision_focus = 8
    max_git_diff_summary_chars = 4000
    max_previous_verification_summary_chars = 1200
    max_display_item_chars = 500

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
    global_feedback: GlobalFeedback | None = None
    story_feedback: StoryFeedback | None = None
    revision_focus: list[str] = field(default_factory=list)
    previous_verification_summary: str | None = None
    iteration: int = 1
    analysis_goal: str = "content_review"
    previous_analysis_result: dict[str, Any] | None = None
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
            open_files=_truncate_list(
                _optional_list_of_str(data.get("open_files"), "open_files"),
                cls.max_open_files,
                cls.max_display_item_chars,
            ),
            diagnostics=_truncate_list(
                _optional_list_of_display_str(data.get("diagnostics"), "diagnostics"),
                cls.max_diagnostics,
                cls.max_display_item_chars,
            ),
            recent_test_failures=_truncate_list(
                _optional_list_of_display_str(data.get("recent_test_failures"), "recent_test_failures"),
                cls.max_recent_test_failures,
                cls.max_display_item_chars,
            ),
            git_diff_summary=_truncate_text(
                _optional_str(data.get("git_diff_summary"), "git_diff_summary"),
                cls.max_git_diff_summary_chars,
            ),
            global_feedback=(
                GlobalFeedback.from_dict(data.get("global_feedback"))
                if data.get("global_feedback") is not None
                else None
            ),
            story_feedback=(
                StoryFeedback.from_dict(data.get("story_feedback"))
                if data.get("story_feedback") is not None
                else None
            ),
            revision_focus=_truncate_list(
                _optional_list_of_display_str(data.get("revision_focus"), "revision_focus"),
                cls.max_revision_focus,
                cls.max_display_item_chars,
            ),
            previous_verification_summary=_truncate_text(
                _optional_str(data.get("previous_verification_summary"), "previous_verification_summary"),
                cls.max_previous_verification_summary_chars,
            ),
            iteration=max(1, int(data.get("iteration", 1))),
            analysis_goal=cls._normalize_analysis_goal(data.get("analysis_goal")),
            previous_analysis_result=cls._normalize_optional_object(
                data.get("previous_analysis_result"),
                "previous_analysis_result",
            ),
            execution_constraints=ExecutionConstraints.from_dict(data.get("execution_constraints")),
        )

    @staticmethod
    def _normalize_analysis_goal(value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            return "content_review"
        normalized = value.strip()
        if normalized not in {"content_review", "composition_review"}:
            raise ValueError("analysis_goal must be content_review or composition_review")
        return normalized

    @staticmethod
    def _normalize_optional_object(value: Any, field_name: str) -> dict[str, Any] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be an object or null")
        return value


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
    story_kind: str
    title: str
    as_a: str
    when_context: str
    i_want: str
    so_that: str | None
    narrative: str
    actor: str
    goal: str
    business_value: str | None
    business_outcome: str
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
        story_kind = _optional_str(data.get("story_kind"), "story_unit.story_kind") or "user_outcome"
        title = _require_str(data.get("title"), "story_unit.title")
        as_a = _optional_str(data.get("as_a"), "story_unit.as_a") or _require_str(
            data.get("actor"),
            "story_unit.actor",
        )
        when_context = _optional_str(data.get("when_context"), "story_unit.when_context") or _require_str(
            data.get("context"),
            "story_unit.context",
        )
        i_want = _optional_str(data.get("i_want"), "story_unit.i_want") or _require_str(
            data.get("goal"),
            "story_unit.goal",
        )
        so_that = _optional_str(data.get("so_that"), "story_unit.so_that")
        business_value = _optional_str(data.get("business_value"), "story_unit.business_value")
        if so_that is None:
            so_that = business_value
        business_outcome = _optional_str(
            data.get("business_outcome"),
            "story_unit.business_outcome",
        ) or (so_that or i_want)
        # Structured story fields are the source of truth. We always rebuild the
        # normalized narrative so lightweight provider paraphrasing does not
        # break continuation rounds.
        narrative = cls._build_narrative(
            as_a=as_a,
            when_context=when_context,
            i_want=i_want,
            so_that=so_that,
        )
        return cls(
            id=_require_str(data.get("id"), "story_unit.id"),
            story_kind=story_kind,
            title=title,
            as_a=as_a,
            when_context=when_context,
            i_want=i_want,
            so_that=so_that,
            narrative=narrative,
            actor=as_a,
            goal=i_want,
            business_value=so_that,
            business_outcome=business_outcome,
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

    @staticmethod
    def _build_narrative(
        as_a: str,
        when_context: str,
        i_want: str,
        so_that: str | None,
    ) -> str:
        if so_that:
            return f"作为{as_a}，当{when_context}时，我希望{i_want}，从而{so_that}。"
        return f"作为{as_a}，当{when_context}时，我希望{i_want}。"


@dataclass(frozen=True)
class CapabilityGroup:
    id: str
    title: str
    goal: str
    scope: list[str]
    story_ids: list[str]
    priority: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityGroup":
        if not isinstance(data, dict):
            raise ValueError("capability_group must be an object")
        return cls(
            id=_require_str(data.get("id"), "capability_group.id"),
            title=_require_str(data.get("title"), "capability_group.title"),
            goal=_require_str(data.get("goal"), "capability_group.goal"),
            scope=_require_list_of_str(data.get("scope"), "capability_group.scope"),
            story_ids=_require_list_of_str(data.get("story_ids"), "capability_group.story_ids"),
            priority=_require_str(data.get("priority"), "capability_group.priority").lower(),
        )


@dataclass(frozen=True)
class AnalysisSummary:
    story_unit_count: int
    high_priority_count: int
    high_risk_count: int
    capability_group_count: int = 0


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
    capability_groups: list[CapabilityGroup] = field(default_factory=list)


@dataclass(frozen=True)
class VerificationIssue:
    id: str
    severity: str
    issue_type: str
    message: str
    affected_story_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VerificationIssue":
        if not isinstance(data, dict):
            raise ValueError("verification issue must be an object")
        return cls(
            id=_require_str(data.get("id"), "verification_issue.id"),
            severity=_require_str(data.get("severity"), "verification_issue.severity").lower(),
            issue_type=_require_str(
                data.get("type") if data.get("type") is not None else data.get("issue_type"),
                "verification_issue.type",
            ),
            message=_require_str(data.get("message"), "verification_issue.message"),
            affected_story_ids=_optional_list_of_str(
                data.get("affected_story_ids"),
                "verification_issue.affected_story_ids",
            ),
        )


@dataclass(frozen=True)
class VerificationQualityScore:
    scope_clarity: int
    testability: int
    dependency_sanity: int
    story_granularity: int

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "VerificationQualityScore":
        if data is None:
            return cls(scope_clarity=0, testability=0, dependency_sanity=0, story_granularity=0)
        if not isinstance(data, dict):
            raise ValueError("quality_score must be an object")
        return cls(
            scope_clarity=_score_value(data.get("scope_clarity"), "quality_score.scope_clarity"),
            testability=_score_value(data.get("testability"), "quality_score.testability"),
            dependency_sanity=_score_value(
                data.get("dependency_sanity"),
                "quality_score.dependency_sanity",
            ),
            story_granularity=_score_value(
                data.get("story_granularity"),
                "quality_score.story_granularity",
            ),
        )


@dataclass(frozen=True)
class RequirementVerificationResult:
    status: str
    summary: str
    issues: list[VerificationIssue]
    revision_guidance: list[str]
    quality_score: VerificationQualityScore

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RequirementVerificationResult":
        if not isinstance(data, dict):
            raise ValueError("requirement verification result must be an object")
        raw_issues = data.get("issues", [])
        if not isinstance(raw_issues, list):
            raise ValueError("verification issues must be a list")
        normalized_issues = []
        for index, item in enumerate(raw_issues, start=1):
            if isinstance(item, dict):
                normalized_issues.append(item)
                continue
            normalized_issues.append(
                {
                    "id": f"issue_{index}",
                    "severity": "medium",
                    "type": "unspecified_issue",
                    "message": str(item),
                    "affected_story_ids": [],
                }
            )
        status_value = data.get("status") if data.get("status") is not None else data.get("verdict")
        normalized_status = str(status_value).strip().lower() if status_value is not None else ""
        if normalized_status not in {"pass", "revise", "blocked"}:
            normalized_status = "revise" if normalized_issues else "pass"
        summary_value = data.get("summary")
        if not isinstance(summary_value, str) or not summary_value.strip():
            summary_value = (
                "发现需要修订的问题。"
                if normalized_issues
                else "当前需求拆解通过验证，可以进入下一环。"
            )
        return cls(
            status=normalized_status,
            summary=_require_str(summary_value, "verification.summary"),
            issues=[VerificationIssue.from_dict(item) for item in normalized_issues],
            revision_guidance=_optional_list_of_display_str(
                data.get("revision_guidance"),
                "verification.revision_guidance",
            ),
            quality_score=VerificationQualityScore.from_dict(data.get("quality_score")),
        )


@dataclass(frozen=True)
class RequirementAnalysisIteration:
    iteration: int
    analysis_summary: str
    verification_status: str
    issue_count: int
    revision_guidance: list[str] = field(default_factory=list)
    composition_verification_status: str | None = None
    composition_issue_count: int = 0
    composition_revision_guidance: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RequirementAnalysisPackage:
    package_id: str
    task_id: str
    status: str
    requirement_spec: RequirementSpec
    story_units: list[StoryUnit]
    analysis_summary: AnalysisSummary
    warnings: list[str]
    quality_checks: QualityChecks
    verification: RequirementVerificationResult
    iteration_count: int
    composition_verification: RequirementCompositionVerificationResult | None = None
    history: list[RequirementAnalysisIteration] = field(default_factory=list)
    verification_gate_summary: dict[str, Any] = field(default_factory=dict)
    user_review_guidance: dict[str, list[str]] = field(default_factory=dict)


def _score_value(value: Any, field_name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    if value < 0 or value > 100:
        raise ValueError(f"{field_name} must be between 0 and 100")
    return value


def build_analysis_summary(
    story_units: list[StoryUnit],
    capability_groups: list[CapabilityGroup] | None = None,
) -> AnalysisSummary:
    return AnalysisSummary(
        story_unit_count=len(story_units),
        high_priority_count=sum(1 for item in story_units if item.priority == "high"),
        high_risk_count=sum(1 for item in story_units if item.risk == "high"),
        capability_group_count=len(capability_groups or []),
    )
