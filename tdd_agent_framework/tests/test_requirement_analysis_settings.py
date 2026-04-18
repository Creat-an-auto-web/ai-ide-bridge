from __future__ import annotations

import unittest

from tdd_agent_framework.agents.requirement_analysis import (
    RequirementAnalysisAgentSettings,
    RequirementAnalysisAgentSettingsView,
    build_requirement_analysis_service,
)


class RequirementAnalysisSettingsTest(unittest.TestCase):
    def test_settings_from_dict_builds_runtime_and_public_view(self) -> None:
        settings = RequirementAnalysisAgentSettings.from_dict(
            {
                "enabled": True,
                "provider_kind": "openai_compatible",
                "provider_name": "openrouter",
                "model": "qwen/qwen3-32b",
                "api_base": "https://openrouter.ai/api/v1",
                "api_key": "secret-key",
                "temperature": 0.1,
                "max_tokens": 3200,
                "timeout_seconds": 30,
            },
        )

        public_view = RequirementAnalysisAgentSettingsView.from_settings(settings)

        self.assertEqual(settings.to_provider_config().api_base, "https://openrouter.ai/api/v1")
        self.assertEqual(settings.to_model_target().model, "qwen/qwen3-32b")
        self.assertEqual(settings.to_generation_config().max_tokens, 3200)
        self.assertTrue(public_view.has_api_key)
        self.assertEqual(public_view.provider_name, "openrouter")

    def test_build_service_rejects_disabled_agent(self) -> None:
        settings = RequirementAnalysisAgentSettings.from_dict(
            {
                "enabled": False,
                "provider_kind": "openai_compatible",
                "provider_name": "openai",
                "model": "gpt-5.4",
                "api_base": "https://api.openai.com/v1",
                "api_key": "secret-key",
            },
        )

        with self.assertRaisesRegex(ValueError, "disabled"):
            build_requirement_analysis_service(settings)

    def test_settings_validation_rejects_missing_api_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "api_key"):
            RequirementAnalysisAgentSettings.from_dict(
                {
                    "enabled": True,
                    "provider_kind": "openai_compatible",
                    "provider_name": "openai",
                    "model": "gpt-5.4",
                    "api_base": "https://api.openai.com/v1"
                },
            )


if __name__ == "__main__":
    unittest.main()
