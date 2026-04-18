from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderConfig:
    provider_name: str
    api_base: str
    api_key: str
    timeout_seconds: float = 60.0
    headers: dict[str, str] = field(default_factory=dict)
    chat_path: str = "/chat/completions"
