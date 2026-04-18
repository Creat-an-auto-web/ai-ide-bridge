from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from tdd_agent_framework.agents.requirement_analysis import (
    ExecutionConstraints,
    RequirementAnalysisAgent,
    RequirementAnalysisInput,
    WorkspaceSummary,
)
from tdd_agent_framework.core import ModelTarget, ProviderResponse
from tdd_agent_framework.orchestrators import RequirementAnalysisOrchestrator


class StaticProvider:
    def __init__(self, payload):
        self.payload = payload

    async def generate(self, request):
        return ProviderResponse(raw_text="{}", parsed_json=self.payload)


class RequirementAnalysisOrchestratorTest(unittest.TestCase):
    def test_orchestrator_enriches_workspace_summary_from_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_demo.py").write_text("def test_demo():\n    assert True\n", encoding="utf-8")
            (root / "app").mkdir()
            (root / "app" / "service.py").write_text("print('ok')\n", encoding="utf-8")

            payload = {
                "requirement_spec": {
                    "task_id": "task_001",
                    "version": 1,
                    "problem_statement": "需要修复某个问题并拆解需求。",
                    "product_goal": "产出结构化需求结果。",
                    "scope": ["scope_a"],
                    "out_of_scope": [],
                    "constraints": [],
                    "assumptions": [],
                    "interfaces_or_contracts": [],
                    "acceptance_criteria": [
                        "产出 requirement spec",
                        "产出 story units",
                        "story units 可被测试消费"
                    ],
                    "decomposition_strategy": "按职责拆分",
                },
                "story_units": [
                    {
                        "id": "story_a",
                        "title": "Story A",
                        "actor": "用户",
                        "goal": "目标足够具体以便测试",
                        "business_value": "价值",
                        "scope": ["scope_a"],
                        "out_of_scope": [],
                        "acceptance_criteria": [
                            "行为 A 会被执行",
                            "结果 A 可被验证",
                            "失败 A 可被观测"
                        ],
                        "dependencies": [],
                        "priority": "high",
                        "risk": "medium",
                        "test_focus": ["A", "B", "C"],
                        "implementation_hints": [],
                    }
                ],
            }
            orchestrator = RequirementAnalysisOrchestrator()
            settings = type("SettingsProxy", (), {})()
            # Reuse the real factory path through the orchestrator's service builder.
            from tdd_agent_framework.agents.requirement_analysis import RequirementAnalysisAgentSettings

            runtime_settings = RequirementAnalysisAgentSettings.from_dict(
                {
                    "enabled": True,
                    "provider_kind": "openai_compatible",
                    "provider_name": "openai",
                    "model": "gpt-test",
                    "api_base": "https://api.openai.com/v1",
                    "api_key": "secret-key",
                }
            )

            # Replace the built agent with a static provider by monkeypatching the factory target.
            agent = RequirementAnalysisAgent(
                provider=StaticProvider(payload),
                model_target=ModelTarget(provider="openai", model="gpt-test"),
            )

            async def fake_run(settings, analysis_input):
                enriched = orchestrator._build_workspace_summary(analysis_input)
                result = await agent.run(
                    RequirementAnalysisInput(
                        task_id=analysis_input.task_id,
                        mode=analysis_input.mode,
                        user_prompt=analysis_input.user_prompt,
                        repo_root=analysis_input.repo_root,
                        workspace_summary=enriched,
                        active_file=analysis_input.active_file,
                        selection=analysis_input.selection,
                        open_files=analysis_input.open_files,
                        diagnostics=analysis_input.diagnostics,
                        recent_test_failures=analysis_input.recent_test_failures,
                        git_diff_summary=analysis_input.git_diff_summary,
                        execution_constraints=analysis_input.execution_constraints,
                    ),
                    context=type("Ctx", (), {"task_id": analysis_input.task_id, "trace_id": None, "metadata": {}})(),
                )
                return result, enriched

            analysis_input = RequirementAnalysisInput(
                task_id="task_001",
                mode="repo_chat",
                user_prompt="修复并拆解需求",
                repo_root=str(root),
                workspace_summary=WorkspaceSummary(),
                execution_constraints=ExecutionConstraints(),
            )

            result, enriched = asyncio.run(fake_run(runtime_settings, analysis_input))

            self.assertIn("python", enriched.languages)
            self.assertIn("pytest", enriched.frameworks)
            self.assertIn("app", enriched.key_modules)
            self.assertEqual(result.analysis_summary.story_unit_count, 1)


if __name__ == "__main__":
    unittest.main()
