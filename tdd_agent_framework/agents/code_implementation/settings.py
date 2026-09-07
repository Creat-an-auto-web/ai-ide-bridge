from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tdd_agent_framework.core import GenerationConfig, ModelTarget
from tdd_agent_framework.providers import ProviderConfig


@dataclass(frozen=True)
class CodeImplementationAgentSettings:
    provider_name: str
    model: str
    api_base: str
    api_key: str
    wire_api: str = "chat_completions"
    temperature: float = 0.1
    max_tokens: int = 12000
    timeout_seconds: float = 60.0
    max_request_seconds: float = 900.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CodeImplementationAgentSettings":
        if not isinstance(data, dict):
            raise ValueError("code implementation settings must be an object")
        required = {}
        for key in ("provider_name", "model", "api_base", "api_key"):
            value = data.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{key} must be a non-empty string")
            required[key] = value.strip()
        wire_api = str(data.get("wire_api", "chat_completions")).strip()
        if wire_api not in {"chat_completions", "responses"}:
            raise ValueError("wire_api must be chat_completions or responses")
        max_tokens = int(data.get("max_tokens", 12000))
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        return cls(
            **required,
            wire_api=wire_api,
            temperature=float(data.get("temperature", 0.1)),
            max_tokens=max_tokens,
            timeout_seconds=float(data.get("timeout_seconds", 60.0)),
            max_request_seconds=float(data.get("max_request_seconds", 900.0)),
        )

    def to_provider_config(self) -> ProviderConfig:
        return ProviderConfig(
            provider_name=self.provider_name,
            api_base=self.api_base,
            api_key=self.api_key,
            wire_api=self.wire_api,
            timeout_seconds=self.timeout_seconds,
            max_request_seconds=self.max_request_seconds,
        )

    def to_model_target(self) -> ModelTarget:
        return ModelTarget(self.provider_name, self.model, self.api_base)

    def to_generation_config(self) -> GenerationConfig:
        return GenerationConfig(
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format="json_object",
        )

