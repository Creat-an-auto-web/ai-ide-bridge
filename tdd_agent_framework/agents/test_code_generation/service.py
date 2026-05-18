from __future__ import annotations

from tdd_agent_framework.core import AgentRunContext

from .agent import TestCodeGenerationAgent
from .models import TestCodeGenerationInput


class TestCodeGenerationService:
    def __init__(self, agent: TestCodeGenerationAgent) -> None:
        self.agent = agent

    async def generate(
        self,
        generation_input: TestCodeGenerationInput,
        trace_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ):
        return await self.agent.run(
            generation_input,
            AgentRunContext(
                task_id=generation_input.task_id,
                trace_id=trace_id,
                metadata=metadata or {},
            ),
        )
