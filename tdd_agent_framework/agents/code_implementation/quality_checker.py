from __future__ import annotations

from dataclasses import replace
from pathlib import PurePosixPath

from .models import (
    CodeImplementationInput,
    CodeImplementationQualityChecks,
    CodeImplementationResult,
)


class CodeImplementationQualityChecker:
    def validate(
        self,
        data: CodeImplementationInput,
        result: CodeImplementationResult,
    ) -> CodeImplementationResult:
        paths = [item.path for item in result.files]
        if len(paths) != len(set(paths)):
            raise ValueError("generated implementation contains duplicate file paths")
        test_paths = {
            str(PurePosixPath(str(item.get("path", "")).replace("\\", "/")))
            for item in data.test_files
        }
        keeps_tests = not (set(paths) & test_paths)
        if not keeps_tests:
            raise ValueError("implementation output must not modify immutable test files")
        complete = all(item.content.strip() for item in result.files)
        relative = all(
            not PurePosixPath(path).is_absolute() and ".." not in PurePosixPath(path).parts
            for path in paths
        )
        changed_match = set(result.changed_files) == set(paths)
        if not changed_match:
            raise ValueError("changed_files must exactly match generated implementation files")
        if data.previous_files and not {item.path for item in data.previous_files}.issubset(paths):
            raise ValueError("repair output must include all previous implementation files")
        return replace(
            result,
            quality_checks=CodeImplementationQualityChecks(
                has_complete_file_content=complete,
                keeps_test_baseline_immutable=keeps_tests,
                changed_files_match_generated_files=changed_match,
                paths_are_repository_relative=relative,
            ),
        )
