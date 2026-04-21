from __future__ import annotations

from tdd_agent_framework.core import ProgressCallback
from tdd_agent_framework.providers import OpenAICompatibleProvider

from .agent import RequirementVerificationAgent
from .service import RequirementVerificationService


def build_requirement_verification_service(
    settings,
    progress_callback: ProgressCallback | None = None,
) -> RequirementVerificationService:
    if not settings.enabled:
        raise ValueError("requirement verification agent is disabled")

    if settings.provider_kind != "openai_compatible":
        raise ValueError(f"unsupported provider_kind: {settings.provider_kind}")

    provider = OpenAICompatibleProvider(
        settings.to_provider_config(),
        progress_callback=progress_callback,
    )
    agent = RequirementVerificationAgent(
        provider=provider,
        model_target=settings.to_model_target(),
        generation_config=settings.to_generation_config(),
    )
    return RequirementVerificationService(agent)
