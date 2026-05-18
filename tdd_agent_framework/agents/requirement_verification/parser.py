from __future__ import annotations

from tdd_agent_framework.agents.requirement_analysis.models import (
    RequirementVerificationResult,
)
from tdd_agent_framework.core import ProviderResponse, parse_json_object_from_text


class RequirementVerificationParser:
    blocking_medium_issue_types = {
        "missing_scope",
        "untestable_ac",
        "dependency_conflict",
        "over_scoped",
        "under_scoped",
        "missing_story",
        "blocked_dependency",
    }

    def parse(self, response: ProviderResponse) -> RequirementVerificationResult:
        payload = response.parsed_json
        if payload is None:
            payload = parse_json_object_from_text(response.raw_text)
        elif not isinstance(payload, dict):
            raise ValueError("provider output must be a JSON object")
        return self._normalize_over_strict_result(RequirementVerificationResult.from_dict(payload))

    def _normalize_over_strict_result(
        self,
        result: RequirementVerificationResult,
    ) -> RequirementVerificationResult:
        if result.status != "revise":
            return result
        if any(issue.severity == "high" for issue in result.issues):
            return result
        if any(
            issue.severity == "medium" and issue.issue_type in self.blocking_medium_issue_types
            for issue in result.issues
        ):
            return result
        score = result.quality_score
        if (
            score.scope_clarity >= 80
            and score.testability >= 80
            and score.dependency_sanity >= 75
            and score.story_granularity >= 75
        ):
            return RequirementVerificationResult(
                status="pass",
                summary=(
                    f"{result.summary} 当前问题均非高严重度，且质量分达到用户审核门槛，"
                    "系统按非阻塞建议处理。"
                ),
                issues=[],
                revision_guidance=list(result.revision_guidance)
                or [issue.message for issue in result.issues],
                quality_score=result.quality_score,
            )
        return result
