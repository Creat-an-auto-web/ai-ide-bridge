from __future__ import annotations

from typing import Any

from app.models.test_code_execution import TestCodeExecutionRunRequest
from app.services.sandbox_execution_service import SandboxExecutionBackendService


class TestCodeExecutionBackendService:
    """Backward-compatible facade for the original execution endpoint."""

    def __init__(
        self,
        sandbox_service: SandboxExecutionBackendService | None = None,
    ) -> None:
        self.sandbox_service = sandbox_service or SandboxExecutionBackendService()

    async def run(self, payload: TestCodeExecutionRunRequest) -> dict[str, Any]:
        return await self.sandbox_service.run_legacy(payload)
