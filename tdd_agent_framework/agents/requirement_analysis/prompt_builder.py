from __future__ import annotations

import json

from .models import RequirementAnalysisInput


class RequirementAnalysisPromptBuilder:
    max_open_files = 8
    max_diagnostics = 8
    max_recent_test_failures = 8
    max_revision_focus = 8
    json_example = {
        "requirement_spec": {
            "task_id": "task_001",
            "version": 1,
            "problem_statement": "当前任务列表缺少导出能力，用户无法将筛选结果用于汇报和离线分析。",
            "product_goal": "为任务列表提供稳定的 CSV 导出能力，并补齐权限与失败反馈边界。",
            "scope": ["任务列表导出入口", "CSV 文件生成", "导出失败反馈"],
            "out_of_scope": ["Excel 导出", "任务列表整体改版"],
            "constraints": ["保持现有公共接口不变", "不新增外部依赖"],
            "assumptions": ["当前任务列表已经支持筛选条件"],
            "interfaces_or_contracts": ["导出结果仅覆盖当前筛选条件下的任务记录"],
            "acceptance_criteria": [
                "用户可以对当前筛选结果发起 CSV 导出",
                "导出成功时文件内容与当前筛选条件一致",
                "导出失败时用户可以看到明确反馈",
            ],
            "decomposition_strategy": "按导出主路径、权限约束与失败反馈三个能力方向拆分",
        },
        "capability_groups": [
            {
                "id": "CG1",
                "title": "任务列表导出主流程",
                "goal": "让用户可以完成当前筛选结果的导出",
                "scope": ["任务列表导出入口", "CSV 文件生成"],
                "story_ids": ["S1"],
                "priority": "high",
            }
        ],
        "story_units": [
            {
                "id": "S1",
                "story_kind": "user_outcome",
                "title": "任务列表用户可以导出当前筛选结果用于汇报和离线分析",
                "as_a": "任务列表用户",
                "when_context": "我已经在任务列表中设置好筛选条件并准备导出结果",
                "i_want": "导出当前筛选结果为 CSV 文件",
                "so_that": "我可以将当前结果用于汇报和离线分析",
                "narrative": "作为任务列表用户，当我已经在任务列表中设置好筛选条件并准备导出结果时，我希望导出当前筛选结果为 CSV 文件，从而我可以将当前结果用于汇报和离线分析。",
                "actor": "任务列表用户",
                "goal": "导出当前筛选结果为 CSV 文件",
                "business_value": "我可以将当前结果用于汇报和离线分析",
                "business_outcome": "用户能够获得与当前筛选条件一致的导出文件。",
                "scope": ["任务列表导出入口", "CSV 文件生成"],
                "out_of_scope": ["Excel 导出"],
                "acceptance_criteria": [
                    "给定用户已经设置筛选条件，当用户发起导出时，那么系统会生成仅包含当前筛选结果的 CSV 文件",
                    "给定导出成功，当用户下载文件时，那么文件字段顺序符合约定",
                    "给定导出失败，当系统无法生成文件时，那么用户可以看到明确失败反馈",
                ],
                "dependencies": [],
                "priority": "high",
                "risk": "medium",
                "test_focus": ["导出主路径", "筛选条件保留", "失败反馈"],
                "implementation_hints": ["优先复用现有筛选逻辑，避免重复定义导出范围"],
            }
        ],
    }

    def build_system_prompt(self) -> str:
        return (
            "你是 RequirementAnalysisAgent。"
            "你的任务是把原始需求整理成结构化 RequirementSpec 和 StoryUnit 列表。"
            "你只能返回一个标准 json 对象。"
            "不要输出 markdown，不要使用 ```json 代码块，不要添加任何前缀、后缀或解释。"
            "输出必须能被 json.loads 直接解析。"
            "每个 StoryUnit 必须可测试、可排序、可实现，并且必须是完整的 user story。"
        )

    def build_user_prompt(self, analysis_input: RequirementAnalysisInput) -> str:
        previous_analysis_result = (
            analysis_input.previous_analysis_result
            if isinstance(analysis_input.previous_analysis_result, dict)
            else None
        )
        payload = {
            "task_id": analysis_input.task_id,
            "iteration": analysis_input.iteration,
            "analysis_goal": analysis_input.analysis_goal,
            "mode": analysis_input.mode,
            "user_prompt": analysis_input.user_prompt,
            "previous_analysis_result": previous_analysis_result,
            "workspace_summary": {
                "languages": analysis_input.workspace_summary.languages,
                "frameworks": analysis_input.workspace_summary.frameworks,
                "key_modules": analysis_input.workspace_summary.key_modules,
            },
            "active_file": analysis_input.active_file,
            "selection": analysis_input.selection,
            "open_files": analysis_input.open_files[: self.max_open_files],
            "diagnostics": analysis_input.diagnostics[: self.max_diagnostics],
            "recent_test_failures": analysis_input.recent_test_failures[: self.max_recent_test_failures],
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
                "revision_focus": analysis_input.revision_focus[: self.max_revision_focus],
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
                    "narrative": "作为[角色]，当[场景]时，我希望[能力]，从而[业务结果]。",
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
            "1. 只允许返回一个标准 json 对象，且必须能被 json.loads 直接解析。\n"
            "2. 不要输出 markdown，不要使用 ```json 代码块，不要添加任何解释、前缀或后缀。\n"
            "3. 必须先给出 capability_groups，再给出每个 group 内展开的 story_units。\n"
            "4. capability_groups 数量不能超过 max_capability_groups。\n"
            "5. story_units 总数量不能超过 max_story_units。\n"
            "6. capability_groups.story_ids 必须只引用已有 story id。\n"
            "7. dependencies 只能引用已有 story id。\n"
            "8. acceptance_criteria 必须可被测试验证。\n"
            "9. 每个 story_unit 都必须显式提供 story_kind、as_a、when_context、i_want、so_that、narrative、business_outcome，并保持语义一致。\n"
            "10. narrative 必须遵循“作为[角色]，当[场景]时，我希望[能力]，从而[业务结果]。”；如果 so_that 为空，则使用“作为[角色]，当[场景]时，我希望[能力]。”。\n"
            "11. title 必须是具体的业务能力描述，不要只写功能名、模块名、页面名或技术组件名，例如不要写“用户登录”“导出 CSV”“需求分析页面”。\n"
            "12. 一条 story 只能表达一个主要用户目标，不能把多个独立能力揉进同一条。\n"
            "13. 对复杂需求优先做能力域分组，不要一次性平铺出无层次的大量 story。\n"
            "14. 如果输入里提供了 user_feedback，必须显式吸收这些反馈；对 story_feedback 要优先修订对应 story 或将其拆分/改写。\n"
            "15. 如果输入里提供了 global_feedback，必要时同步修正 requirement_spec 的 scope、out_of_scope、constraints 和 acceptance_criteria。\n"
            "16. 不要返回验证器或组合验证器风格的结果；禁止只返回 status、summary、issues、revision_guidance、coverage_assessment 这类审查结论对象。\n"
            "17. 你的输出必须同时包含 requirement_spec、capability_groups、story_units 三个顶层字段，缺一不可。\n\n"
            "18. 当 analysis_goal 为 composition_revision 时，必须以 previous_analysis_result 中已有 story 为基线，围绕 revision_context 和上一轮 composition_verification 做增删改；不要无视上一版结果从零重写。\n"
            "19. 如果上一轮 composition_verification.status 为 revise 或 blocked，应优先修复端到端闭环、缺失能力、story 依赖冲突、重复或割裂的 story。\n"
            "20. 如果上一轮 composition_verification.status 为 pass，则这是组合增强优化：不要推翻已通过闭环，应在保持通过结果稳定的前提下，补强边界场景、跨 story 一致性、验收标准和集成测试可验证性。\n"
            "21. composition_revision 必要时可以新增、合并、拆分或改写 story，但必须保持所有 story 单条仍可测试。\n\n"
            f"输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            "输出最小结构示意：\n"
            f"{json.dumps(output_shape, ensure_ascii=False, separators=(',', ':'))}\n\n"
            "输出完整 json 示例：\n"
            "请严格参考下面示例的 json 层级、字段名、数组/对象位置与字符串类型；示例仅用于格式参考，不要照抄业务内容。\n"
            f"{json.dumps(self.json_example, ensure_ascii=False, indent=2)}"
        )
