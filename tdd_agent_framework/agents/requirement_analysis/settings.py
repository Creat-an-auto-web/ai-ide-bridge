from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tdd_agent_framework.core import GenerationConfig, ModelTarget
from tdd_agent_framework.providers import ProviderConfig


ALLOWED_PROVIDER_KINDS = {"openai_compatible"}


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class RequirementAnalysisAgentSettings:
    enabled: bool
    provider_kind: str
    provider_name: str
    model: str
    api_base: str
    api_key: str
    temperature: float = 0.2
    max_tokens: int = 4000
    timeout_seconds: float = 60.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RequirementAnalysisAgentSettings":
        if not isinstance(data, dict):
            raise ValueError("requirement analysis settings must be an object")

        provider_kind = _require_non_empty_string(
            data.get("provider_kind", "openai_compatible"),
            "provider_kind",
        )
        if provider_kind not in ALLOWED_PROVIDER_KINDS:
            raise ValueError(
                f"provider_kind must be one of {sorted(ALLOWED_PROVIDER_KINDS)}",
            )

        temperature = data.get("temperature", 0.2)
        if not isinstance(temperature, (int, float)):
            raise ValueError("temperature must be a number")

        max_tokens = data.get("max_tokens", 4000)
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")

        timeout_seconds = data.get("timeout_seconds", 60.0)
        if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive number")

        return cls(
            enabled=bool(data.get("enabled", True)),
            provider_kind=provider_kind,
            provider_name=_require_non_empty_string(data.get("provider_name"), "provider_name"),
            model=_require_non_empty_string(data.get("model"), "model"),
            api_base=_require_non_empty_string(data.get("api_base"), "api_base"),
            api_key=_require_non_empty_string(data.get("api_key"), "api_key"),
            temperature=float(temperature),
            max_tokens=max_tokens,
            timeout_seconds=float(timeout_seconds),
        )

    def to_provider_config(self) -> ProviderConfig:
        return ProviderConfig(
            provider_name=self.provider_name,
            api_base=self.api_base,
            api_key=self.api_key,
            timeout_seconds=self.timeout_seconds,
        )

    def to_model_target(self) -> ModelTarget:
        return ModelTarget(
            provider=self.provider_name,
            model=self.model,
            api_base=self.api_base,
        )

    def to_generation_config(self) -> GenerationConfig:
        return GenerationConfig(
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format="json_object",
        )


@dataclass(frozen=True)
class RequirementAnalysisAgentSettingsView:
    enabled: bool
    provider_kind: str
    provider_name: str
    model: str
    api_base: str
    has_api_key: bool
    temperature: float
    max_tokens: int
    timeout_seconds: float

    @classmethod
    def from_settings(
        cls,
        settings: RequirementAnalysisAgentSettings,
    ) -> "RequirementAnalysisAgentSettingsView":
        return cls(
            enabled=settings.enabled,
            provider_kind=settings.provider_kind,
            provider_name=settings.provider_name,
            model=settings.model,
            api_base=settings.api_base,
            has_api_key=bool(settings.api_key),
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout_seconds=settings.timeout_seconds,
        )
