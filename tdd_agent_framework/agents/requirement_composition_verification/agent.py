from __future__ import annotations

from tdd_agent_framework.core import (
    AgentRunContext,
    BaseAgent,
    ProviderMessage,
    ProviderRequest,
)

from .models import (
    RequirementCompositionVerificationInput,
    RequirementCompositionVerificationResult,
)
from .parser import RequirementCompositionVerificationParser
from .prompt_builder import RequirementCompositionVerificationPromptBuilder


class RequirementCompositionVerificationAgent(
    BaseAgent[
        RequirementCompositionVerificationInput,
        RequirementCompositionVerificationResult,
    ],
):
    name = "requirement_composition_verification"

    def __init__(
        self,
        provider,
        model_target,
        generation_config=None,
        prompt_builder: RequirementCompositionVerificationPromptBuilder | None = None,
        parser: RequirementCompositionVerificationParser | None = None,
    ) -> None:
        super().__init__(
            provider=provider,
            model_target=model_target,
            generation_config=generation_config,
        )
        self.prompt_builder = prompt_builder or RequirementCompositionVerificationPromptBuilder()
        self.parser = parser or RequirementCompositionVerificationParser()

    def build_request(
        self,
        data: RequirementCompositionVerificationInput,
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

    def parse_response(self, response) -> RequirementCompositionVerificationResult:
        return self.parser.parse(response)
