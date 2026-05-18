from __future__ import annotations

from dataclasses import replace

from .models import TestCodeRepairInput, TestCodeRepairQualityChecks, TestCodeRepairResult


class TestCodeRepairValidationError(ValueError):
    pass


class TestCodeRepairQualityChecker:
    def validate(
        self,
        repair_input: TestCodeRepairInput,
        result: TestCodeRepairResult,
    ) -> TestCodeRepairResult:
        original_paths = {test_file.path for test_file in repair_input.test_files}
        repaired_paths = {test_file.path for test_file in result.test_files}

        has_test_file_content = all(test_file.content.strip() for test_file in result.test_files)
        covers_all_original_files = original_paths.issubset(repaired_paths)
        keeps_test_scope = all(
            "test" in test_file.path.lower() or "spec" in test_file.path.lower()
            for test_file in result.test_files
        )

        if not has_test_file_content:
            raise TestCodeRepairValidationError("repaired test files must include non-empty content")
        if not covers_all_original_files:
            raise TestCodeRepairValidationError("repair output must cover all original test files")

        return replace(
            result,
            quality_checks=TestCodeRepairQualityChecks(
                has_test_file_content=has_test_file_content,
                covers_all_original_files=covers_all_original_files,
                keeps_test_scope=keeps_test_scope,
            ),
        )
