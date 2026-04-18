from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path

from tdd_agent_framework.agents.requirement_analysis import (
    ExecutionConstraints,
    RequirementAnalysisAgent,
    RequirementAnalysisInput,
    RequirementAnalysisService,
    WorkspaceSummary,
)
from tdd_agent_framework.core import ModelTarget, ProviderResponse


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class StaticProvider:
    def __init__(self, payload):
        self.payload = payload

    async def generate(self, request):
        return ProviderResponse(raw_text=json.dumps(self.payload), parsed_json=self.payload)


def load_input_fixture(name: str) -> RequirementAnalysisInput:
    data = json.loads((FIXTURES_DIR / f"{name}_input.json").read_text(encoding="utf-8"))
    return RequirementAnalysisInput(
        task_id=data["task_id"],
        mode=data["mode"],
        user_prompt=data["user_prompt"],
        repo_root=data["repo_root"],
        workspace_summary=WorkspaceSummary.from_dict(data.get("workspace_summary")),
        active_file=data.get("active_file"),
        selection=data.get("selection"),
        open_files=data.get("open_files", []),
        diagnostics=data.get("diagnostics", []),
        recent_test_failures=data.get("recent_test_failures", []),
        git_diff_summary=data.get("git_diff_summary"),
        execution_constraints=ExecutionConstraints.from_dict(data.get("execution_constraints")),
    )


def load_expected_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}_expected.json").read_text(encoding="utf-8"))


class RequirementAnalysisGoldenTest(unittest.TestCase):
    def test_all_fixture_pairs(self) -> None:
        input_files = sorted(FIXTURES_DIR.glob("*_input.json"))
        fixture_names = [file_path.name.removesuffix("_input.json") for file_path in input_files]
        self.assertGreaterEqual(len(fixture_names), 6)
        for fixture_name in fixture_names:
            with self.subTest(fixture=fixture_name):
                self._assert_fixture_matches(fixture_name)

    def _assert_fixture_matches(self, name: str) -> None:
        analysis_input = load_input_fixture(name)
        expected = load_expected_fixture(name)
        service = RequirementAnalysisService(
            RequirementAnalysisAgent(
                provider=StaticProvider(expected),
                model_target=ModelTarget(provider="openai", model="gpt-5.4"),
            ),
        )

        result = asyncio.run(service.analyze(analysis_input))

        self.assertEqual(result.requirement_spec.problem_statement, expected["requirement_spec"]["problem_statement"])
        self.assertEqual(result.analysis_summary.story_unit_count, len(expected["story_units"]))
        self.assertEqual(result.story_units[0].id, expected["story_units"][0]["id"])
        self.assertTrue(result.quality_checks.has_testable_ac)
        self.assertTrue(result.quality_checks.dependency_graph_valid)


if __name__ == "__main__":
    unittest.main()
