from __future__ import annotations

from dataclasses import dataclass

from tdd_agent_framework.agents.test_case_generation import (
    TestCaseCompletionCheck,
    TestCaseGenerationInput,
    TestCaseGenerationResult,
)


@dataclass(frozen=True)
class TestCaseGenerationVerificationInput:
    plan: str
    generation_input: TestCaseGenerationInput
    generation_result: TestCaseGenerationResult


@dataclass(frozen=True)
class TestCaseGenerationVerificationResult(TestCaseCompletionCheck):
    pass
