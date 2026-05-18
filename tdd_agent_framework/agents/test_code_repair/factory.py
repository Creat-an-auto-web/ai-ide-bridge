from __future__ import annotations

from tdd_agent_framework.providers import OpenAICompatibleProvider

from .agent import TestCodeRepairAgent
from .service import TestCodeRepairService
from .settings import TestCodeRepairAgentSettings


def build_test_code_repair_service(
    settings: TestCodeRepairAgentSettings,
) -> TestCodeRepairService:
    if not settings.enabled:
        raise ValueError("test code repair agent is disabled")

    if settings.provider_kind != "openai_compatible":
        raise ValueError(f"unsupported provider_kind: {settings.provider_kind}")

    provider = OpenAICompatibleProvider(settings.to_provider_config())
    agent = TestCodeRepairAgent(
        provider=provider,
        model_target=settings.to_model_target(),
        generation_config=settings.to_generation_config(),
    )
    return TestCodeRepairService(agent)
