from __future__ import annotations

from dataclasses import replace

from .models import TestCodeGenerationInput, TestCodeGenerationQualityChecks, TestCodeGenerationResult


class TestCodeGenerationValidationError(ValueError):
    pass


class TestCodeGenerationQualityChecker:
    def validate(
        self,
        generation_input: TestCodeGenerationInput,
        result: TestCodeGenerationResult,
    ) -> TestCodeGenerationResult:
        generated_paths = {test_file.path for test_file in result.test_files}
        changed_paths = set(result.changed_files)
        input_test_case_ids = {test_case.id for test_case in generation_input.test_cases}
        referenced_test_case_ids = {
            related_id
            for test_file in result.test_files
            for related_id in test_file.related_test_case_ids
        }

        has_test_file_content = all(test_file.content.strip() for test_file in result.test_files)
        all_files_are_tests = all(
            "test" in test_file.path.lower() or "spec" in test_file.path.lower()
            for test_file in result.test_files
        )
        covers_all_input_test_cases = input_test_case_ids.issubset(referenced_test_case_ids)
        changed_files_match_generated_files = generated_paths.issubset(changed_paths)

        if not has_test_file_content:
            raise TestCodeGenerationValidationError("generated test files must include non-empty content")
        if not covers_all_input_test_cases:
            raise TestCodeGenerationValidationError("generated test files must cover all input test cases")
        if not changed_files_match_generated_files:
            raise TestCodeGenerationValidationError("changed_files must include every generated test file path")

        return replace(
            result,
            quality_checks=TestCodeGenerationQualityChecks(
                has_test_file_content=has_test_file_content,
                all_files_are_tests=all_files_are_tests,
                covers_all_input_test_cases=covers_all_input_test_cases,
                changed_files_match_generated_files=changed_files_match_generated_files,
            ),
        )
