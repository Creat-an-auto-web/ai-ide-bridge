from __future__ import annotations

from tdd_agent_framework.core import AgentRunContext

from .agent import CodeImplementationAgent
from .models import CodeImplementationInput


class CodeImplementationService:
    def __init__(self, agent: CodeImplementationAgent) -> None:
        self.agent = agent

    async def implement(self, data: CodeImplementationInput, metadata: dict | None = None):
        return await self.agent.run(
            data,
            AgentRunContext(task_id=data.task_id, metadata=metadata or {}),
        )

