from __future__ import annotations

from tdd_agent_framework.core import AgentRunContext

from .agent import TestCaseGenerationVerificationAgent
from .models import TestCaseGenerationVerificationInput


class TestCaseGenerationVerificationService:
    def __init__(self, agent: TestCaseGenerationVerificationAgent) -> None:
        self.agent = agent

    async def verify(
        self,
        verification_input: TestCaseGenerationVerificationInput,
        trace_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ):
        return await self.agent.run(
            verification_input,
            AgentRunContext(
                task_id=verification_input.generation_input.task_id,
                trace_id=trace_id,
                metadata=metadata or {},
            ),
        )
