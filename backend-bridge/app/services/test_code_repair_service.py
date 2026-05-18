from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys

from app.models.test_code_repair import TestCodeRepairRunRequest


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tdd_agent_framework.agents.test_code_repair import (  # noqa: E402
    TestCodeRepairAgentSettings,
    TestCodeRepairInput,
)
from tdd_agent_framework.orchestrators import TestCodeRepairOrchestrator  # noqa: E402


class TestCodeRepairBackendService:
    def __init__(self, orchestrator: TestCodeRepairOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or TestCodeRepairOrchestrator()

    async def run(self, payload: TestCodeRepairRunRequest) -> dict:
        settings = TestCodeRepairAgentSettings.from_dict(payload.settings.model_dump())
        repair_input = TestCodeRepairInput.from_dict(payload.input.model_dump())
        result = await self.orchestrator.run(settings, repair_input)
        return asdict(result)
