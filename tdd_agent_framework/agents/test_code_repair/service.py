from __future__ import annotations

from tdd_agent_framework.core import AgentRunContext

from .agent import TestCodeRepairAgent
from .models import TestCodeRepairInput


class TestCodeRepairService:
    def __init__(self, agent: TestCodeRepairAgent) -> None:
        self.agent = agent

    async def repair(
        self,
        repair_input: TestCodeRepairInput,
        trace_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ):
        return await self.agent.run(
            repair_input,
            AgentRunContext(
                task_id=repair_input.task_id,
                trace_id=trace_id,
                metadata=metadata or {},
            ),
        )
