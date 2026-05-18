from __future__ import annotations

import re

from tdd_agent_framework.agents.requirement_analysis.models import (
    VerificationIssue,
    VerificationQualityScore,
    RequirementVerificationResult,
)
from tdd_agent_framework.core import (
    AgentRunContext,
    BaseAgent,
    ProviderMessage,
    ProviderRequest,
)

from .models import RequirementVerificationInput
from .parser import RequirementVerificationParser
from .prompt_builder import RequirementVerificationPromptBuilder


class RequirementVerificationAgent(
    BaseAgent[RequirementVerificationInput, RequirementVerificationResult],
):
    name = "requirement_verification"

    def __init__(
        self,
        provider,
        model_target,
        generation_config=None,
        prompt_builder: RequirementVerificationPromptBuilder | None = None,
        parser: RequirementVerificationParser | None = None,
    ) -> None:
        super().__init__(
            provider=provider,
            model_target=model_target,
            generation_config=generation_config,
        )
        self.prompt_builder = prompt_builder or RequirementVerificationPromptBuilder()
        self.parser = parser or RequirementVerificationParser()

    def build_request(
        self,
        data: RequirementVerificationInput,
        context: AgentRunContext,
    ) -> ProviderRequest:
        return ProviderRequest(
            agent_name=self.name,
            task_id=context.task_id,
            model_target=self.model_target,
            system_prompt=self.prompt_builder.build_system_prompt(),
            messages=(
                ProviderMessage(
                    role="user",
                    content=self.prompt_builder.build_user_prompt(data),
                ),
            ),
            generation_config=self.generation_config,
            metadata={"trace_id": context.trace_id, **context.metadata},
        )

    def parse_response(self, response) -> RequirementVerificationResult:
        return self.parser.parse(response)

    def finalize_output(
        self,
        data: RequirementVerificationInput,
        context: AgentRunContext,
        output: RequirementVerificationResult,
    ) -> RequirementVerificationResult:
        return self._enforce_explicit_capability_coverage(data, output)

    def _enforce_explicit_capability_coverage(
        self,
        data: RequirementVerificationInput,
        output: RequirementVerificationResult,
    ) -> RequirementVerificationResult:
        required_capabilities = self._extract_explicit_capabilities(data.analysis_input.user_prompt)
        if len(required_capabilities) < 3:
            return output

        story_text = " ".join(
            [data.analysis_result.requirement_spec.product_goal]
            + data.analysis_result.requirement_spec.scope
            + [story.title for story in data.analysis_result.story_units]
            + [story.when_context for story in data.analysis_result.story_units]
            + [story.i_want for story in data.analysis_result.story_units]
            + [story.business_outcome for story in data.analysis_result.story_units]
            + [criterion for story in data.analysis_result.story_units for criterion in story.acceptance_criteria]
        )
        missing = [capability for capability in required_capabilities if capability not in story_text]
        if not missing:
            return output

        issue = VerificationIssue(
            id="explicit_capability_coverage",
            severity="medium",
            issue_type="missing_story",
            message=f"原始需求显式要求能力未被 story 明确覆盖：{'、'.join(missing)}。",
            affected_story_ids=[],
        )
        existing_issues = list(output.issues)
        if not any(item.id == issue.id for item in existing_issues):
            existing_issues.append(issue)
        guidance = list(output.revision_guidance)
        guidance_text = f"补齐原始需求中显式列出的能力：{'、'.join(missing)}。"
        if guidance_text not in guidance:
            guidance.insert(0, guidance_text)
        return RequirementVerificationResult(
            status="revise",
            summary=f"{output.summary} 原始需求仍有显式能力未被覆盖。",
            issues=existing_issues,
            revision_guidance=guidance,
            quality_score=VerificationQualityScore(
                scope_clarity=min(output.quality_score.scope_clarity, 74),
                testability=output.quality_score.testability,
                dependency_sanity=output.quality_score.dependency_sanity,
                story_granularity=output.quality_score.story_granularity,
            ),
        )

    def _extract_explicit_capabilities(self, user_prompt: str) -> list[str]:
        normalized_prompt = user_prompt.strip()
        segments: list[str] = []
        for marker in ("具备", "包括", "包含", "支持", "实现", "提供"):
            marker_index = normalized_prompt.find(marker)
            if marker_index >= 0:
                segments.append(normalized_prompt[marker_index + len(marker):])

        candidates: list[str] = []
        for segment in segments or [normalized_prompt]:
            bounded_segment = re.split(r"[。；;\n]", segment, maxsplit=1)[0]
            for item in re.split(r"[、,，/]", bounded_segment):
                candidate = self._normalize_capability_candidate(item)
                if candidate:
                    candidates.append(candidate)

        required: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                required.append(candidate)
        return required

    def _normalize_capability_candidate(self, value: str) -> str | None:
        candidate = re.sub(r"^(和|及|以及|等|的|并|与|还有)", "", value.strip())
        candidate = re.sub(r"(等功能|等能力|功能|能力|模块|系统)$", "", candidate).strip()
        if not candidate or len(candidate) > 16:
            return None
        if candidate in {"网站", "应用", "平台", "系统", "一个", "等"}:
            return None
        return candidate
