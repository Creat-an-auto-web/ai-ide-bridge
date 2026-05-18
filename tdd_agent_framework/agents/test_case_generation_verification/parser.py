from __future__ import annotations

import json
import re

from tdd_agent_framework.core import ProviderResponse

from .models import TestCaseGenerationVerificationResult


class TestCaseGenerationVerificationParser:
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

    def parse(self, response: ProviderResponse) -> TestCaseGenerationVerificationResult:
        payload = self._load_payload(response)

        status = payload.get("status")
        if not isinstance(status, str) or status not in {"complete", "incomplete", "blocked"}:
            raise ValueError("status must be one of complete, incomplete, blocked")

        summary = payload.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("summary must be a non-empty string")

        raw_missing_items = payload.get("missing_items", [])
        if not isinstance(raw_missing_items, list):
            raise ValueError("missing_items must be a list of strings")

        raw_notes = payload.get("notes", [])
        if not isinstance(raw_notes, list):
            raise ValueError("notes must be a list of strings")

        return TestCaseGenerationVerificationResult(
            status=status,
            is_complete=status == "complete",
            summary=summary.strip(),
            missing_items=[str(item).strip() for item in raw_missing_items if str(item).strip()],
            notes=[str(item).strip() for item in raw_notes if str(item).strip()],
        )
