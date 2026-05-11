from __future__ import annotations

import json

from .models import RequirementAnalysisInput


class RequirementAnalysisPromptBuilder:
    def build_system_prompt(self) -> str:
        return (
            "你是 RequirementAnalysisAgent。"
            "你的任务是把原始需求整理成结构化 RequirementSpec 和 StoryUnit 列表。"
            "输出必须是合法 JSON 对象，不要输出 markdown，不要解释。"
            "每个 StoryUnit 必须可测试、可排序、可实现，并且必须是完整的 user story。"
        )

    def build_user_prompt(self, analysis_input: RequirementAnalysisInput) -> str:
        payload = {
            "task_id": analysis_input.task_id,
            "iteration": analysis_input.iteration,
            "mode": analysis_input.mode,
            "user_prompt": analysis_input.user_prompt,
            "repo_root": analysis_input.repo_root,
            "workspace_summary": {
                "languages": analysis_input.workspace_summary.languages,
                "frameworks": analysis_input.workspace_summary.frameworks,
                "key_modules": analysis_input.workspace_summary.key_modules,
            },
            "active_file": analysis_input.active_file,
            "selection": analysis_input.selection,
            "open_files": analysis_input.open_files,
            "diagnostics": analysis_input.diagnostics,
            "recent_test_failures": analysis_input.recent_test_failures,
            "git_diff_summary": analysis_input.git_diff_summary,
            "user_feedback": {
                "global_feedback": (
                    {
                        "feedback_id": analysis_input.global_feedback.feedback_id,
                        "kind": analysis_input.global_feedback.kind,
                        "feedback_type": analysis_input.global_feedback.feedback_type,
                        "feedback_text": analysis_input.global_feedback.feedback_text,
                        "expected_action": analysis_input.global_feedback.expected_action,
                        "applies_to": {
                            "capability_group_ids": analysis_input.global_feedback.applies_to.capability_group_ids,
                            "story_ids": analysis_input.global_feedback.applies_to.story_ids,
                        },
                    }
                    if analysis_input.global_feedback is not None
                    else None
                ),
                "story_feedback": (
                    {
                        "feedback_id": analysis_input.story_feedback.feedback_id,
                        "kind": analysis_input.story_feedback.kind,
                        "story_id": analysis_input.story_feedback.story_id,
                        "feedback_type": analysis_input.story_feedback.feedback_type,
                        "feedback_text": analysis_input.story_feedback.feedback_text,
                        "expected_action": analysis_input.story_feedback.expected_action,
                    }
                    if analysis_input.story_feedback is not None
                    else None
                ),
            },
            "revision_context": {
                "previous_verification_summary": analysis_input.previous_verification_summary,
                "revision_focus": analysis_input.revision_focus,
            },
            "execution_constraints": {
                "disallow_new_dependencies": analysis_input.execution_constraints.disallow_new_dependencies,
                "preserve_public_api": analysis_input.execution_constraints.preserve_public_api,
                "max_capability_groups": analysis_input.execution_constraints.max_capability_groups,
                "max_story_units": analysis_input.execution_constraints.max_story_units,
            },
        }
        output_shape = {
            "requirement_spec": {
                "task_id": analysis_input.task_id,
                "version": 1,
                "problem_statement": "...",
                "product_goal": "...",
                "scope": ["..."],
                "out_of_scope": ["..."],
                "constraints": ["..."],
                "assumptions": ["..."],
                "interfaces_or_contracts": ["..."],
                "acceptance_criteria": ["..."],
                "decomposition_strategy": "...",
            },
            "capability_groups": [
                {
                    "id": "...",
                    "title": "...",
                    "goal": "...",
                    "scope": ["..."],
                    "story_ids": ["..."],
                    "priority": "low|medium|high",
                }
            ],
            "story_units": [
                {
                    "id": "...",
                    "story_kind": "user_outcome|admin_outcome|operator_outcome|compliance_guard|system_feedback",
                    "title": "...",
                    "as_a": "...",
                    "when_context": "...",
                    "i_want": "...",
                    "so_that": "...",
                    "narrative": "As a ..., when ..., I want ..., so that ...",
                    "actor": "...",
                    "goal": "...",
                    "business_value": "...",
                    "business_outcome": "...",
                    "scope": ["..."],
                    "out_of_scope": ["..."],
                    "acceptance_criteria": ["..."],
                    "dependencies": ["..."],
                    "priority": "low|medium|high",
                    "risk": "low|medium|high",
                    "test_focus": ["..."],
                    "implementation_hints": ["..."],
                }
            ],
        }
        return (
            "请基于下面输入生成结果。\n"
            "要求：\n"
            "1. 输出必须是 JSON 对象。\n"
            "2. 必须先给出 capability_groups，再给出每个 group 内展开的 story_units。\n"
            "3. capability_groups 数量不能超过 max_capability_groups。\n"
            "4. story_units 总数量不能超过 max_story_units。\n"
            "5. capability_groups.story_ids 必须只引用已有 story id。\n"
            "6. dependencies 只能引用已有 story id。\n"
            "7. acceptance_criteria 必须可被测试验证。\n"
            "8. 每个 story_unit 都必须显式提供 story_kind、as_a、when_context、i_want、so_that、narrative、business_outcome，并保持语义一致。\n"
            "9. narrative 必须遵循 As a [role], when [context], I want [capability], so that [business outcome].\n"
            "10. title 必须是具体的业务能力描述，不要只写功能名、模块名、页面名或技术组件名，例如不要写“用户登录”“导出 CSV”“需求分析页面”。\n"
            "11. 一条 story 只能表达一个主要用户目标，不能把多个独立能力揉进同一条。\n"
            "12. 对复杂需求优先做能力域分组，不要一次性平铺出无层次的大量 story。\n"
            "13. 如果输入里提供了 user_feedback，必须显式吸收这些反馈；对 story_feedback 要优先修订对应 story 或将其拆分/改写。\n"
            "14. 如果输入里提供了 global_feedback，必要时同步修正 requirement_spec 的 scope、out_of_scope、constraints 和 acceptance_criteria。\n\n"
            f"输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"输出结构：\n{json.dumps(output_shape, ensure_ascii=False, indent=2)}"
        )
