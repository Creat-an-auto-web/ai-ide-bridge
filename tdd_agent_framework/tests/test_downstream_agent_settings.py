from __future__ import annotations

import unittest

from tdd_agent_framework.agents.test_code_generation import TestCodeGenerationAgentSettings
from tdd_agent_framework.agents.test_code_repair import TestCodeRepairAgentSettings


class DownstreamAgentSettingsTest(unittest.TestCase):
    def _base(self) -> dict[str, object]:
        return {
            "enabled": True,
            "provider_kind": "openai_compatible",
            "provider_name": "auto-code",
            "wire_api": "responses",
            "model": "gpt-5.5",
            "api_base": "https://vip.auto-code.net",
            "api_key": "secret-key",
        }

    def test_test_code_generation_preserves_wire_api(self) -> None:
        settings = TestCodeGenerationAgentSettings.from_dict(self._base())

        self.assertEqual(settings.wire_api, "responses")
        self.assertEqual(settings.to_provider_config().wire_api, "responses")

    def test_test_code_repair_preserves_wire_api(self) -> None:
        settings = TestCodeRepairAgentSettings.from_dict(self._base())

        self.assertEqual(settings.wire_api, "responses")
        self.assertEqual(settings.to_provider_config().wire_api, "responses")


if __name__ == "__main__":
    unittest.main()
