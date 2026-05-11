from __future__ import annotations

from dataclasses import replace

from .models import (
    CapabilityGroup,
    QualityChecks,
    RequirementAnalysisInput,
    RequirementAnalysisResult,
    StoryUnit,
)


ALLOWED_LEVELS = {"low", "medium", "high"}


class RequirementAnalysisValidationError(ValueError):
    """需求分析输出未通过质量校验。"""


class RequirementAnalysisQualityChecker:
    def validate(
        self,
        analysis_input: RequirementAnalysisInput,
        result: RequirementAnalysisResult,
    ) -> RequirementAnalysisResult:
        warnings = list(result.warnings)
        self._validate_requirement_spec(analysis_input, result)
        self._validate_capability_groups(
            analysis_input,
            result.capability_groups,
            result.story_units,
            warnings,
        )
        self._validate_story_units(analysis_input, result.story_units, warnings)

        quality_checks = QualityChecks(
            has_clear_scope=bool(result.requirement_spec.scope)
            and not set(result.requirement_spec.scope).intersection(result.requirement_spec.out_of_scope),
            has_testable_ac=self._has_testable_ac(result),
            dependency_graph_valid=True,
            story_count_within_limit=len(result.story_units)
            <= analysis_input.execution_constraints.max_story_units,
        )

        if not quality_checks.story_count_within_limit:
            raise RequirementAnalysisValidationError(
                "story_units count exceeds execution_constraints.max_story_units",
            )
        if not quality_checks.has_testable_ac:
            raise RequirementAnalysisValidationError("acceptance_criteria are not specific enough")

        return replace(result, warnings=warnings, quality_checks=quality_checks)

    def _validate_requirement_spec(
        self,
        analysis_input: RequirementAnalysisInput,
        result: RequirementAnalysisResult,
    ) -> None:
        if result.requirement_spec.task_id != analysis_input.task_id:
            raise RequirementAnalysisValidationError("requirement_spec.task_id does not match task_id")
        scope_conflict = set(result.requirement_spec.scope).intersection(
            result.requirement_spec.out_of_scope,
        )
        if scope_conflict:
            raise RequirementAnalysisValidationError(
                f"requirement_spec scope conflicts with out_of_scope: {sorted(scope_conflict)}",
            )

    def _validate_story_units(
        self,
        analysis_input: RequirementAnalysisInput,
        story_units: list[StoryUnit],
        warnings: list[str],
    ) -> None:
        seen_ids: set[str] = set()
        for story in story_units:
            if story.id in seen_ids:
                raise RequirementAnalysisValidationError(f"duplicate story id: {story.id}")
            seen_ids.add(story.id)
            if story.priority not in ALLOWED_LEVELS:
                raise RequirementAnalysisValidationError(
                    f"story priority must be one of {sorted(ALLOWED_LEVELS)}",
                )
            if story.risk not in ALLOWED_LEVELS:
                raise RequirementAnalysisValidationError(
                    f"story risk must be one of {sorted(ALLOWED_LEVELS)}",
                )
            if story.actor != story.as_a or story.goal != story.i_want or story.business_value != story.so_that:
                raise RequirementAnalysisValidationError(
                    f"story user story fields are inconsistent with legacy aliases: {story.id}",
                )
            if not story.narrative.startswith("As a ") or ", I want " not in story.narrative:
                raise RequirementAnalysisValidationError(
                    f"story narrative must follow user story format: {story.id}",
                )
            if story.so_that and ", so that " not in story.narrative:
                raise RequirementAnalysisValidationError(
                    f"story narrative must include so_that clause when provided: {story.id}",
                )
            overlap = set(story.scope).intersection(story.out_of_scope)
            if overlap:
                raise RequirementAnalysisValidationError(
                    f"story scope conflicts with out_of_scope: {story.id}",
                )
            if len(story.title.strip()) < 4:
                warnings.append(f"story {story.id} title is very short; confirm it is a real user capability")
            if len(story.acceptance_criteria) < 3 or len(story.acceptance_criteria) > 7:
                warnings.append(
                    f"story {story.id} has {len(story.acceptance_criteria)} acceptance criteria; recommended range is 3-7",
                )
        if len(story_units) > analysis_input.execution_constraints.max_story_units:
            raise RequirementAnalysisValidationError(
                "story_units count exceeds execution_constraints.max_story_units",
            )
        self._validate_dependencies(story_units)

    def _validate_capability_groups(
        self,
        analysis_input: RequirementAnalysisInput,
        capability_groups: list[CapabilityGroup],
        story_units: list[StoryUnit],
        warnings: list[str],
    ) -> None:
        if not capability_groups:
            raise RequirementAnalysisValidationError("capability_groups must be a non-empty list")
        if len(capability_groups) > analysis_input.execution_constraints.max_capability_groups:
            raise RequirementAnalysisValidationError(
                "capability_groups count exceeds execution_constraints.max_capability_groups",
            )

        seen_group_ids: set[str] = set()
        all_story_ids = {story.id for story in story_units}
        covered_story_ids: set[str] = set()

        for group in capability_groups:
            if group.id in seen_group_ids:
                raise RequirementAnalysisValidationError(f"duplicate capability group id: {group.id}")
            seen_group_ids.add(group.id)
            if group.priority not in ALLOWED_LEVELS:
                raise RequirementAnalysisValidationError(
                    f"capability group priority must be one of {sorted(ALLOWED_LEVELS)}",
                )
            unknown_story_ids = set(group.story_ids).difference(all_story_ids)
            if unknown_story_ids:
                raise RequirementAnalysisValidationError(
                    f"capability group references unknown story ids: {sorted(unknown_story_ids)}",
                )
            covered_story_ids.update(group.story_ids)
            if len(group.story_ids) == 1:
                warnings.append(
                    f"capability group {group.id} only contains one story; consider whether grouping is too fine-grained",
                )

        uncovered_story_ids = all_story_ids.difference(covered_story_ids)
        if uncovered_story_ids:
            raise RequirementAnalysisValidationError(
                f"stories are not covered by capability_groups: {sorted(uncovered_story_ids)}",
            )

    def _validate_dependencies(self, story_units: list[StoryUnit]) -> None:
        adjacency: dict[str, list[str]] = {story.id: story.dependencies for story in story_units}
        unknown = {
            dependency
            for story in story_units
            for dependency in story.dependencies
            if dependency not in adjacency
        }
        if unknown:
            raise RequirementAnalysisValidationError(
                f"story dependencies reference unknown ids: {sorted(unknown)}",
            )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                raise RequirementAnalysisValidationError("story dependencies contain a cycle")
            visiting.add(node)
            for next_node in adjacency[node]:
                visit(next_node)
            visiting.remove(node)
            visited.add(node)

        for story_id in adjacency:
            visit(story_id)

    def _has_testable_ac(self, result: RequirementAnalysisResult) -> bool:
        requirement_ac = all(len(item.strip()) >= 8 for item in result.requirement_spec.acceptance_criteria)
        story_ac = all(
            len(item.strip()) >= 8
            for story in result.story_units
            for item in story.acceptance_criteria
        )
        return requirement_ac and story_ac
