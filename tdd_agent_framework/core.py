from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar


InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class ModelTarget:
    provider: str
    model: str
    api_base: str | None = None


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float = 0.2
    max_tokens: int = 4000
    response_format: str = "json_object"


@dataclass(frozen=True)
class ProviderMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ProviderRequest:
    agent_name: str
    task_id: str
    model_target: ModelTarget
    system_prompt: str
    messages: tuple[ProviderMessage, ...]
    generation_config: GenerationConfig = field(default_factory=GenerationConfig)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponse:
    raw_text: str
    parsed_json: dict[str, Any] | None = None
    model_target: ModelTarget | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRunContext:
    task_id: str
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelProvider(Protocol):
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        ...


class BaseAgent(Generic[InputT, OutputT]):
    name: str = "base_agent"

    def __init__(
        self,
        provider: ModelProvider,
        model_target: ModelTarget,
        generation_config: GenerationConfig | None = None,
    ) -> None:
        self.provider = provider
        self.model_target = model_target
        self.generation_config = generation_config or GenerationConfig()

    async def run(self, data: InputT, context: AgentRunContext) -> OutputT:
        request = self.build_request(data, context)
        response = await self.provider.generate(request)
        parsed_output = self.parse_response(response)
        return self.finalize_output(data, context, parsed_output)

    def build_request(self, data: InputT, context: AgentRunContext) -> ProviderRequest:
        raise NotImplementedError

    def parse_response(self, response: ProviderResponse) -> OutputT:
        raise NotImplementedError

    def finalize_output(
        self,
        data: InputT,
        context: AgentRunContext,
        output: OutputT,
    ) -> OutputT:
        return output
