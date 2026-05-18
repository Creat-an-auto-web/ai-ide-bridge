from __future__ import annotations

from tdd_agent_framework.core import (
    AgentRunContext,
    BaseAgent,
    ProviderMessage,
    ProviderRequest,
)

from .models import TestCodeGenerationInput, TestCodeGenerationResult
from .parser import TestCodeGenerationParser
from .prompt_builder import TestCodeGenerationPromptBuilder
from .quality_checker import TestCodeGenerationQualityChecker


class TestCodeGenerationAgent(
    BaseAgent[TestCodeGenerationInput, TestCodeGenerationResult],
):
    name = "test_code_generation"

    def __init__(
        self,
        provider,
        model_target,
        generation_config=None,
        prompt_builder: TestCodeGenerationPromptBuilder | None = None,
        parser: TestCodeGenerationParser | None = None,
        quality_checker: TestCodeGenerationQualityChecker | None = None,
    ) -> None:
        super().__init__(
            provider=provider,
            model_target=model_target,
            generation_config=generation_config,
        )
        self.prompt_builder = prompt_builder or TestCodeGenerationPromptBuilder()
        self.parser = parser or TestCodeGenerationParser()
        self.quality_checker = quality_checker or TestCodeGenerationQualityChecker()

    def build_request(
        self,
        data: TestCodeGenerationInput,
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

    def parse_response(self, response) -> TestCodeGenerationResult:
        raise NotImplementedError(
            "TestCodeGenerationAgent.parse_response is context-dependent; use finalize_output flow",
        )

    async def run(self, data: TestCodeGenerationInput, context: AgentRunContext) -> TestCodeGenerationResult:
        request = self.build_request(data, context)
        response = await self.provider.generate(request)
        parsed_output = self.parser.parse(response)
        return self.finalize_output(data, context, parsed_output)

    def finalize_output(
        self,
        data: TestCodeGenerationInput,
        context: AgentRunContext,
        output: TestCodeGenerationResult,
    ) -> TestCodeGenerationResult:
        return self.quality_checker.validate(data, output)
