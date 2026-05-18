from __future__ import annotations

from tdd_agent_framework.agents.test_code_repair import (
    TestCodeRepairAgentSettings,
    TestCodeRepairInput,
    TestCodeRepairResult,
    build_test_code_repair_service,
)


class TestCodeRepairOrchestrator:
    def __init__(self) -> None:
        self.name = "test_code_repair_orchestrator"

    async def run(
        self,
        settings: TestCodeRepairAgentSettings,
        repair_input: TestCodeRepairInput,
    ) -> TestCodeRepairResult:
        service = build_test_code_repair_service(settings)
        return await service.repair(
            repair_input,
            metadata={"orchestrator": self.name},
        )
