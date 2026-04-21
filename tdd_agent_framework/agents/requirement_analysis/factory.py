from __future__ import annotations

from tdd_agent_framework.core import ProgressCallback
from tdd_agent_framework.providers import OpenAICompatibleProvider

from .agent import RequirementAnalysisAgent
from .service import RequirementAnalysisService
from .settings import RequirementAnalysisAgentSettings


def build_requirement_analysis_service(
    settings: RequirementAnalysisAgentSettings,
    progress_callback: ProgressCallback | None = None,
) -> RequirementAnalysisService:
    if not settings.enabled:
        raise ValueError("requirement analysis agent is disabled")

    if settings.provider_kind != "openai_compatible":
        raise ValueError(f"unsupported provider_kind: {settings.provider_kind}")

    provider = OpenAICompatibleProvider(
        settings.to_provider_config(),
        progress_callback=progress_callback,
    )
    agent = RequirementAnalysisAgent(
        provider=provider,
        model_target=settings.to_model_target(),
        generation_config=settings.to_generation_config(),
    )
    return RequirementAnalysisService(agent)
