from __future__ import annotations

import json
import re

from tdd_agent_framework.agents.test_code_generation import GeneratedTestFile
from tdd_agent_framework.core import ProviderResponse

from .models import TestCodeRepairQualityChecks, TestCodeRepairResult


class TestCodeRepairParser:
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

    def parse(self, response: ProviderResponse) -> TestCodeRepairResult:
        payload = self._load_payload(response)
        repair_plan = payload.get("repair_plan")
        if not isinstance(repair_plan, list) or not repair_plan:
            raise ValueError("repair_plan must be a non-empty list")

        raw_test_files = payload.get("test_files")
        if not isinstance(raw_test_files, list) or not raw_test_files:
            raise ValueError("test_files must be a non-empty list")
        test_files = [GeneratedTestFile.from_dict(item) for item in raw_test_files]

        changed_files = payload.get("changed_files")
        if not isinstance(changed_files, list) or not changed_files:
            raise ValueError("changed_files must be a non-empty list")

        reasoning_summary = payload.get("reasoning_summary")
        if not isinstance(reasoning_summary, str) or not reasoning_summary.strip():
            raise ValueError("reasoning_summary must be a non-empty string")

        warnings = payload.get("warnings", [])
        if not isinstance(warnings, list):
            raise ValueError("warnings must be a list")

        return TestCodeRepairResult(
            repair_plan=[str(item).strip() for item in repair_plan if str(item).strip()],
            test_files=test_files,
            changed_files=[str(item).strip() for item in changed_files if str(item).strip()],
            reasoning_summary=reasoning_summary.strip(),
            warnings=[str(item).strip() for item in warnings if str(item).strip()],
            quality_checks=TestCodeRepairQualityChecks(
                has_test_file_content=False,
                covers_all_original_files=False,
                keeps_test_scope=False,
            ),
        )
