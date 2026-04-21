from __future__ import annotations

from tdd_agent_framework.agents.requirement_analysis.models import (
    RequirementVerificationResult,
)
from tdd_agent_framework.core import (
    AgentRunContext,
    BaseAgent,
    ProviderMessage,
    ProviderRequest,
)

from .models import RequirementVerificationInput
from .parser import RequirementVerificationParser
from .prompt_builder import RequirementVerificationPromptBuilder


class RequirementVerificationAgent(
    BaseAgent[RequirementVerificationInput, RequirementVerificationResult],
):
    name = "requirement_verification"

    def __init__(
        self,
        provider,
        model_target,
        generation_config=None,
        prompt_builder: RequirementVerificationPromptBuilder | None = None,
        parser: RequirementVerificationParser | None = None,
    ) -> None:
        super().__init__(
            provider=provider,
            model_target=model_target,
            generation_config=generation_config,
        )
        self.prompt_builder = prompt_builder or RequirementVerificationPromptBuilder()
        self.parser = parser or RequirementVerificationParser()

    def build_request(
        self,
        data: RequirementVerificationInput,
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

    def parse_response(self, response) -> RequirementVerificationResult:
        return self.parser.parse(response)
