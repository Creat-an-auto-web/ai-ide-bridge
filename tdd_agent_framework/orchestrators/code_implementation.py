from __future__ import annotations

from tdd_agent_framework.agents.code_implementation import (
    CodeImplementationAgentSettings,
    CodeImplementationInput,
    build_code_implementation_service,
)
from tdd_agent_framework.core import ProgressCallback


class CodeImplementationOrchestrator:
    name = "code_implementation_orchestrator"

    async def run(
        self,
        settings: CodeImplementationAgentSettings,
        implementation_input: CodeImplementationInput,
        progress_callback: ProgressCallback | None = None,
    ):
        service = build_code_implementation_service(settings, progress_callback)
        return await service.implement(
            implementation_input,
            metadata={"orchestrator": self.name, "iteration": implementation_input.iteration},
        )

