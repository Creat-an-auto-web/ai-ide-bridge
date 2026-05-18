from __future__ import annotations

from tdd_agent_framework.providers import OpenAICompatibleProvider

from .agent import TestCodeGenerationAgent
from .service import TestCodeGenerationService
from .settings import TestCodeGenerationAgentSettings


def build_test_code_generation_service(
    settings: TestCodeGenerationAgentSettings,
) -> TestCodeGenerationService:
    if not settings.enabled:
        raise ValueError("test code generation agent is disabled")

    if settings.provider_kind != "openai_compatible":
        raise ValueError(f"unsupported provider_kind: {settings.provider_kind}")

    provider = OpenAICompatibleProvider(settings.to_provider_config())
    agent = TestCodeGenerationAgent(
        provider=provider,
        model_target=settings.to_model_target(),
        generation_config=settings.to_generation_config(),
    )
    return TestCodeGenerationService(agent)
