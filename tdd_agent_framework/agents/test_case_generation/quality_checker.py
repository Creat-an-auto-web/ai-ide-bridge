from __future__ import annotations

from dataclasses import replace

from .models import (
    GeneratedTestCase,
    TestCaseGenerationInput,
    TestCaseGenerationResult,
    TestCaseQualityChecks,
)


ALLOWED_LEVELS = {"unit", "integration", "e2e"}
ALLOWED_CATEGORIES = {"positive", "negative", "boundary", "regression"}
ALLOWED_PRIORITIES = {"low", "medium", "high"}


class TestCaseGenerationValidationError(ValueError):
    """测试用例生成结果未通过校验。"""


class TestCaseGenerationQualityChecker:
    def validate(
        self,
        generation_input: TestCaseGenerationInput,
        result: TestCaseGenerationResult,
    ) -> TestCaseGenerationResult:
        warnings = list(result.warnings)
        self._validate_cases(generation_input, result.test_cases, warnings)

        has_boundary_cases = any(case.category == "boundary" for case in result.test_cases)
        has_negative_cases = any(case.category == "negative" for case in result.test_cases)
        has_inputs_and_expected = all(
            bool(case.test_input) and bool(case.expected_result.strip())
            for case in result.test_cases
        )
        covers_all_stories = result.coverage_summary.covered_story_count == result.coverage_summary.total_story_count
        case_count_within_limit = self._check_case_limit(generation_input, result.test_cases)

        if generation_input.execution_constraints.require_boundary_cases and not has_boundary_cases:
            raise TestCaseGenerationValidationError("missing boundary test cases")
        if generation_input.execution_constraints.require_negative_cases and not has_negative_cases:
            raise TestCaseGenerationValidationError("missing negative test cases")
        if not has_inputs_and_expected:
            raise TestCaseGenerationValidationError("each test case must include test_input and expected_result")
        if not covers_all_stories:
            raise TestCaseGenerationValidationError(
                f"some stories are not covered: {result.coverage_summary.uncovered_story_ids}",
            )
        if not case_count_within_limit:
            raise TestCaseGenerationValidationError(
                "some stories exceed execution_constraints.max_test_cases_per_story",
            )

        quality_checks = TestCaseQualityChecks(
            has_inputs_and_expected_results=has_inputs_and_expected,
            covers_all_stories=covers_all_stories,
            has_boundary_cases=has_boundary_cases,
            has_negative_cases=has_negative_cases,
            case_count_within_limit=case_count_within_limit,
        )
        return replace(result, warnings=warnings, quality_checks=quality_checks)

    def _validate_cases(
        self,
        generation_input: TestCaseGenerationInput,
        cases: list[GeneratedTestCase],
        warnings: list[str],
    ) -> None:
        story_ids = {story.id for story in generation_input.story_units}
        seen_ids: set[str] = set()
        for case in cases:
            if case.id in seen_ids:
                raise TestCaseGenerationValidationError(f"duplicate test case id: {case.id}")
            seen_ids.add(case.id)
            if case.story_id not in story_ids:
                raise TestCaseGenerationValidationError(
                    f"test case references unknown story_id: {case.story_id}",
                )
            if case.level not in ALLOWED_LEVELS:
                raise TestCaseGenerationValidationError(
                    f"test case level must be one of {sorted(ALLOWED_LEVELS)}",
                )
            if case.category not in ALLOWED_CATEGORIES:
                raise TestCaseGenerationValidationError(
                    f"test case category must be one of {sorted(ALLOWED_CATEGORIES)}",
                )
            if case.priority not in ALLOWED_PRIORITIES:
                raise TestCaseGenerationValidationError(
                    f"test case priority must be one of {sorted(ALLOWED_PRIORITIES)}",
                )
            if len(case.steps) < 2:
                warnings.append(f"test case {case.id} has too few steps; recommended >= 2")

    def _check_case_limit(
        self,
        generation_input: TestCaseGenerationInput,
        cases: list[GeneratedTestCase],
    ) -> bool:
        counter: dict[str, int] = {story.id: 0 for story in generation_input.story_units}
        for case in cases:
            if case.story_id in counter:
                counter[case.story_id] += 1
        return all(
            count <= generation_input.execution_constraints.max_test_cases_per_story
            for count in counter.values()
        )
