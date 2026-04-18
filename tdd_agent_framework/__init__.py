"""TDD 多智能体框架原型。"""

from .core import (
    AgentRunContext,
    BaseAgent,
    GenerationConfig,
    ModelProvider,
    ModelTarget,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
)
from .providers import OpenAICompatibleProvider, ProviderConfig, ProviderError
from .registry import AgentRegistry

__all__ = [
    "AgentRegistry",
    "AgentRunContext",
    "BaseAgent",
    "GenerationConfig",
    "ModelProvider",
    "ModelTarget",
    "ProviderMessage",
    "ProviderRequest",
    "ProviderResponse",
    "OpenAICompatibleProvider",
    "ProviderConfig",
    "ProviderError",
]
