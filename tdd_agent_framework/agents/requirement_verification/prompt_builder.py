from __future__ import annotations

import json

from .models import RequirementVerificationInput


class RequirementVerificationPromptBuilder:
    def build_system_prompt(self) -> str:
        return (
            "你是 RequirementVerificationAgent。"
            "你必须独立审查需求拆解结果，不要假设分析初稿一定正确。"
            "输出必须是合法 json 对象，不要输出 markdown，不要解释。"
            "你要关注范围完整性、验收标准可测试性、story 颗粒度、user story 叙事质量和依赖合理性。"
        )

    def build_user_prompt(self, verification_input: RequirementVerificationInput) -> str:
        analysis_input = verification_input.analysis_input
        analysis_result = verification_input.analysis_result
        payload = {
            "iteration": verification_input.iteration,
            "task_id": analysis_input.task_id,
            "user_prompt": analysis_input.user_prompt,
            "workspace_summary": {
                "languages": analysis_input.workspace_summary.languages,
                "frameworks": analysis_input.workspace_summary.frameworks,
                "key_modules": analysis_input.workspace_summary.key_modules,
            },
            "execution_constraints": {
                "disallow_new_dependencies": analysis_input.execution_constraints.disallow_new_dependencies,
                "preserve_public_api": analysis_input.execution_constraints.preserve_public_api,
                "max_capability_groups": analysis_input.execution_constraints.max_capability_groups,
                "max_story_units": analysis_input.execution_constraints.max_story_units,
            },
            "analysis_result": {
                "requirement_spec": {
                    "task_id": analysis_result.requirement_spec.task_id,
                    "version": analysis_result.requirement_spec.version,
                    "problem_statement": analysis_result.requirement_spec.problem_statement,
                    "product_goal": analysis_result.requirement_spec.product_goal,
                    "scope": analysis_result.requirement_spec.scope,
                    "out_of_scope": analysis_result.requirement_spec.out_of_scope,
                    "constraints": analysis_result.requirement_spec.constraints,
                    "assumptions": analysis_result.requirement_spec.assumptions,
                    "interfaces_or_contracts": analysis_result.requirement_spec.interfaces_or_contracts,
                    "acceptance_criteria": analysis_result.requirement_spec.acceptance_criteria,
                    "decomposition_strategy": analysis_result.requirement_spec.decomposition_strategy,
                },
                "capability_groups": [
                    {
                        "id": group.id,
                        "title": group.title,
                        "goal": group.goal,
                        "scope": group.scope,
                        "story_ids": group.story_ids,
                        "priority": group.priority,
                    }
                    for group in analysis_result.capability_groups
                ],
                "story_units": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "as_a": item.as_a,
                        "i_want": item.i_want,
                        "so_that": item.so_that,
                        "narrative": item.narrative,
                        "actor": item.actor,
                        "goal": item.goal,
                        "business_value": item.business_value,
                        "scope": item.scope,
                        "out_of_scope": item.out_of_scope,
                        "acceptance_criteria": item.acceptance_criteria,
                        "dependencies": item.dependencies,
                        "priority": item.priority,
                        "risk": item.risk,
                        "test_focus": item.test_focus,
                        "implementation_hints": item.implementation_hints,
                    }
                    for item in analysis_result.story_units
                ],
                "quality_checks": {
                    "has_clear_scope": analysis_result.quality_checks.has_clear_scope,
                    "has_testable_ac": analysis_result.quality_checks.has_testable_ac,
                    "dependency_graph_valid": analysis_result.quality_checks.dependency_graph_valid,
                    "story_count_within_limit": analysis_result.quality_checks.story_count_within_limit,
                },
                "warnings": analysis_result.warnings,
            },
        }
        output_shape = {
            "status": "pass|revise|blocked",
            "summary": "...",
            "issues": [
                {
                    "id": "...",
                    "severity": "low|medium|high",
                    "type": "missing_scope|untestable_ac|dependency_conflict|over_scoped|under_scoped|missing_story|blocked_dependency",
                    "message": "...",
                    "affected_story_ids": ["..."],
                }
            ],
            "revision_guidance": ["..."],
            "quality_score": {
                "scope_clarity": 0,
                "testability": 0,
                "dependency_sanity": 0,
                "story_granularity": 0,
            },
        }
        return (
            "请作为独立验证者检查下面的需求拆解结果。\n"
            "要求：\n"
            "1. 输出必须是 json 对象。\n"
            "2. 如果结果可以直接交给测试生成环节，status 设为 pass。\n"
            "3. 如果存在可修复问题，status 设为 revise，并给出 revision_guidance。\n"
            "4. 如果缺少关键前提、无法继续，status 设为 blocked。\n"
            "5. 要同时检查 capability_groups 与 story_units 的边界是否一致。\n"
            "6. 要检查每个 story_unit 是否真的是 user story，而不是模块名、页面名或纯技术任务名。\n"
            "7. issues 要聚焦真正的问题，不要为了凑数量而制造问题。\n\n"
            f"输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"输出结构：\n{json.dumps(output_shape, ensure_ascii=False, indent=2)}"
        )
