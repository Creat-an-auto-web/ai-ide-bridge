from __future__ import annotations

from dataclasses import dataclass

from tdd_agent_framework.agents.requirement_analysis.models import (
    RequirementAnalysisInput,
    RequirementAnalysisResult,
)


@dataclass(frozen=True)
class RequirementVerificationInput:
    analysis_input: RequirementAnalysisInput
    analysis_result: RequirementAnalysisResult
    iteration: int = 1
