from __future__ import annotations

from tdd_agent_framework.core import ProviderResponse, parse_json_object_from_text

from .models import (
    CodeImplementationQualityChecks,
    CodeImplementationResult,
    GeneratedCodeFile,
    _required_text,
    _string_list,
)


class CodeImplementationParser:
    def parse(self, response: ProviderResponse) -> CodeImplementationResult:
        payload = response.parsed_json or parse_json_object_from_text(response.raw_text)
        raw_files = payload.get("files")
        if not isinstance(raw_files, list) or not raw_files:
            raise ValueError("files must be a non-empty list")
        test_command = _string_list(payload.get("test_command"), "test_command")
        return CodeImplementationResult(
            implementation_plan=_string_list(
                payload.get("implementation_plan"),
                "implementation_plan",
                required=True,
            ),
            files=[GeneratedCodeFile.from_dict(item) for item in raw_files],
            changed_files=_string_list(
                payload.get("changed_files"),
                "changed_files",
                required=True,
            ),
            rationale=_required_text(payload.get("rationale"), "rationale"),
            test_command=test_command,
            warnings=_string_list(payload.get("warnings"), "warnings"),
            quality_checks=CodeImplementationQualityChecks(False, False, False, False),
        )

