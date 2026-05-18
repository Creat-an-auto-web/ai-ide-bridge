from __future__ import annotations

from pydantic import BaseModel, Field


class GeneratedTestFilePayload(BaseModel):
    path: str
    language: str
    framework: str
    purpose: str
    related_test_case_ids: list[str] = Field(default_factory=list)
    content: str


class TestCodeExecutionInputPayload(BaseModel):
    task_id: str
    repo_root: str
    test_files: list[GeneratedTestFilePayload] = Field(default_factory=list)
    test_command: str | None = None
    timeout_seconds: int = 120


class TestCodeExecutionRunRequest(BaseModel):
    input: TestCodeExecutionInputPayload
