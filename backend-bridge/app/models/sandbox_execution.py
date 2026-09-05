from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


SandboxExecutionStatus = Literal[
    "passed",
    "failed",
    "timed_out",
    "cancelled",
    "blocked",
    "infrastructure_error",
]

SandboxRuntime = Literal["local_copy", "docker"]
SandboxNetworkMode = Literal["allow", "deny"]


def _new_run_id() -> str:
    return f"exec_{uuid4().hex[:12]}"


class SandboxWorkspacePayload(BaseModel):
    repo_root: str = Field(min_length=1)
    base_revision: str | None = None


class SandboxTestFilePayload(BaseModel):
    path: str = Field(min_length=1)
    content: str
    language: str = ""
    framework: str = ""
    purpose: str = ""
    related_test_case_ids: list[str] = Field(default_factory=list)


class SandboxCommandPayload(BaseModel):
    argv: list[str] = Field(min_length=1)
    cwd: str = "."
    environment: dict[str, str] = Field(default_factory=dict)

    @field_validator("argv")
    @classmethod
    def validate_argv(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if not normalized or not normalized[0]:
            raise ValueError("command.argv must start with a non-empty executable")
        if any("\x00" in item for item in normalized):
            raise ValueError("command.argv must not contain NUL characters")
        return normalized

    @field_validator("cwd")
    @classmethod
    def validate_cwd(cls, value: str) -> str:
        normalized = value.strip() or "."
        if "\x00" in normalized:
            raise ValueError("command.cwd must not contain NUL characters")
        return normalized


class SandboxExecutionPolicyPayload(BaseModel):
    runtime: SandboxRuntime = "local_copy"
    network: SandboxNetworkMode = "deny"
    timeout_seconds: int = Field(default=120, gt=0)
    max_output_bytes: int = Field(default=262144, gt=0)
    retain_artifacts: bool = True
    allow_workspace_changes: bool = False


class DockerRuntimeStatusPayload(BaseModel):
    available: bool
    command: str
    server_version: str | None = None
    detail: str


class SandboxProvenancePayload(BaseModel):
    requirement_package_id: str | None = None
    test_case_result_id: str | None = None
    test_code_result_id: str | None = None


class SandboxExecutionRunRequest(BaseModel):
    protocol_version: Literal["sandbox-execution.v1"] = "sandbox-execution.v1"
    task_id: str = Field(min_length=1)
    run_id: str = Field(default_factory=_new_run_id)
    workspace: SandboxWorkspacePayload
    test_files: list[SandboxTestFilePayload] = Field(min_length=1)
    command: SandboxCommandPayload | None = None
    execution_policy: SandboxExecutionPolicyPayload = Field(
        default_factory=SandboxExecutionPolicyPayload,
    )
    provenance: SandboxProvenancePayload = Field(
        default_factory=SandboxProvenancePayload,
    )


class SandboxCommandResultPayload(BaseModel):
    argv: list[str]
    cwd: str


class SandboxExecutionSummaryPayload(BaseModel):
    command: SandboxCommandResultPayload
    runtime: SandboxRuntime
    sandbox_id: str
    workspace_isolated: bool
    network_isolated: bool
    duration_ms: int
    exit_code: int | None = None
    signal: int | None = None
    termination_reason: str


class SandboxTestSummaryPayload(BaseModel):
    framework: str | None = None
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    failed_tests: list[str] = Field(default_factory=list)
    passed_tests: list[str] = Field(default_factory=list)


class SandboxOutputsPayload(BaseModel):
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False
    workspace_diff: str = ""
    artifacts: list[str] = Field(default_factory=list)


class SandboxFailurePayload(BaseModel):
    kind: str
    summary: str
    repair_targets: list[str] = Field(default_factory=list)
    related_test_case_ids: list[str] = Field(default_factory=list)


class SandboxExecutionResultPayload(BaseModel):
    protocol_version: str
    task_id: str
    run_id: str
    status: SandboxExecutionStatus
    execution: SandboxExecutionSummaryPayload
    test_summary: SandboxTestSummaryPayload
    outputs: SandboxOutputsPayload
    failure: SandboxFailurePayload | None = None
    warnings: list[str] = Field(default_factory=list)
    provenance: SandboxProvenancePayload = Field(
        default_factory=SandboxProvenancePayload,
    )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
