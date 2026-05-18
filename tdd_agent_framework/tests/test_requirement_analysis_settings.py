from __future__ import annotations

import unittest

from tdd_agent_framework.agents.requirement_analysis import (
    ExecutionConstraints,
    RequirementAnalysisAgentSettings,
    RequirementAnalysisAgentSettingsView,
    RequirementAnalysisInput,
    WorkspaceSummary,
    build_requirement_analysis_service,
)
from tdd_agent_framework.agents.requirement_analysis.prompt_builder import RequirementAnalysisPromptBuilder


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
                "max_request_seconds": 600,
            },
        )

        public_view = RequirementAnalysisAgentSettingsView.from_settings(settings)

        self.assertEqual(settings.to_provider_config().api_base, "https://openrouter.ai/api/v1")
        self.assertEqual(settings.to_provider_config().max_request_seconds, 600)
        self.assertEqual(settings.to_model_target().model, "qwen/qwen3-32b")
        self.assertEqual(settings.to_generation_config().max_tokens, 3200)
        self.assertEqual(settings.first_round_max_capability_groups, 4)
        self.assertEqual(settings.first_round_max_story_units, 12)
        self.assertEqual(settings.second_round_max_capability_groups, 6)
        self.assertEqual(settings.second_round_max_story_units, 24)
        self.assertIsNone(settings.later_round_max_capability_groups)
        self.assertIsNone(settings.later_round_max_story_units)
        self.assertTrue(public_view.has_api_key)
        self.assertEqual(public_view.provider_name, "openrouter")
        self.assertEqual(public_view.max_request_seconds, 600)

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

    def test_prompt_builder_truncates_large_context_lists(self) -> None:
        builder = RequirementAnalysisPromptBuilder()
        analysis_input = RequirementAnalysisInput(
            task_id="task_001",
            mode="repo_chat",
            user_prompt="分析复杂需求",
            repo_root="/workspace/project",
            workspace_summary=WorkspaceSummary(
                languages=["python"],
                frameworks=["pytest"],
                key_modules=["app", "tests"],
            ),
            open_files=[f"file_{idx}.py" for idx in range(12)],
            diagnostics=[f"diag_{idx}" for idx in range(12)],
            recent_test_failures=[f"failure_{idx}" for idx in range(12)],
            revision_focus=[f"focus_{idx}" for idx in range(12)],
            execution_constraints=ExecutionConstraints(),
        )

        prompt = builder.build_user_prompt(analysis_input)

        self.assertIn("file_7.py", prompt)
        self.assertNotIn("file_8.py", prompt)
        self.assertIn("diag_7", prompt)
        self.assertNotIn("diag_8", prompt)
        self.assertIn("failure_7", prompt)
        self.assertNotIn("failure_8", prompt)
        self.assertIn("focus_7", prompt)
        self.assertNotIn("focus_8", prompt)
        self.assertNotIn("\"repo_root\"", prompt)
        self.assertIn("输出最小结构示意", prompt)
        self.assertIn("输出完整 json 示例", prompt)

    def test_requirement_analysis_input_from_dict_truncates_large_context_fields(self) -> None:
        analysis_input = RequirementAnalysisInput.from_dict(
            {
                "task_id": "task_001",
                "mode": "repo_chat",
                "user_prompt": "分析复杂需求",
                "repo_root": "/workspace/project",
                "workspace_summary": {
                    "languages": ["python"],
                    "frameworks": ["pytest"],
                    "key_modules": ["app", "tests"],
                },
                "open_files": [f"file_{idx}.py" for idx in range(12)],
                "diagnostics": [f"diag_{idx}" for idx in range(12)],
                "recent_test_failures": [f"failure_{idx}" for idx in range(12)],
                "git_diff_summary": "x" * 5000,
                "revision_focus": [f"focus_{idx}" for idx in range(12)],
                "previous_verification_summary": "y" * 1500,
                "execution_constraints": {
                    "disallow_new_dependencies": True,
                    "preserve_public_api": True,
                    "max_capability_groups": 6,
                    "max_story_units": 24,
                },
            },
        )

        self.assertEqual(len(analysis_input.open_files), 8)
        self.assertEqual(len(analysis_input.diagnostics), 8)
        self.assertEqual(len(analysis_input.recent_test_failures), 8)
        self.assertEqual(len(analysis_input.revision_focus), 8)
        self.assertEqual(len(analysis_input.git_diff_summary), 4000)
        self.assertEqual(len(analysis_input.previous_verification_summary), 1200)

    def test_execution_constraints_allow_null_limits(self) -> None:
        constraints = ExecutionConstraints.from_dict(
            {
                "disallow_new_dependencies": True,
                "preserve_public_api": True,
                "max_capability_groups": None,
                "max_story_units": None,
            },
        )

        self.assertIsNone(constraints.max_capability_groups)
        self.assertIsNone(constraints.max_story_units)


if __name__ == "__main__":
    unittest.main()
