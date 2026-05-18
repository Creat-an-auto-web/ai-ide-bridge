from __future__ import annotations

from tdd_agent_framework.core import ProviderResponse, parse_json_object_from_text

from .models import RequirementCompositionVerificationResult


class RequirementCompositionVerificationParser:
    def parse(self, response: ProviderResponse) -> RequirementCompositionVerificationResult:
        payload = response.parsed_json
        if payload is None:
            payload = parse_json_object_from_text(response.raw_text)
        elif not isinstance(payload, dict):
            raise ValueError("provider output must be a JSON object")
        return RequirementCompositionVerificationResult.from_dict(payload)
