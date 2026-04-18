from __future__ import annotations

from tdd_agent_framework.core import (
    AgentRunContext,
    BaseAgent,
    ProviderMessage,
    ProviderRequest,
)

from .models import RequirementAnalysisInput, RequirementAnalysisResult
from .parser import RequirementAnalysisParser
from .prompt_builder import RequirementAnalysisPromptBuilder
from .quality_checker import RequirementAnalysisQualityChecker


class RequirementAnalysisAgent(
    BaseAgent[RequirementAnalysisInput, RequirementAnalysisResult],
):
    name = "requirement_analysis"

    def __init__(
        self,
        provider,
        model_target,
        generation_config=None,
        prompt_builder: RequirementAnalysisPromptBuilder | None = None,
        parser: RequirementAnalysisParser | None = None,
        quality_checker: RequirementAnalysisQualityChecker | None = None,
    ) -> None:
        super().__init__(
            provider=provider,
            model_target=model_target,
            generation_config=generation_config,
        )
        self.prompt_builder = prompt_builder or RequirementAnalysisPromptBuilder()
        self.parser = parser or RequirementAnalysisParser()
        self.quality_checker = quality_checker or RequirementAnalysisQualityChecker()

    def build_request(
        self,
        data: RequirementAnalysisInput,
        context: AgentRunContext,
    ) -> ProviderRequest:
        return ProviderRequest(
            agent_name=self.name,
            task_id=context.task_id,
            model_target=self.model_target,
            system_prompt=self.prompt_builder.build_system_prompt(),
            messages=(
                ProviderMessage(
                    role="user",
                    content=self.prompt_builder.build_user_prompt(data),
                ),
            ),
            generation_config=self.generation_config,
            metadata={"trace_id": context.trace_id, **context.metadata},
        )

    def parse_response(self, response) -> RequirementAnalysisResult:
        return self.parser.parse(response)

    def finalize_output(
        self,
        data: RequirementAnalysisInput,
        context: AgentRunContext,
        output: RequirementAnalysisResult,
    ) -> RequirementAnalysisResult:
        return self.quality_checker.validate(data, output)
