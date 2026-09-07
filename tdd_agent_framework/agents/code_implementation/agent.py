from __future__ import annotations

from tdd_agent_framework.core import AgentRunContext, BaseAgent, ProviderMessage, ProviderRequest

from .models import CodeImplementationInput, CodeImplementationResult
from .parser import CodeImplementationParser
from .prompt_builder import CodeImplementationPromptBuilder
from .quality_checker import CodeImplementationQualityChecker


class CodeImplementationAgent(BaseAgent[CodeImplementationInput, CodeImplementationResult]):
    name = "code_implementation"

    def __init__(self, provider, model_target, generation_config=None) -> None:
        super().__init__(provider, model_target, generation_config)
        self.prompt_builder = CodeImplementationPromptBuilder()
        self.parser = CodeImplementationParser()
        self.quality_checker = CodeImplementationQualityChecker()

    def build_request(self, data: CodeImplementationInput, context: AgentRunContext) -> ProviderRequest:
        return ProviderRequest(
            agent_name=self.name,
            task_id=context.task_id,
            model_target=self.model_target,
            system_prompt=self.prompt_builder.build_system_prompt(),
            messages=(ProviderMessage("user", self.prompt_builder.build_user_prompt(data)),),
            generation_config=self.generation_config,
            metadata={"trace_id": context.trace_id, **context.metadata},
        )

    def parse_response(self, response) -> CodeImplementationResult:
        return self.parser.parse(response)

    def finalize_output(
        self,
        data: CodeImplementationInput,
        context: AgentRunContext,
        output: CodeImplementationResult,
    ) -> CodeImplementationResult:
        return self.quality_checker.validate(data, output)

