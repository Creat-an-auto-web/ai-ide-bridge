from __future__ import annotations

import json
import re

from tdd_agent_framework.core import ProviderResponse

from .models import (
    GeneratedTestFile,
    TestCodeGenerationQualityChecks,
    TestCodeGenerationResult,
)


class TestCodeGenerationParser:
    @staticmethod
    def _load_payload(response: ProviderResponse) -> dict:
        if response.parsed_json is not None:
            if isinstance(response.parsed_json, dict):
                return response.parsed_json
            raise ValueError("provider output must be a JSON object")

        raw_text = response.raw_text.strip()
        if not raw_text:
            raise ValueError("provider output is empty")

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw_text)
            if match is None:
                raise
            payload = json.loads(match.group(0))

        if not isinstance(payload, dict):
            raise ValueError("provider output must be a JSON object")
        return payload

    def parse(self, response: ProviderResponse) -> TestCodeGenerationResult:
        payload = self._load_payload(response)

        implementation_plan = payload.get("implementation_plan")
        if not isinstance(implementation_plan, list) or not implementation_plan:
            raise ValueError("implementation_plan must be a non-empty list")

        raw_test_files = payload.get("test_files")
        if not isinstance(raw_test_files, list) or not raw_test_files:
            raise ValueError("test_files must be a non-empty list")
        test_files = [GeneratedTestFile.from_dict(item) for item in raw_test_files]

        changed_files = payload.get("changed_files")
        if not isinstance(changed_files, list) or not changed_files:
            raise ValueError("changed_files must be a non-empty list")

        rationale = payload.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("rationale must be a non-empty string")

        warnings = payload.get("warnings", [])
        if not isinstance(warnings, list):
            raise ValueError("warnings must be a list of strings")

        return TestCodeGenerationResult(
            implementation_plan=[str(item).strip() for item in implementation_plan if str(item).strip()],
            test_files=test_files,
            changed_files=[str(item).strip() for item in changed_files if str(item).strip()],
            rationale=rationale.strip(),
            warnings=[str(item).strip() for item in warnings if str(item).strip()],
            quality_checks=TestCodeGenerationQualityChecks(
                has_test_file_content=False,
                all_files_are_tests=False,
                covers_all_input_test_cases=False,
                changed_files_match_generated_files=False,
            ),
        )
