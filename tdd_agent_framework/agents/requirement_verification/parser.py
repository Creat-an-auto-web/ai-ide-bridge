from __future__ import annotations

import json

from tdd_agent_framework.agents.requirement_analysis.models import (
    RequirementVerificationResult,
)
from tdd_agent_framework.core import ProviderResponse


class RequirementVerificationParser:
    def parse(self, response: ProviderResponse) -> RequirementVerificationResult:
        payload = response.parsed_json
        if payload is None:
            payload = json.loads(response.raw_text)
        if not isinstance(payload, dict):
            raise ValueError("provider output must be a JSON object")
        return RequirementVerificationResult.from_dict(payload)
