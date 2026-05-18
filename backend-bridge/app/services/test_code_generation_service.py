from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys

from app.models.test_code_generation import TestCodeGenerationRunRequest


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tdd_agent_framework.agents.test_code_generation import (  # noqa: E402
    TestCodeGenerationAgentSettings,
    TestCodeGenerationInput,
)
from tdd_agent_framework.orchestrators import TestCodeGenerationOrchestrator  # noqa: E402


class TestCodeGenerationBackendService:
    def __init__(self, orchestrator: TestCodeGenerationOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or TestCodeGenerationOrchestrator()

    async def run(self, payload: TestCodeGenerationRunRequest) -> dict:
        settings = TestCodeGenerationAgentSettings.from_dict(payload.settings.model_dump())
        generation_input = TestCodeGenerationInput.from_dict(payload.input.model_dump())
        result = await self.orchestrator.run(settings, generation_input)
        return asdict(result)
