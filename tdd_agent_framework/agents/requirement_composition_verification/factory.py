from __future__ import annotations

from tdd_agent_framework.core import ProgressCallback
from tdd_agent_framework.providers import OpenAICompatibleProvider

from .agent import RequirementCompositionVerificationAgent
from .service import RequirementCompositionVerificationService


def build_requirement_composition_verification_service(
    settings,
    progress_callback: ProgressCallback | None = None,
) -> RequirementCompositionVerificationService:
    if not settings.enabled:
        raise ValueError("requirement composition verification agent is disabled")

    if settings.provider_kind != "openai_compatible":
        raise ValueError(f"unsupported provider_kind: {settings.provider_kind}")

    provider = OpenAICompatibleProvider(
        settings.to_provider_config(),
        progress_callback=progress_callback,
    )
    agent = RequirementCompositionVerificationAgent(
        provider=provider,
        model_target=settings.to_model_target(),
        generation_config=settings.to_generation_config(),
    )
    return RequirementCompositionVerificationService(agent)
