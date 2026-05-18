from __future__ import annotations

from dataclasses import replace

from tdd_agent_framework.agents.test_case_generation import (
    TestCaseGenerationAgentSettings,
    TestCaseGenerationInput,
    TestCaseGenerationResult,
    build_test_case_generation_service,
)
from tdd_agent_framework.agents.test_case_generation_verification import (
    TestCaseGenerationVerificationInput,
    build_test_case_generation_verification_service,
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
        result = await service.generate(
            generation_input,
            metadata={"orchestrator": self.name},
        )
        if generation_input.plan:
            verifier = build_test_case_generation_verification_service(settings)
            completion_check = await verifier.verify(
                TestCaseGenerationVerificationInput(
                    plan=generation_input.plan,
                    generation_input=generation_input,
                    generation_result=result,
                ),
                metadata={
                    "orchestrator": self.name,
                    "stage": "completion_check",
                },
            )
            return replace(result, completion_check=completion_check)
        return result
