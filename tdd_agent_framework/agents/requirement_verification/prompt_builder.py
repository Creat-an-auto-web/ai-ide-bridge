from __future__ import annotations

import json

from .models import RequirementVerificationInput


class RequirementVerificationPromptBuilder:
    json_example = {
        "status": "pass",
        "summary": "当前需求拆解已达到可进入用户审核的质量，只有少量非阻塞优化建议。",
        "issues": [],
        "revision_guidance": ["后续可以在用户审核时继续细化异常提示文案。"],
        "quality_score": {
            "scope_clarity": 82,
            "testability": 82,
            "dependency_sanity": 90,
            "story_granularity": 80,
        },
    }

    def build_system_prompt(self) -> str:
        return (
            "你是 RequirementVerificationAgent。"
            "你必须独立审查需求拆解结果，不要假设分析初稿一定正确。"
            "你只能返回一个标准 json 对象。"
            "不要输出 markdown，不要使用 ```json 代码块，不要添加任何前缀、后缀或解释。"
            "输出必须能被 json.loads 直接解析。"
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
                        "story_kind": item.story_kind,
                        "title": item.title,
                        "as_a": item.as_a,
                        "when_context": item.when_context,
                        "i_want": item.i_want,
                        "so_that": item.so_that,
                        "narrative": item.narrative,
                        "actor": item.actor,
                        "goal": item.goal,
                        "business_value": item.business_value,
                        "business_outcome": item.business_outcome,
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
            "1. 只允许返回一个标准 json 对象，且必须能被 json.loads 直接解析。\n"
            "2. 不要输出 markdown，不要使用 ```json 代码块，不要添加任何解释、前缀或后缀。\n"
            "3. 这是进入用户审核前的门禁，不是完美主义审稿；只要结果足够清晰、可测试、未明显偏离原始需求，就应设为 pass。\n"
            "4. high 严重度问题必须设为 revise；medium 严重度的结构性问题也必须设为 revise，例如遗漏原始需求核心能力、验收标准无法生成测试、story 明显过大或过小、依赖明显冲突。\n"
            "5. 如果缺少关键前提、无法继续，status 设为 blocked。\n"
            "6. 要同时检查 capability_groups 与 story_units 的边界是否一致。\n"
            "7. 要检查每个 story_unit 是否真的是 user story，而不是模块名、页面名或纯技术任务名。\n"
            "8. low 严重度问题，以及不影响测试生成和业务完整性的 medium 措辞、命名、优先级、文案微调建议不得阻塞流程；这类建议可以放入 revision_guidance，但 status 应为 pass。\n"
            "9. issues 要聚焦真正阻塞用户审核或测试生成的问题，不要为了凑数量而制造问题。\n"
            "10. 如果连续轮次已经吸收过上一轮 revision_guidance，不要换一个角度提出新的非阻塞问题来继续要求 revise。\n\n"
            f"输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"输出结构：\n{json.dumps(output_shape, ensure_ascii=False, indent=2)}\n\n"
            "输出完整 json 示例：\n"
            "请严格参考下面示例的 json 层级、字段名、数组/对象位置与字符串类型；示例仅用于格式参考，不要照抄内容。\n"
            f"{json.dumps(self.json_example, ensure_ascii=False, indent=2)}"
        )
