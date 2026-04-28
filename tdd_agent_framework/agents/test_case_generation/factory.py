from __future__ import annotations

from tdd_agent_framework.providers import OpenAICompatibleProvider

from .agent import TestCaseGenerationAgent
from .service import TestCaseGenerationService
from .settings import TestCaseGenerationAgentSettings


def build_test_case_generation_service(
    settings: TestCaseGenerationAgentSettings,
) -> TestCaseGenerationService:
    if not settings.enabled:
        raise ValueError("test case generation agent is disabled")

    if settings.provider_kind != "openai_compatible":
        raise ValueError(f"unsupported provider_kind: {settings.provider_kind}")

    provider = OpenAICompatibleProvider(settings.to_provider_config())
    agent = TestCaseGenerationAgent(
        provider=provider,
        model_target=settings.to_model_target(),
        generation_config=settings.to_generation_config(),
    )
    return TestCaseGenerationService(agent)
