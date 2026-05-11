from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.models.requirement_analysis import RequirementAnalysisSettingsPayload
from app.models.test_case_generation import TestCaseGenerationSettingsPayload


class GlmEnvDefaultsTest(unittest.TestCase):
    def test_test_case_generation_settings_use_glm_env_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GLM_API_KEY": "dummy-key",
                "GLM_MODEL": "GLM-4.7-Flash",
                "GLM_API_BASE": '" `https://api.z.ai/api/paas/v4/` "）',
            },
            clear=False,
        ):
            payload = TestCaseGenerationSettingsPayload()

        self.assertEqual(payload.provider_name, "zhipu")
        self.assertEqual(payload.model, "GLM-4.7-Flash")
        self.assertEqual(payload.api_key, "dummy-key")
        self.assertEqual(payload.api_base, "https://api.z.ai/api/paas/v4")

    def test_requirement_analysis_settings_use_glm_env_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GLM_API_KEY": "dummy-key",
                "GLM_MODEL": "GLM-4.7-Flash",
                "GLM_API_BASE": "https://api.z.ai/api/paas/v4/",
            },
            clear=False,
        ):
            payload = RequirementAnalysisSettingsPayload()

        self.assertEqual(payload.provider_name, "zhipu")
        self.assertEqual(payload.model, "GLM-4.7-Flash")
        self.assertEqual(payload.api_key, "dummy-key")
        self.assertEqual(payload.api_base, "https://api.z.ai/api/paas/v4")


if __name__ == "__main__":
    unittest.main()
