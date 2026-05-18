from __future__ import annotations

from tdd_agent_framework.core import (
    AgentRunContext,
    BaseAgent,
    ProviderMessage,
    ProviderRequest,
)

from .models import TestCodeRepairInput, TestCodeRepairResult
from .parser import TestCodeRepairParser
from .prompt_builder import TestCodeRepairPromptBuilder
from .quality_checker import TestCodeRepairQualityChecker


class TestCodeRepairAgent(
    BaseAgent[TestCodeRepairInput, TestCodeRepairResult],
):
    name = "test_code_repair"

    def __init__(
        self,
        provider,
        model_target,
        generation_config=None,
        prompt_builder: TestCodeRepairPromptBuilder | None = None,
        parser: TestCodeRepairParser | None = None,
        quality_checker: TestCodeRepairQualityChecker | None = None,
    ) -> None:
        super().__init__(
            provider=provider,
            model_target=model_target,
            generation_config=generation_config,
        )
        self.prompt_builder = prompt_builder or TestCodeRepairPromptBuilder()
        self.parser = parser or TestCodeRepairParser()
        self.quality_checker = quality_checker or TestCodeRepairQualityChecker()

    def build_request(
        self,
        data: TestCodeRepairInput,
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

    def parse_response(self, response) -> TestCodeRepairResult:
        raise NotImplementedError(
            "TestCodeRepairAgent.parse_response is context-dependent; use finalize_output flow",
        )

    async def run(self, data: TestCodeRepairInput, context: AgentRunContext) -> TestCodeRepairResult:
        request = self.build_request(data, context)
        response = await self.provider.generate(request)
        parsed_output = self.parser.parse(response)
        return self.finalize_output(data, context, parsed_output)

    def finalize_output(
        self,
        data: TestCodeRepairInput,
        context: AgentRunContext,
        output: TestCodeRepairResult,
    ) -> TestCodeRepairResult:
        return self.quality_checker.validate(data, output)
