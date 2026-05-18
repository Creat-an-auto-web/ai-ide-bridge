from __future__ import annotations

from tdd_agent_framework.core import ProviderResponse, parse_json_object_from_text

from .models import (
    CapabilityGroup,
    QualityChecks,
    RequirementAnalysisInput,
    RequirementAnalysisResult,
    RequirementSpec,
    StoryUnit,
    build_analysis_summary,
)


class RequirementAnalysisParser:
    def parse(
        self,
        response: ProviderResponse,
        analysis_input: RequirementAnalysisInput | None = None,
    ) -> RequirementAnalysisResult:
        payload = response.parsed_json
        if payload is None:
            payload = parse_json_object_from_text(response.raw_text)
        elif not isinstance(payload, dict):
            raise ValueError("provider output must be a JSON object")
        payload = self._unwrap_payload(payload)

        if analysis_input is not None and not self._contains_requirement_analysis_fields(payload):
            payload = self._rebuild_payload_from_input(payload, analysis_input)

        raw_requirement_spec = payload.get("requirement_spec") or payload.get("requirementSpec")
        raw_story_units = payload.get("story_units") or payload.get("storyUnits") or payload.get("stories")
        requirement_spec = self._normalize_requirement_spec(
            raw_requirement_spec,
            payload=payload,
            raw_story_units=raw_story_units,
        )
        if not isinstance(raw_story_units, list) or not raw_story_units:
            raise ValueError("story_units must be a non-empty list")
        raw_story_units = [
            self._normalize_story_unit(item, requirement_spec, index=index + 1)
            for index, item in enumerate(raw_story_units)
        ]
        story_units = [StoryUnit.from_dict(item) for item in raw_story_units]
        capability_groups = self._parse_capability_groups(payload, story_units, requirement_spec)

        warnings = payload.get("warnings", [])
        if not isinstance(warnings, list):
            raise ValueError("warnings must be a list of strings")

        return RequirementAnalysisResult(
            requirement_spec=requirement_spec,
            story_units=story_units,
            analysis_summary=build_analysis_summary(story_units, capability_groups),
            warnings=[str(item) for item in warnings],
            quality_checks=QualityChecks(
                has_clear_scope=False,
                has_testable_ac=False,
                dependency_graph_valid=False,
                story_count_within_limit=False,
            ),
            capability_groups=capability_groups,
        )

    def _contains_requirement_analysis_fields(self, payload: dict) -> bool:
        return any(
            key in payload
            for key in ("requirement_spec", "requirementSpec", "story_units", "storyUnits", "stories")
        )

    def _unwrap_payload(self, payload: dict) -> dict:
        current = payload
        visited_ids: set[int] = set()
        while isinstance(current, dict) and id(current) not in visited_ids:
            visited_ids.add(id(current))
            candidate = None
            for key in ("data", "result", "output", "analysis_result"):
                nested = current.get(key)
                if isinstance(nested, dict):
                    candidate = nested
                    break
            if candidate is None:
                return current
            if any(
                key in candidate
                for key in ("requirement_spec", "requirementSpec", "story_units", "storyUnits", "stories")
            ):
                return candidate
            current = candidate
        return payload

    def _rebuild_payload_from_input(
        self,
        payload: dict,
        analysis_input: RequirementAnalysisInput,
    ) -> dict:
        story_title = self._build_fallback_story_title(analysis_input.user_prompt)
        story_scope = self._build_fallback_scope(analysis_input)
        issues = self._collect_issue_messages(payload)
        revision_guidance = self._normalize_string_list(payload.get("revision_guidance"))
        summary = self._first_non_empty_str(
            payload.get("summary"),
            payload.get("message"),
            analysis_input.previous_verification_summary,
            default="本轮模型返回了非需求分析结构，已基于原始需求上下文自动重建最小需求包。",
        )
        fallback_warnings = [
            "模型本轮未返回标准 RequirementAnalysis 结构，系统已基于原始需求上下文自动重建最小结果。",
            f"原始返回摘要：{summary}",
        ]
        fallback_warnings.extend(f"原始返回问题：{message}" for message in issues[:3])
        fallback_warnings.extend(f"原始返回修订建议：{item}" for item in revision_guidance[:3])

        return {
            "requirement_spec": {
                "task_id": analysis_input.task_id,
                "version": 1,
                "problem_statement": analysis_input.user_prompt,
                "product_goal": "将原始需求整理为可继续迭代、可验证的结构化需求包。",
                "scope": story_scope,
                "out_of_scope": [],
                "constraints": self._build_fallback_constraints(analysis_input, summary, issues),
                "assumptions": [
                    "本轮模型返回了非需求分析结构，当前结果由系统基于原始需求上下文自动重建。",
                ],
                "interfaces_or_contracts": [],
                "acceptance_criteria": [
                    "需求包会保留原始需求中的核心业务目标，供后续轮次继续细化。",
                    "至少保留一条可测试、可继续修订的核心 user story。",
                    "当前结果会保留上一轮修订意见和失败摘要，避免继续优化时丢失上下文。",
                ],
                "decomposition_strategy": "先保留单一核心 story，再在后续轮次继续补齐能力分组与细化 story。",
            },
            "capability_groups": [
                {
                    "id": "capability_group_1",
                    "title": "原始需求核心目标",
                    "goal": "保留当前原始需求的核心业务目标，供下一轮继续优化。",
                    "scope": story_scope,
                    "story_ids": ["S1"],
                    "priority": "high",
                }
            ],
            "story_units": [
                {
                    "id": "S1",
                    "story_kind": "user_outcome",
                    "title": story_title,
                    "as_a": "目标角色",
                    "when_context": "我正在执行当前原始需求对应的核心业务场景",
                    "i_want": "完成当前原始需求中的核心业务能力",
                    "so_that": "我可以满足原始需求并进入后续实现与测试阶段",
                    "narrative": "作为目标角色，当我正在执行当前原始需求对应的核心业务场景时，我希望完成当前原始需求中的核心业务能力，从而我可以满足原始需求并进入后续实现与测试阶段。",
                    "actor": "目标角色",
                    "goal": "完成当前原始需求中的核心业务能力",
                    "business_value": "我可以满足原始需求并进入后续实现与测试阶段",
                    "business_outcome": "系统保留了一条可继续细化和验证的核心业务目标。",
                    "scope": story_scope,
                    "out_of_scope": [],
                    "acceptance_criteria": [
                        "给定原始需求已经明确，当进入需求分析阶段时，那么结果会保留可执行的业务目标边界。",
                        "给定用户执行核心业务路径，当对应能力实现完成时，那么用户可以观察到明确且可验证的业务结果。",
                        "给定上一轮存在修订意见或失败摘要，当继续优化再次开始时，那么当前 story 会保留这些上下文供下一轮细化。",
                    ],
                    "dependencies": [],
                    "priority": "high",
                    "risk": "medium",
                    "test_focus": [
                        "原始需求核心路径",
                        "继续优化上下文保留",
                        "后续细化可扩展性",
                    ],
                    "implementation_hints": revision_guidance[:3] or issues[:3],
                }
            ],
            "warnings": fallback_warnings,
        }

    def _normalize_requirement_spec(
        self,
        raw_requirement_spec: object,
        *,
        payload: dict,
        raw_story_units: object,
    ) -> RequirementSpec:
        if not isinstance(raw_story_units, list) or not raw_story_units:
            if isinstance(raw_requirement_spec, dict):
                raise ValueError("story_units must be a non-empty list")
            raise ValueError("provider output must contain either requirement_spec or non-empty story_units")

        base_spec = dict(raw_requirement_spec) if isinstance(raw_requirement_spec, dict) else {}

        task_id = self._first_non_empty_str(
            base_spec.get("task_id"),
            base_spec.get("taskId"),
            payload.get("task_id"),
            payload.get("taskId"),
            default="unknown_task",
        )
        user_prompt = self._first_non_empty_str(
            base_spec.get("problem_statement"),
            payload.get("user_prompt"),
            payload.get("userPrompt"),
            default="原始需求未显式返回，需基于 story_units 继续补全。",
        )
        story_scopes = self._collect_story_scope(raw_story_units)
        story_titles = self._collect_story_titles(raw_story_units)
        acceptance_criteria = self._collect_acceptance_criteria(raw_story_units)
        story_count = len([item for item in raw_story_units if isinstance(item, dict)])

        fallback_spec = {
            "task_id": task_id,
            "version": base_spec.get("version", 1),
            "problem_statement": user_prompt,
            "product_goal": self._first_non_empty_str(
                base_spec.get("product_goal"),
                base_spec.get("productGoal"),
                default=self._build_product_goal(story_titles),
            ),
            "scope": self._normalize_string_list(base_spec.get("scope")) or story_scopes or ["core_scope"],
            "out_of_scope": self._normalize_string_list(
                base_spec.get("out_of_scope") or base_spec.get("outOfScope")
            ),
            "constraints": self._normalize_string_list(base_spec.get("constraints")),
            "assumptions": self._normalize_string_list(base_spec.get("assumptions")),
            "interfaces_or_contracts": self._normalize_string_list(
                base_spec.get("interfaces_or_contracts") or base_spec.get("interfacesOrContracts")
            ),
            "acceptance_criteria": (
                self._normalize_string_list(
                    base_spec.get("acceptance_criteria") or base_spec.get("acceptanceCriteria")
                )
                or acceptance_criteria
                or ["story_units 需要被补全并通过后续验证"]
            ),
            "decomposition_strategy": self._first_non_empty_str(
                base_spec.get("decomposition_strategy"),
                base_spec.get("decompositionStrategy"),
                default=(
                "按 capability_groups 分组拆分"
                if story_count > 1
                else "按单一 story 输出"
                ),
            ),
        }
        return RequirementSpec.from_dict(fallback_spec)

    def _normalize_story_unit(
        self,
        item: object,
        requirement_spec: RequirementSpec,
        *,
        index: int,
    ) -> dict:
        if not isinstance(item, dict):
            raise ValueError("story_unit must be an object")

        normalized = dict(item)
        actor = self._first_non_empty_str(
            normalized.get("as_a"),
            normalized.get("actor"),
            default="相关角色",
        )
        goal = self._first_non_empty_str(
            normalized.get("i_want"),
            normalized.get("goal"),
            default="完成当前业务目标",
        )
        when_context = self._first_non_empty_str(
            normalized.get("when_context"),
            normalized.get("context"),
            default="用户处于需要完成该业务目标的业务场景中",
        )

        normalized["id"] = self._first_non_empty_str(
            normalized.get("id"),
            default=f"S{index}",
        )
        normalized["story_kind"] = self._first_non_empty_str(
            normalized.get("story_kind"),
            default="user_outcome",
        )
        normalized["as_a"] = actor
        normalized["actor"] = actor
        normalized["i_want"] = goal
        normalized["goal"] = goal
        normalized["when_context"] = when_context
        normalized["context"] = when_context
        normalized["title"] = self._first_non_empty_str(
            normalized.get("title"),
            default=f"{actor}可以{goal}",
        )

        if not self._has_non_empty_list(normalized.get("scope")):
            fallback_scope = requirement_spec.scope[:3] if requirement_spec.scope else ["core_scope"]
            normalized["scope"] = fallback_scope

        if normalized.get("out_of_scope") is None:
            normalized["out_of_scope"] = []

        if not self._has_non_empty_list(normalized.get("acceptance_criteria")):
            normalized["acceptance_criteria"] = (
                requirement_spec.acceptance_criteria[:3]
                if requirement_spec.acceptance_criteria
                else [
                    f"给定{actor}处于目标场景，当发起{goal}时，那么系统返回可验证结果",
                    "给定主路径执行成功，当业务结果产生时，那么用户可以观察到预期结果",
                    "给定主路径执行失败，当系统无法完成能力时，那么用户可以获得明确失败反馈",
                ]
            )

        if not self._has_non_empty_list(normalized.get("test_focus")):
            acceptance_criteria = normalized.get("acceptance_criteria")
            if isinstance(acceptance_criteria, list):
                fallback_focus = [str(value).strip() for value in acceptance_criteria if str(value).strip()][:3]
            else:
                fallback_focus = []
            normalized["test_focus"] = fallback_focus or ["主路径验证"]

        if normalized.get("implementation_hints") is None:
            normalized["implementation_hints"] = []

        if not isinstance(normalized.get("so_that"), str) or not str(normalized.get("so_that")).strip():
            business_value = normalized.get("business_value")
            if isinstance(business_value, str) and business_value.strip():
                normalized["so_that"] = business_value.strip()

        if not isinstance(normalized.get("business_outcome"), str) or not str(normalized.get("business_outcome")).strip():
            so_that = normalized.get("so_that")
            i_want = normalized.get("i_want") or normalized.get("goal")
            if isinstance(so_that, str) and so_that.strip():
                normalized["business_outcome"] = so_that.strip()
            elif isinstance(i_want, str) and i_want.strip():
                normalized["business_outcome"] = i_want.strip()

        normalized["priority"] = self._normalize_level(normalized.get("priority"), default="medium")
        normalized["risk"] = self._normalize_level(normalized.get("risk"), default="medium")
        if normalized.get("business_value") is None and isinstance(normalized.get("so_that"), str):
            normalized["business_value"] = normalized["so_that"]

        return normalized

    def _has_non_empty_list(self, value: object) -> bool:
        return isinstance(value, list) and any(isinstance(item, str) and item.strip() for item in value)

    def _first_non_empty_str(self, *values: object, default: str) -> str:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return default

    def _collect_story_scope(self, raw_story_units: list[object]) -> list[str]:
        scope: list[str] = []
        seen: set[str] = set()
        for item in raw_story_units:
            if not isinstance(item, dict):
                continue
            story_scope = item.get("scope")
            if not isinstance(story_scope, list):
                continue
            for entry in story_scope:
                if not isinstance(entry, str):
                    continue
                stripped = entry.strip()
                if stripped and stripped not in seen:
                    seen.add(stripped)
                    scope.append(stripped)
        return scope[:8]

    def _collect_story_titles(self, raw_story_units: list[object]) -> list[str]:
        titles: list[str] = []
        for item in raw_story_units:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            if isinstance(title, str) and title.strip():
                titles.append(title.strip())
        return titles

    def _collect_acceptance_criteria(self, raw_story_units: list[object]) -> list[str]:
        collected: list[str] = []
        seen: set[str] = set()
        for item in raw_story_units:
            if not isinstance(item, dict):
                continue
            acceptance_criteria = item.get("acceptance_criteria")
            if not isinstance(acceptance_criteria, list):
                continue
            for criterion in acceptance_criteria:
                text = str(criterion).strip()
                if text and text not in seen:
                    seen.add(text)
                    collected.append(text)
                if len(collected) >= 6:
                    return collected
        return collected

    def _build_product_goal(self, story_titles: list[str]) -> str:
        if not story_titles:
            return "基于当前 story_units 产出可验证的结构化需求结果。"
        if len(story_titles) == 1:
            return f"围绕“{story_titles[0]}”产出可验证的结构化需求结果。"
        return f"围绕 {len(story_titles)} 条核心 story 产出可验证的结构化需求结果。"

    def _build_fallback_story_title(self, user_prompt: str) -> str:
        compact = " ".join(user_prompt.strip().split())
        if compact:
            compact = compact[:32]
            return f"目标角色可以围绕“{compact}”完成核心业务目标"
        return "目标角色可以完成当前原始需求中的核心业务目标"

    def _build_fallback_scope(self, analysis_input: RequirementAnalysisInput) -> list[str]:
        if analysis_input.revision_focus:
            scope = [item.strip() for item in analysis_input.revision_focus if item.strip()]
            if scope:
                return scope[:3]
        return ["原始需求核心业务目标", "继续优化上下文保留"]

    def _build_fallback_constraints(
        self,
        analysis_input: RequirementAnalysisInput,
        summary: str,
        issues: list[str],
    ) -> list[str]:
        constraints: list[str] = []
        if analysis_input.execution_constraints.preserve_public_api:
            constraints.append("继续优化时保持现有公共接口不变。")
        if analysis_input.execution_constraints.disallow_new_dependencies:
            constraints.append("继续优化时不新增外部依赖。")
        if summary:
            constraints.append(f"需吸收上一轮摘要中的修订背景：{summary}")
        constraints.extend(f"需处理上一轮指出的问题：{message}" for message in issues[:2])
        return constraints

    def _collect_issue_messages(self, payload: dict) -> list[str]:
        raw_issues = payload.get("issues")
        if not isinstance(raw_issues, list):
            return []
        messages: list[str] = []
        for item in raw_issues:
            if isinstance(item, dict):
                message = item.get("message")
                if isinstance(message, str) and message.strip():
                    messages.append(message.strip())
                    continue
            text = str(item).strip()
            if text:
                messages.append(text)
        return messages

    def _parse_capability_groups(
        self,
        payload: dict,
        story_units: list[StoryUnit],
        requirement_spec: RequirementSpec,
    ) -> list[CapabilityGroup]:
        raw_groups = payload.get("capability_groups") or payload.get("capabilityGroups")
        if isinstance(raw_groups, list) and raw_groups:
            normalized_groups = [
                self._normalize_capability_group(
                    item,
                    story_units=story_units,
                    requirement_spec=requirement_spec,
                    index=index + 1,
                )
                for index, item in enumerate(raw_groups)
            ]
            return [CapabilityGroup.from_dict(item) for item in normalized_groups]

        return [
            CapabilityGroup(
                id="capability_group_1",
                title="整体需求分组",
                goal="在缺少显式 capability_groups 时保留最小分层结构",
                scope=sorted({scope for story in story_units for scope in story.scope})[:8] or ["core_scope"],
                story_ids=[story.id for story in story_units],
                priority="high" if any(story.priority == "high" for story in story_units) else "medium",
            )
        ]

    def _normalize_capability_group(
        self,
        item: object,
        *,
        story_units: list[StoryUnit],
        requirement_spec: RequirementSpec,
        index: int,
    ) -> dict:
        if not isinstance(item, dict):
            raise ValueError("capability_group must be an object")

        normalized = dict(item)
        all_story_ids = [story.id for story in story_units]
        referenced_story_ids = [
            story_id
            for story_id in self._normalize_string_list(normalized.get("story_ids") or normalized.get("storyIds"))
            if story_id in all_story_ids
        ]
        if not referenced_story_ids:
            referenced_story_ids = all_story_ids

        group_scope = self._normalize_string_list(normalized.get("scope"))
        if not group_scope:
            story_scope = sorted(
                {
                    scope
                    for story in story_units
                    if story.id in referenced_story_ids
                    for scope in story.scope
                }
            )
            group_scope = story_scope[:8] or requirement_spec.scope[:3] or ["core_scope"]

        normalized["id"] = self._first_non_empty_str(normalized.get("id"), default=f"capability_group_{index}")
        normalized["title"] = self._first_non_empty_str(
            normalized.get("title"),
            default=f"能力分组 {index}",
        )
        normalized["goal"] = self._first_non_empty_str(
            normalized.get("goal"),
            default=f"支撑 {len(referenced_story_ids)} 条 story 组成可交付能力闭环",
        )
        normalized["scope"] = group_scope
        normalized["story_ids"] = referenced_story_ids
        normalized["priority"] = self._normalize_level(normalized.get("priority"), default="medium")
        return normalized

    def _normalize_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                continue
            stripped = item.strip()
            if stripped and stripped not in seen:
                seen.add(stripped)
                normalized.append(stripped)
        return normalized

    def _normalize_level(self, value: object, *, default: str) -> str:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"low", "medium", "high"}:
                return lowered
        return default
