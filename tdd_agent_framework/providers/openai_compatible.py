from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from tdd_agent_framework.core import (
    ModelTarget,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
)

from .config import ProviderConfig


class ProviderError(RuntimeError):
    """Provider request failed."""


class OpenAICompatibleProvider:
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    async def generate(self, provider_request: ProviderRequest) -> ProviderResponse:
        http_request = self._build_http_request(provider_request)
        try:
            with request.urlopen(http_request, timeout=self.config.timeout_seconds) as response:
                response_bytes = response.read()
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(
                f"provider request failed with status {exc.code}: {body}",
            ) from exc
        except error.URLError as exc:
            raise ProviderError(f"provider request failed: {exc.reason}") from exc

        raw_json = json.loads(response_bytes.decode("utf-8"))
        content = self._extract_content(raw_json)
        return ProviderResponse(
            raw_text=content,
            parsed_json=self._try_parse_json(content),
            model_target=provider_request.model_target,
            metadata={"provider": self.config.provider_name, "raw_response": raw_json},
        )

    def _build_http_request(self, provider_request: ProviderRequest) -> request.Request:
        payload = self._build_payload(provider_request)
        api_base = provider_request.model_target.api_base or self.config.api_base
        url = api_base.rstrip("/") + self.config.chat_path
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
            **self.config.headers,
        }
        return request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

    def _build_payload(self, provider_request: ProviderRequest) -> dict[str, Any]:
        messages = [self._to_message("system", provider_request.system_prompt)]
        messages.extend(self._to_message(item.role, item.content) for item in provider_request.messages)
        payload: dict[str, Any] = {
            "model": provider_request.model_target.model,
            "messages": messages,
            "temperature": provider_request.generation_config.temperature,
            "max_tokens": provider_request.generation_config.max_tokens,
        }
        if provider_request.generation_config.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _to_message(self, role: str, content: str) -> dict[str, str]:
        return {"role": role, "content": content}

    def _extract_content(self, raw_json: dict[str, Any]) -> str:
        choices = raw_json.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("provider response does not contain choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ProviderError("provider response does not contain choices[0].message")
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
            if text_parts:
                return "\n".join(text_parts)
        raise ProviderError("provider response message content is not a supported format")

    def _try_parse_json(self, text: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
