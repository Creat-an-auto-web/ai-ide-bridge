from __future__ import annotations

from tdd_agent_framework.core import AgentRunContext

from .agent import RequirementAnalysisAgent
from .models import RequirementAnalysisInput, RequirementAnalysisResult


class RequirementAnalysisService:
    def __init__(self, agent: RequirementAnalysisAgent) -> None:
        self.agent = agent

    async def analyze(
        self,
        analysis_input: RequirementAnalysisInput,
        trace_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> RequirementAnalysisResult:
        return await self.agent.run(
            analysis_input,
            AgentRunContext(
                task_id=analysis_input.task_id,
                trace_id=trace_id,
                metadata=metadata or {},
            ),
        )
