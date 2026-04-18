from __future__ import annotations

from pydantic import BaseModel, Field


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


class RequirementAnalysisWorkspaceSummaryPayload(BaseModel):
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    key_modules: list[str] = Field(default_factory=list)


class RequirementAnalysisExecutionConstraintsPayload(BaseModel):
    disallow_new_dependencies: bool = False
    preserve_public_api: bool = False
    max_story_units: int = 8


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
    execution_constraints: RequirementAnalysisExecutionConstraintsPayload = Field(
        default_factory=RequirementAnalysisExecutionConstraintsPayload
    )


class RequirementAnalysisRunRequest(BaseModel):
    settings: RequirementAnalysisSettingsPayload
    input: RequirementAnalysisInputPayload
