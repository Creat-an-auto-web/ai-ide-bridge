from __future__ import annotations

import json

from tdd_agent_framework.core import ProviderResponse

from .models import RequirementCompositionVerificationResult


class RequirementCompositionVerificationParser:
    def parse(self, response: ProviderResponse) -> RequirementCompositionVerificationResult:
        payload = response.parsed_json
        if payload is None:
            payload = json.loads(response.raw_text)
        if not isinstance(payload, dict):
            raise ValueError("provider output must be a JSON object")
        return RequirementCompositionVerificationResult.from_dict(payload)
