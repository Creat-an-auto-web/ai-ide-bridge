from __future__ import annotations

from tdd_agent_framework.agents.test_case_generation.settings import (
    TestCaseGenerationAgentSettings,
)
from tdd_agent_framework.providers import OpenAICompatibleProvider

from .agent import TestCaseGenerationVerificationAgent
from .service import TestCaseGenerationVerificationService


def build_test_case_generation_verification_service(
    settings: TestCaseGenerationAgentSettings,
) -> TestCaseGenerationVerificationService:
    if not settings.enabled:
        raise ValueError("test case generation agent is disabled")

    if settings.provider_kind != "openai_compatible":
        raise ValueError(f"unsupported provider_kind: {settings.provider_kind}")

    provider = OpenAICompatibleProvider(settings.to_provider_config())
    agent = TestCaseGenerationVerificationAgent(
        provider=provider,
        model_target=settings.to_model_target(),
        generation_config=settings.to_generation_config(),
    )
    return TestCaseGenerationVerificationService(agent)
