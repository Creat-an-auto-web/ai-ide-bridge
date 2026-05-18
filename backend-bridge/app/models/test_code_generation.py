from __future__ import annotations

import os
import re

from pydantic import BaseModel, Field


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _normalize_api_base(value: str) -> str:
    cleaned = value.strip().replace(" ", "")
    match = re.search(r"https?://[^\s\"'`）)]+", cleaned)
    if match:
        cleaned = match.group(0)
    cleaned = cleaned.strip("\"'`")
    while cleaned.endswith("/"):
        cleaned = cleaned[:-1]
    return cleaned


class TestCodeGenerationSettingsPayload(BaseModel):
    enabled: bool = True
    provider_kind: str = "openai_compatible"
    provider_name: str = "zhipu"
    model: str = Field(default_factory=lambda: _env_str("GLM_MODEL", "GLM-4.7-Flash"))
    api_base: str = Field(
        default_factory=lambda: _normalize_api_base(
            _env_str("GLM_API_BASE", "https://api.z.ai/api/paas/v4"),
        ),
    )
    api_key: str = Field(default_factory=lambda: _env_str("GLM_API_KEY", ""))
    temperature: float = 0.2
    max_tokens: int = 4000
    timeout_seconds: float = 60.0


class StoryUnitPayload(BaseModel):
    id: str
    story_kind: str | None = None
    title: str
    as_a: str | None = None
    when_context: str | None = None
    i_want: str | None = None
    so_that: str | None = None
    narrative: str | None = None
    actor: str
    context: str | None = None
    goal: str
    business_value: str | None = None
    business_outcome: str | None = None
    scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    priority: str
    risk: str
    test_focus: list[str] = Field(default_factory=list)
    implementation_hints: list[str] = Field(default_factory=list)


class GeneratedTestCasePayload(BaseModel):
    id: str
    story_id: str
    title: str
    level: str
    category: str
    purpose: str
    preconditions: list[str] = Field(default_factory=list)
    test_input: dict = Field(default_factory=dict)
    steps: list[str] = Field(default_factory=list)
    expected_result: str
    acceptance_criteria_refs: list[str] = Field(default_factory=list)
    priority: str
    automatable: bool = True


class TestCodeGenerationExecutionConstraintsPayload(BaseModel):
    max_test_files: int = 4
    prefer_existing_test_stack: bool = True
    include_fixtures: bool = True
    framework_hint: str | None = None


class TestCodeGenerationInputPayload(BaseModel):
    task_id: str
    user_prompt: str | None = None
    plan: str | None = None
    story_units: list[StoryUnitPayload] = Field(default_factory=list)
    test_plan: str
    test_cases: list[GeneratedTestCasePayload] = Field(default_factory=list)
    execution_constraints: TestCodeGenerationExecutionConstraintsPayload = Field(
        default_factory=TestCodeGenerationExecutionConstraintsPayload,
    )


class TestCodeGenerationRunRequest(BaseModel):
    settings: TestCodeGenerationSettingsPayload
    input: TestCodeGenerationInputPayload
