from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class RequirementAnalysisFeedbackAppliesToPayload(BaseModel):
    capability_group_ids: list[str] = Field(default_factory=list)
    story_ids: list[str] = Field(default_factory=list)


class RequirementAnalysisGlobalFeedbackPayload(BaseModel):
    feedback_id: str
    package_id: str | None = None
    task_id: str
    kind: str = "global_feedback"
    author_role: str | None = None
    feedback_type: str
    feedback_text: str
    applies_to: RequirementAnalysisFeedbackAppliesToPayload | None = None
    expected_action: str | None = None
    created_at: str | None = None


class RequirementAnalysisStoryFeedbackPayload(BaseModel):
    feedback_id: str
    package_id: str | None = None
    task_id: str
    kind: str = "story_feedback"
    author_role: str | None = None
    story_id: str
    feedback_type: str
    feedback_text: str
    expected_action: str | None = None
    created_at: str | None = None


class RequirementAnalysisSettingsPayload(BaseModel):
    enabled: bool = True
    provider_kind: str = "openai_compatible"
    provider_name: str
    model: str
    api_base: str
    api_key: str
    temperature: float = 0.2
    max_tokens: int = 4000
    timeout_seconds: float = 60.0
    max_request_seconds: float = 900.0
    first_round_max_capability_groups: int | None = 4
    first_round_max_story_units: int | None = 12
    second_round_max_capability_groups: int | None = 6
    second_round_max_story_units: int | None = 24
    later_round_max_capability_groups: int | None = None
    later_round_max_story_units: int | None = None


class RequirementAnalysisWorkspaceSummaryPayload(BaseModel):
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    key_modules: list[str] = Field(default_factory=list)


class RequirementAnalysisExecutionConstraintsPayload(BaseModel):
    disallow_new_dependencies: bool = False
    preserve_public_api: bool = False
    max_story_units: int | None = 24
    max_capability_groups: int | None = 6


class RequirementAnalysisInputPayload(BaseModel):
    task_id: str
    mode: str
    user_prompt: str
    repo_root: str
    workspace_summary: RequirementAnalysisWorkspaceSummaryPayload = Field(
        default_factory=RequirementAnalysisWorkspaceSummaryPayload
    )
    active_file: str | None = None
    selection: str | None = None
    open_files: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    recent_test_failures: list[str] = Field(default_factory=list)
    git_diff_summary: str = ""
    global_feedback: RequirementAnalysisGlobalFeedbackPayload | None = None
    story_feedback: RequirementAnalysisStoryFeedbackPayload | None = None
    revision_focus: list[str] = Field(default_factory=list)
    previous_verification_summary: str | None = None
    iteration: int = 1
    analysis_goal: str = "content_review"
    previous_analysis_result: dict[str, Any] | None = None
    execution_constraints: RequirementAnalysisExecutionConstraintsPayload = Field(
        default_factory=RequirementAnalysisExecutionConstraintsPayload
    )


class RequirementAnalysisRunRequest(BaseModel):
    settings: RequirementAnalysisSettingsPayload
    input: RequirementAnalysisInputPayload
