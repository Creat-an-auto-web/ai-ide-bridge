from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from tdd_agent_framework.agents.requirement_analysis import (
    RequirementAnalysisAgentSettings,
    RequirementAnalysisInput,
)
from tdd_agent_framework.orchestrators import RequirementAnalysisOrchestrator


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_input(path: Path) -> RequirementAnalysisInput:
    from tdd_agent_framework.agents.requirement_analysis import (
        ExecutionConstraints,
        WorkspaceSummary,
    )

    data = _load_json(path)
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


def _normalize_title(value: str) -> str:
    return "".join(value.lower().split())


def _score_result(expected: dict, actual: dict) -> dict[str, float]:
    expected_titles = {
        _normalize_title(item["title"])
        for item in expected["story_units"]
    }
    actual_titles = {
        _normalize_title(item["title"])
        for item in actual["story_units"]
    }
    matched_titles = expected_titles.intersection(actual_titles)
    title_recall = len(matched_titles) / len(expected_titles) if expected_titles else 1.0

    quality = actual.get("quality_checks", {})
    return {
        "title_recall": title_recall,
        "has_clear_scope": float(bool(quality.get("has_clear_scope"))),
        "has_testable_ac": float(bool(quality.get("has_testable_ac"))),
        "dependency_graph_valid": float(bool(quality.get("dependency_graph_valid"))),
        "story_count_within_limit": float(bool(quality.get("story_count_within_limit"))),
    }


async def _run_eval(
    fixtures_dir: Path,
    settings: RequirementAnalysisAgentSettings,
) -> dict:
    orchestrator = RequirementAnalysisOrchestrator()
    fixture_names = sorted(
        path.name.removesuffix("_input.json")
        for path in fixtures_dir.glob("*_input.json")
    )
    results = []
    for fixture_name in fixture_names:
        analysis_input = _load_input(fixtures_dir / f"{fixture_name}_input.json")
        expected = _load_json(fixtures_dir / f"{fixture_name}_expected.json")
        actual_result = await orchestrator.run(settings, analysis_input)
        actual = {
            "requirement_spec": {
                "problem_statement": actual_result.requirement_spec.problem_statement,
            },
            "story_units": [
                {"title": story.title}
                for story in actual_result.story_units
            ],
            "quality_checks": {
                "has_clear_scope": actual_result.quality_checks.has_clear_scope,
                "has_testable_ac": actual_result.quality_checks.has_testable_ac,
                "dependency_graph_valid": actual_result.quality_checks.dependency_graph_valid,
                "story_count_within_limit": actual_result.quality_checks.story_count_within_limit,
            },
        }
        metrics = _score_result(expected, actual)
        results.append({"fixture": fixture_name, "metrics": metrics})

    aggregate: dict[str, float] = {}
    metric_keys = list(results[0]["metrics"].keys()) if results else []
    for key in metric_keys:
        aggregate[key] = sum(item["metrics"][key] for item in results) / len(results)

    aggregate["fixture_count"] = float(len(results))
    aggregate["pass_rate"] = (
        sum(
            1
            for item in results
            if item["metrics"]["title_recall"] >= 0.5
            and item["metrics"]["has_testable_ac"] == 1.0
            and item["metrics"]["dependency_graph_valid"] == 1.0
        )
        / len(results)
        if results
        else 0.0
    )

    return {
        "results": results,
        "aggregate": aggregate,
        "criteria": {
            "pass_rate": "title_recall >= 0.5 且 quality_checks 全部通过",
            "recommended_threshold": {
                "pass_rate": 0.8,
                "title_recall": 0.7,
                "has_testable_ac": 1.0,
                "dependency_graph_valid": 1.0,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RequirementAnalysis with real provider")
    parser.add_argument("--settings", required=True, help="JSON file for RequirementAnalysisAgentSettings")
    parser.add_argument(
        "--fixtures-dir",
        default=str(Path(__file__).resolve().parents[1] / "tests" / "fixtures"),
    )
    args = parser.parse_args()

    settings = RequirementAnalysisAgentSettings.from_dict(
        _load_json(Path(args.settings)),
    )
    report = asyncio.run(_run_eval(Path(args.fixtures_dir), settings))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
