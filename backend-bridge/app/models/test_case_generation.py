from __future__ import annotations

from pydantic import BaseModel, Field


class TestCaseGenerationSettingsPayload(BaseModel):
    enabled: bool = True
    provider_kind: str = "openai_compatible"
    provider_name: str
    model: str
    api_base: str
    api_key: str
    temperature: float = 0.2
    max_tokens: int = 4000
    timeout_seconds: float = 60.0


class StoryUnitPayload(BaseModel):
    id: str
    title: str
    actor: str
    goal: str
    business_value: str | None = None
    scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    priority: str
    risk: str
    test_focus: list[str] = Field(default_factory=list)
    implementation_hints: list[str] = Field(default_factory=list)


class TestCaseGenerationExecutionConstraintsPayload(BaseModel):
    max_test_cases_per_story: int = 6
    require_boundary_cases: bool = True
    require_negative_cases: bool = True


class TestCaseGenerationInputPayload(BaseModel):
    task_id: str
    user_prompt: str | None = None
    story_units: list[StoryUnitPayload] = Field(default_factory=list)
    execution_constraints: TestCaseGenerationExecutionConstraintsPayload = Field(
        default_factory=TestCaseGenerationExecutionConstraintsPayload,
    )


class TestCaseGenerationRunRequest(BaseModel):
    settings: TestCaseGenerationSettingsPayload
    input: TestCaseGenerationInputPayload
