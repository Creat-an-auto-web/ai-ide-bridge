from __future__ import annotations

import json

from tdd_agent_framework.core import ProviderResponse

from .models import (
    GeneratedTestCase,
    TestCaseGenerationResult,
    TestCaseQualityChecks,
    build_coverage_summary,
)


class TestCaseGenerationParser:
    def parse(
        self,
        response: ProviderResponse,
        *,
        expected_story_units,
    ) -> TestCaseGenerationResult:
        payload = response.parsed_json
        if payload is None:
            payload = json.loads(response.raw_text)
        if not isinstance(payload, dict):
            raise ValueError("provider output must be a JSON object")

        test_plan = payload.get("test_plan")
        if not isinstance(test_plan, str) or not test_plan.strip():
            raise ValueError("test_plan must be a non-empty string")

        raw_test_cases = payload.get("test_cases")
        if not isinstance(raw_test_cases, list) or not raw_test_cases:
            raise ValueError("test_cases must be a non-empty list")
        test_cases = [GeneratedTestCase.from_dict(item) for item in raw_test_cases]

        warnings = payload.get("warnings", [])
        if not isinstance(warnings, list):
            raise ValueError("warnings must be a list of strings")

        coverage_summary = build_coverage_summary(expected_story_units, test_cases)
        return TestCaseGenerationResult(
            test_plan=test_plan.strip(),
            test_cases=test_cases,
            coverage_summary=coverage_summary,
            warnings=[str(item) for item in warnings],
            quality_checks=TestCaseQualityChecks(
                has_inputs_and_expected_results=False,
                covers_all_stories=False,
                has_boundary_cases=False,
                has_negative_cases=False,
                case_count_within_limit=False,
            ),
        )
