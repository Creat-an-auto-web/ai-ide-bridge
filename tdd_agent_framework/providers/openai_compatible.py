from __future__ import annotations

import asyncio
import json
import re
from typing import Any
import httpx

from tdd_agent_framework.core import (
    ModelTarget,
    ProviderMessage,
    ProgressCallback,
    ProviderRequest,
    ProviderResponse,
    RunProgressEvent,
    emit_progress,
)

from .config import ProviderConfig


class ProviderError(RuntimeError):
    """Provider request failed."""


class OpenAICompatibleProvider:
    request_retry_attempts = 3
    request_retry_backoff_seconds = 1.5
    retryable_status_codes = frozenset({408, 429, 500, 502, 503, 504, 524})

    def __init__(
        self,
        config: ProviderConfig,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.config = config
        self.progress_callback = progress_callback

    async def generate(self, provider_request: ProviderRequest) -> ProviderResponse:
        payload = self._build_payload(provider_request)
        api_base = provider_request.model_target.api_base or self.config.api_base
        url = api_base.rstrip("/") + self.config.chat_path
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
            **self.config.headers,
        }
        timeout = self._build_timeout(provider_request)

        await emit_progress(
            self.progress_callback,
            RunProgressEvent(
                type="status",
                stage="provider_request_started",
                message=f"已向 {self.config.provider_name} 发起模型请求",
                metadata={
                    "agent_name": provider_request.agent_name,
                    "provider_name": self.config.provider_name,
                    "model": provider_request.model_target.model,
                    "api_base": api_base,
                },
            ),
        )

        raw_json: dict[str, Any] | None = None
        content = ""
        last_connect_error: httpx.HTTPError | None = None

        for attempt in range(1, self.request_retry_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        raw_json, content = await self._read_response(
                            response,
                            agent_name=provider_request.agent_name,
                        )
                last_connect_error = None
                break
            except httpx.HTTPStatusError as exc:
                response = exc.response
                if self._is_retryable_status(response.status_code) and attempt < self.request_retry_attempts:
                    await self._emit_retry_progress(
                        provider_request=provider_request,
                        attempt=attempt,
                        retry_reason=f"http_{response.status_code}",
                        message=(
                            f"模型服务暂时不可用（HTTP {response.status_code}），"
                            f"准备进行第 {attempt + 1} 次尝试"
                        ),
                    )
                    await asyncio.sleep(self.request_retry_backoff_seconds * attempt)
                    continue
                raise ProviderError(
                    self._format_status_error(
                        response,
                        url=url,
                        provider_request=provider_request,
                        attempt=attempt,
                    ),
                ) from exc
            except (httpx.ConnectTimeout, httpx.ConnectError) as exc:
                last_connect_error = exc
                if attempt >= self.request_retry_attempts:
                    raise ProviderError(
                        self._format_timeout_error(
                            exc,
                            url=url,
                            provider_request=provider_request,
                            attempt=attempt,
                            phase="connect",
                        ),
                    ) from exc
                await self._emit_retry_progress(
                    provider_request=provider_request,
                    attempt=attempt,
                    retry_reason=type(exc).__name__,
                    message=f"模型连接失败，准备进行第 {attempt + 1} 次尝试",
                )
                await asyncio.sleep(self.request_retry_backoff_seconds * attempt)
            except httpx.TimeoutException as exc:
                if attempt < self.request_retry_attempts:
                    await self._emit_retry_progress(
                        provider_request=provider_request,
                        attempt=attempt,
                        retry_reason=type(exc).__name__,
                        message=(
                            f"模型响应超时，准备进行第 {attempt + 1} 次尝试"
                        ),
                    )
                    await asyncio.sleep(self.request_retry_backoff_seconds * attempt)
                    continue
                raise ProviderError(
                    self._format_timeout_error(
                        exc,
                        url=url,
                        provider_request=provider_request,
                        attempt=attempt,
                        phase="response",
                    ),
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderError(
                    self._format_http_error(exc, url=url, provider_request=provider_request),
                ) from exc

        if raw_json is None and last_connect_error is not None:
            raise ProviderError(
                self._format_timeout_error(
                    last_connect_error,
                    url=url,
                    provider_request=provider_request,
                    attempt=self.request_retry_attempts,
                    phase="connect",
                ),
            )

        await emit_progress(
            self.progress_callback,
            RunProgressEvent(
                type="status",
                stage="provider_response_completed",
                message="模型响应接收完成，准备解析结果",
                raw_text_preview=self._preview_text(content),
                metadata={
                    "agent_name": provider_request.agent_name,
                    "provider_name": self.config.provider_name,
                },
            ),
        )

        return ProviderResponse(
            raw_text=content,
            parsed_json=self._try_parse_json(content),
            model_target=provider_request.model_target,
            metadata={"provider": self.config.provider_name, "raw_response": raw_json},
        )

    def _build_payload(self, provider_request: ProviderRequest) -> dict[str, Any]:
        messages = [self._to_message("system", provider_request.system_prompt)]
        messages.extend(self._to_message(item.role, item.content) for item in provider_request.messages)
        payload: dict[str, Any] = {
            "model": provider_request.model_target.model,
            "messages": messages,
            "temperature": provider_request.generation_config.temperature,
            "max_tokens": provider_request.generation_config.max_tokens,
            "stream": provider_request.generation_config.response_format != "json_object",
        }
        if provider_request.generation_config.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _build_timeout(self, provider_request: ProviderRequest) -> httpx.Timeout:
        # Structured json_object requests are non-streaming in this project, so a
        # bounded read timeout gives us earlier retries instead of waiting for an
        # upstream gateway timeout page.
        read_timeout: float | None = None
        if provider_request.generation_config.response_format == "json_object":
            read_timeout = max(self.config.timeout_seconds * 3, self.config.timeout_seconds + 120.0)
        return httpx.Timeout(
            connect=self.config.timeout_seconds,
            write=self.config.timeout_seconds,
            read=read_timeout,
            pool=self.config.timeout_seconds,
        )

    def _to_message(self, role: str, content: str) -> dict[str, str]:
        return {"role": role, "content": content}

    async def _emit_retry_progress(
        self,
        *,
        provider_request: ProviderRequest,
        attempt: int,
        retry_reason: str,
        message: str,
    ) -> None:
        await emit_progress(
            self.progress_callback,
            RunProgressEvent(
                type="status",
                stage="provider_request_retrying",
                message=message,
                metadata={
                    "agent_name": provider_request.agent_name,
                    "provider_name": self.config.provider_name,
                    "model": provider_request.model_target.model,
                    "attempt": attempt,
                    "next_attempt": attempt + 1,
                    "max_attempts": self.request_retry_attempts,
                    "retry_reason": retry_reason,
                },
            ),
        )

    def _is_retryable_status(self, status_code: int) -> bool:
        return status_code in self.retryable_status_codes

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

    async def _read_response(
        self,
        response: httpx.Response,
        agent_name: str,
    ) -> tuple[dict[str, Any], str]:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            await response.aread()
            raise

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            body = await response.aread()
            raw_json = json.loads(body.decode("utf-8"))
            return raw_json, self._extract_content(raw_json)

        collected_text: list[str] = []
        last_message_json: dict[str, Any] | None = None

        async for line in response.aiter_lines():
            if not line:
                continue
            if line.startswith(":"):
                continue
            if not line.startswith("data:"):
                continue

            raw_line = line[5:].strip()
            if not raw_line:
                continue
            if raw_line == "[DONE]":
                break

            try:
                chunk_json = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            if not isinstance(chunk_json, dict):
                continue

            last_message_json = chunk_json
            delta_text = self._extract_delta_text(chunk_json)
            if delta_text:
                collected_text.append(delta_text)
                current_text = "".join(collected_text)
                await emit_progress(
                    self.progress_callback,
                    RunProgressEvent(
                        type="model_output",
                        stage="provider_streaming",
                        message="模型正在生成结构化结果",
                        raw_text_delta=delta_text,
                        raw_text_preview=self._preview_text(current_text),
                        metadata={
                            "agent_name": agent_name,
                            "provider_name": self.config.provider_name,
                            "delta_length": len(delta_text),
                            "accumulated_length": len(current_text),
                        },
                    ),
                )

        content = "".join(collected_text)
        if not content and last_message_json is not None:
            content = self._extract_content(last_message_json)
            return last_message_json, content

        if last_message_json is None:
            raise ProviderError("provider stream ended without data")

        return last_message_json, content

    def _extract_delta_text(self, raw_json: dict[str, Any]) -> str:
        choices = raw_json.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""

        delta = choices[0].get("delta")
        if not isinstance(delta, dict):
            message = choices[0].get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
            return ""

        content = delta.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
            return "".join(text_parts)
        return ""

    def _preview_text(self, text: str, limit: int = 2000) -> str:
        if len(text) <= limit:
            return text
        return text[-limit:]

    def _format_timeout_error(
        self,
        exc: httpx.HTTPError,
        *,
        url: str,
        provider_request: ProviderRequest,
        attempt: int = 1,
        phase: str = "response",
    ) -> str:
        exc_name = type(exc).__name__
        detail = str(exc).strip() or "no additional detail"
        return (
            "provider request failed: "
            f"{exc_name} while calling {provider_request.agent_name} model "
            f"{provider_request.model_target.model} at {url} "
            f"(phase={phase}, connect_timeout={self.config.timeout_seconds}s, "
            f"read_timeout={self._read_timeout_label(provider_request)}, "
            f"attempt={attempt}/{self.request_retry_attempts}, "
            f"detail={detail})"
        )

    def _format_status_error(
        self,
        response: httpx.Response,
        *,
        url: str,
        provider_request: ProviderRequest,
        attempt: int,
    ) -> str:
        return (
            "provider request failed: "
            f"HTTP {response.status_code} while calling {provider_request.agent_name} model "
            f"{provider_request.model_target.model} at {url} "
            f"(attempt={attempt}/{self.request_retry_attempts}, "
            f"detail={self._summarize_error_body(response.text)})"
        )

    def _format_http_error(
        self,
        exc: httpx.HTTPError,
        *,
        url: str,
        provider_request: ProviderRequest,
    ) -> str:
        exc_name = type(exc).__name__
        detail = str(exc).strip() or "no additional detail"
        return (
            "provider request failed: "
            f"{exc_name} while calling {provider_request.agent_name} model "
            f"{provider_request.model_target.model} at {url} "
            f"(detail={detail})"
        )

    def _read_timeout_label(self, provider_request: ProviderRequest) -> str:
        if provider_request.generation_config.response_format == "json_object":
            return f"{max(self.config.timeout_seconds * 3, self.config.timeout_seconds + 120.0)}s"
        return "streaming_unbounded"

    def _summarize_error_body(self, body: str, limit: int = 240) -> str:
        stripped = body.strip()
        if not stripped:
            return "empty response body"

        title_match = re.search(r"<title>(.*?)</title>", stripped, flags=re.IGNORECASE | re.DOTALL)
        if title_match is not None:
            title = re.sub(r"\s+", " ", title_match.group(1)).strip()
            if title:
                return f"html_title={title[:limit]}"

        normalized = re.sub(r"\s+", " ", stripped)
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 3] + "..."

    def _try_parse_json(self, text: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
