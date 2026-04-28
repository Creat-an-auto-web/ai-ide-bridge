from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys

from app.models.test_case_generation import TestCaseGenerationRunRequest


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tdd_agent_framework.agents.test_case_generation import (  # noqa: E402
    TestCaseGenerationAgentSettings,
    TestCaseGenerationInput,
)
from tdd_agent_framework.orchestrators import TestCaseGenerationOrchestrator  # noqa: E402


class TestCaseGenerationBackendService:
    def __init__(self, orchestrator: TestCaseGenerationOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or TestCaseGenerationOrchestrator()

    async def run(self, payload: TestCaseGenerationRunRequest) -> dict:
        settings = TestCaseGenerationAgentSettings.from_dict(payload.settings.model_dump())
        generation_input = TestCaseGenerationInput.from_dict(payload.input.model_dump())
        result = await self.orchestrator.run(settings, generation_input)
        return asdict(result)
