from __future__ import annotations

from tdd_agent_framework.core import AgentRunContext

from .agent import TestCaseGenerationAgent
from .models import TestCaseGenerationInput, TestCaseGenerationResult


class TestCaseGenerationService:
    def __init__(self, agent: TestCaseGenerationAgent) -> None:
        self.agent = agent

    async def generate(
        self,
        generation_input: TestCaseGenerationInput,
        trace_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> TestCaseGenerationResult:
        return await self.agent.run(
            generation_input,
            AgentRunContext(
                task_id=generation_input.task_id,
                trace_id=trace_id,
                metadata=metadata or {},
            ),
        )
