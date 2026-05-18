from __future__ import annotations

from tdd_agent_framework.agents.test_code_generation import (
    TestCodeGenerationAgentSettings,
    TestCodeGenerationInput,
    TestCodeGenerationResult,
    build_test_code_generation_service,
)


class TestCodeGenerationOrchestrator:
    def __init__(self) -> None:
        self.name = "test_code_generation_orchestrator"

    async def run(
        self,
        settings: TestCodeGenerationAgentSettings,
        generation_input: TestCodeGenerationInput,
    ) -> TestCodeGenerationResult:
        service = build_test_code_generation_service(settings)
        return await service.generate(
            generation_input,
            metadata={"orchestrator": self.name},
        )
