from __future__ import annotations

import os
import re
from typing import Any, Literal

from pydantic import BaseModel, Field


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None else value.strip()


def _normalize_api_base(value: str) -> str:
    cleaned = value.strip().replace(" ", "")
    match = re.search(r"https?://[^\s\"'`）)]+", cleaned)
    if match:
        cleaned = match.group(0)
    return cleaned.strip("\"'`").rstrip("/")


class CodeImplementationSettingsPayload(BaseModel):
    provider_name: str = "zhipu"
    wire_api: Literal["chat_completions", "responses"] = "chat_completions"
    model: str = Field(default_factory=lambda: _env_str("GLM_MODEL", "GLM-4.7-Flash"))
    api_base: str = Field(
        default_factory=lambda: _normalize_api_base(
            _env_str("GLM_API_BASE", "https://api.z.ai/api/paas/v4"),
        ),
    )
    api_key: str = Field(default_factory=lambda: _env_str("GLM_API_KEY", ""))
    temperature: float = 0.1
    max_tokens: int = 12000
    timeout_seconds: float = 60.0
    max_request_seconds: float = 900.0


class CodeImplementationInputPayload(BaseModel):
    task_id: str
    repo_root: str
    user_prompt: str
    requirement_spec: dict[str, Any] = Field(default_factory=dict)
    story_units: list[dict[str, Any]] = Field(default_factory=list)
    test_plan: str
    test_cases: list[dict[str, Any]] = Field(default_factory=list)
    test_files: list[dict[str, Any]] = Field(default_factory=list)
    repository_context: dict[str, str] = Field(default_factory=dict)


class CodeImplementationRunRequest(BaseModel):
    settings: CodeImplementationSettingsPayload
    input: CodeImplementationInputPayload
