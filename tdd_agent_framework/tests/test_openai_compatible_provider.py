from __future__ import annotations

import json
import unittest

from tdd_agent_framework.core import (
    GenerationConfig,
    ModelTarget,
    ProviderMessage,
    ProviderRequest,
)
from tdd_agent_framework.providers import OpenAICompatibleProvider, ProviderConfig


class OpenAICompatibleProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = OpenAICompatibleProvider(
            ProviderConfig(
                provider_name="openrouter",
                api_base="https://openrouter.ai/api/v1",
                api_key="test-key",
            ),
        )

    def test_build_payload_uses_request_model_and_messages(self) -> None:
        provider_request = ProviderRequest(
            agent_name="requirement_analysis",
            task_id="task_001",
            model_target=ModelTarget(provider="openrouter", model="qwen/qwen3"),
            system_prompt="system prompt",
            messages=(ProviderMessage(role="user", content="user prompt"),),
            generation_config=GenerationConfig(temperature=0.1, max_tokens=1200),
        )

        payload = self.provider._build_payload(provider_request)

        self.assertEqual(payload["model"], "qwen/qwen3")
        self.assertEqual(payload["temperature"], 0.1)
        self.assertEqual(payload["max_tokens"], 1200)
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["role"], "user")

    def test_extract_content_supports_string_message(self) -> None:
        raw_json = {
            "choices": [
                {
                    "message": {
                        "content": "{\"ok\": true}"
                    }
                }
            ]
        }

        content = self.provider._extract_content(raw_json)

        self.assertEqual(json.loads(content), {"ok": True})


if __name__ == "__main__":
    unittest.main()
