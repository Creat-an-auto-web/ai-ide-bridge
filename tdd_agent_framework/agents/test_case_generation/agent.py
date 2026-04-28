from __future__ import annotations

from tdd_agent_framework.core import (
    AgentRunContext,
    BaseAgent,
    ProviderMessage,
    ProviderRequest,
)

from .models import TestCaseGenerationInput, TestCaseGenerationResult
from .parser import TestCaseGenerationParser
from .prompt_builder import TestCaseGenerationPromptBuilder
from .quality_checker import TestCaseGenerationQualityChecker


class TestCaseGenerationAgent(
    BaseAgent[TestCaseGenerationInput, TestCaseGenerationResult],
):
    name = "test_case_generation"

    def __init__(
        self,
        provider,
        model_target,
        generation_config=None,
        prompt_builder: TestCaseGenerationPromptBuilder | None = None,
        parser: TestCaseGenerationParser | None = None,
        quality_checker: TestCaseGenerationQualityChecker | None = None,
    ) -> None:
        super().__init__(
            provider=provider,
            model_target=model_target,
            generation_config=generation_config,
        )
        self.prompt_builder = prompt_builder or TestCaseGenerationPromptBuilder()
        self.parser = parser or TestCaseGenerationParser()
        self.quality_checker = quality_checker or TestCaseGenerationQualityChecker()

    def build_request(
        self,
        data: TestCaseGenerationInput,
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

    def parse_response(self, response) -> TestCaseGenerationResult:
        raise NotImplementedError(
            "TestCaseGenerationAgent.parse_response is context-dependent; use finalize_output flow",
        )

    async def run(self, data: TestCaseGenerationInput, context: AgentRunContext) -> TestCaseGenerationResult:
        request = self.build_request(data, context)
        response = await self.provider.generate(request)
        parsed_output = self.parser.parse(response, expected_story_units=data.story_units)
        return self.finalize_output(data, context, parsed_output)

    def finalize_output(
        self,
        data: TestCaseGenerationInput,
        context: AgentRunContext,
        output: TestCaseGenerationResult,
    ) -> TestCaseGenerationResult:
        return self.quality_checker.validate(data, output)
