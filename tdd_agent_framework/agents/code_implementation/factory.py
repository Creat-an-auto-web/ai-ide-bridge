from __future__ import annotations

from tdd_agent_framework.core import ProgressCallback
from tdd_agent_framework.providers import OpenAICompatibleProvider

from .agent import CodeImplementationAgent
from .service import CodeImplementationService
from .settings import CodeImplementationAgentSettings


def build_code_implementation_service(
    settings: CodeImplementationAgentSettings,
    progress_callback: ProgressCallback | None = None,
) -> CodeImplementationService:
    provider = OpenAICompatibleProvider(
        settings.to_provider_config(),
        progress_callback=progress_callback,
    )
    return CodeImplementationService(
        CodeImplementationAgent(
            provider,
            settings.to_model_target(),
            settings.to_generation_config(),
        )
    )

