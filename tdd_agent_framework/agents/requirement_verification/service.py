from __future__ import annotations

from tdd_agent_framework.core import AgentRunContext

from .agent import RequirementVerificationAgent
from .models import RequirementVerificationInput


class RequirementVerificationService:
    def __init__(self, agent: RequirementVerificationAgent) -> None:
        self.agent = agent

    async def verify(
        self,
        verification_input: RequirementVerificationInput,
        trace_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ):
        return await self.agent.run(
            verification_input,
            AgentRunContext(
                task_id=verification_input.analysis_input.task_id,
                trace_id=trace_id,
                metadata=metadata or {},
            ),
        )
