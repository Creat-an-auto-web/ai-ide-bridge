from __future__ import annotations

from tdd_agent_framework.agents.test_case_generation import (
    TestCaseGenerationAgentSettings,
    TestCaseGenerationInput,
    TestCaseGenerationResult,
    build_test_case_generation_service,
)


class TestCaseGenerationOrchestrator:
    def __init__(self) -> None:
        self.name = "test_case_generation_orchestrator"

    async def run(
        self,
        settings: TestCaseGenerationAgentSettings,
        generation_input: TestCaseGenerationInput,
    ) -> TestCaseGenerationResult:
        service = build_test_case_generation_service(settings)
        return await service.generate(
            generation_input,
            metadata={"orchestrator": self.name},
        )
