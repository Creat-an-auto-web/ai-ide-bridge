from __future__ import annotations

import json

from .models import (
    RequirementCompositionVerificationInput,
    capability_groups_to_payload,
    story_units_to_payload,
)


class RequirementCompositionVerificationPromptBuilder:
    json_example = {
        "status": "revise",
        "summary": "当前 story 组合覆盖了导出主路径，但缺少权限限制与失败反馈两个集成测试关键环节。",
        "coverage_assessment": {
            "covers_primary_user_goal": True,
            "covers_permission_constraints": False,
            "covers_failure_handling": False,
            "covers_end_to_end_flow": False,
        },
        "composition_issues": [
            {
                "id": "comp_issue_001",
                "severity": "high",
                "issue_type": "missing_permission_path",
                "message": "导出主流程存在，但没有 story 说明无权限用户应如何被拦截。",
                "related_story_ids": ["S1"],
                "related_capability_group_ids": ["CG1"],
                "suggested_action": "add_story",
            }
        ],
        "integration_test_scenarios": [
            {
                "id": "it_export_success",
                "title": "用户按当前筛选条件成功导出任务记录",
                "covers_story_ids": ["S1"],
                "covers_capability_group_ids": ["CG1"],
                "expected_outcome": "系统返回与当前筛选条件一致的导出文件。",
            }
        ],
        "redundant_story_ids": [],
        "missing_story_topics": ["导出权限控制", "导出失败反馈"],
        "revision_guidance": [
            "补充一条导出权限控制 story。",
            "补充一条导出失败反馈 story。",
        ],
    }

    def build_system_prompt(self) -> str:
        return (
            "你是 RequirementCompositionVerificationAgent。"
            "你的任务不是重写单条 user story，而是从集成测试和业务闭环角度审查整组 story 是否组合合理。"
            "你只能返回一个标准 json 对象。"
            "不要输出 markdown，不要使用 ```json 代码块，不要添加任何前缀、后缀或解释。"
            "输出必须能被 json.loads 直接解析。"
            "你要重点检查主路径覆盖、权限路径、失败路径、依赖顺序和 capability 分组是否支撑完整交付。"
        )

    def build_user_prompt(
        self,
        verification_input: RequirementCompositionVerificationInput,
    ) -> str:
        analysis_input = verification_input.analysis_input
        analysis_result = verification_input.analysis_result
        payload = {
            "session_id": verification_input.session_id,
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
                "capability_groups": capability_groups_to_payload(analysis_result.capability_groups),
                "story_units": story_units_to_payload(analysis_result.story_units),
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
            "coverage_assessment": {
                "covers_primary_user_goal": True,
                "covers_permission_constraints": False,
                "covers_failure_handling": False,
                "covers_end_to_end_flow": False,
            },
            "composition_issues": [
                {
                    "id": "...",
                    "severity": "low|medium|high",
                    "issue_type": "missing_story|redundant_story|conflicting_story|dependency_gap|dependency_order_error|missing_permission_path|missing_failure_path|missing_integration_path|capability_group_misaligned|scope_coverage_gap",
                    "message": "...",
                    "related_story_ids": ["..."],
                    "related_capability_group_ids": ["..."],
                    "suggested_action": "add_story|split_story|merge_story|adjust_dependency|move_story_between_groups|clarify_scope",
                }
            ],
            "integration_test_scenarios": [
                {
                    "id": "...",
                    "title": "...",
                    "covers_story_ids": ["..."],
                    "covers_capability_group_ids": ["..."],
                    "expected_outcome": "...",
                }
            ],
            "redundant_story_ids": ["..."],
            "missing_story_topics": ["..."],
            "revision_guidance": ["..."],
        }
        return (
            "请从组合合理性角度审查下面的需求分析结果。\n"
            "要求：\n"
            "1. 只允许返回一个标准 json 对象，且必须能被 json.loads 直接解析。\n"
            "2. 不要输出 markdown，不要使用 ```json 代码块，不要添加任何解释、前缀或后缀。\n"
            "3. 这不是单条 story 文案检查，而是整组 story 的业务闭环检查。\n"
            "4. 必须检查主路径、权限路径、失败路径和跨 story 依赖是否完整。\n"
            "5. 如果当前 story 集合已经足以构造端到端验证场景，status 设为 pass。\n"
            "6. 如果存在可修复缺口，status 设为 revise，并给出 revision_guidance。\n"
            "7. 如果当前信息不足或 story 集合与原始需求严重冲突，status 设为 blocked。\n"
            "8. 必须给出 integration_test_scenarios，说明哪些 stories 组合起来构成完整验证场景。\n"
            "9. 不要重写所有 stories，只指出组合级问题和缺口。\n\n"
            f"输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"输出结构：\n{json.dumps(output_shape, ensure_ascii=False, indent=2)}\n\n"
            "输出完整 json 示例：\n"
            "请严格参考下面示例的 json 层级、字段名、数组/对象位置与字符串类型；示例仅用于格式参考，不要照抄内容。\n"
            f"{json.dumps(self.json_example, ensure_ascii=False, indent=2)}"
        )
