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
                    "title": "...",
                    "as_a": "...",
                    "i_want": "...",
                    "so_that": "...",
                    "narrative": "As a ..., I want ..., so that ...",
                    "actor": "...",
                    "goal": "...",
                    "business_value": "...",
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
            "8. 每个 story_unit 都必须显式提供 as_a、i_want、so_that、narrative，并保持四者语义一致。\n"
            "9. title 必须是具体的用户能力或业务结果，不要只写模块名、页面名或技术组件名。\n"
            "10. 对复杂需求优先做能力域分组，不要一次性平铺出无层次的大量 story。\n\n"
            f"输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"输出结构：\n{json.dumps(output_shape, ensure_ascii=False, indent=2)}"
        )
