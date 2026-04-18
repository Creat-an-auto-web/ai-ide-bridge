from __future__ import annotations

import json

from .models import RequirementAnalysisInput


class RequirementAnalysisPromptBuilder:
    def build_system_prompt(self) -> str:
        return (
            "你是 RequirementAnalysisAgent。"
            "你的任务是把原始需求整理成结构化 RequirementSpec 和 StoryUnit 列表。"
            "输出必须是合法 JSON 对象，不要输出 markdown，不要解释。"
            "每个 StoryUnit 必须可测试、可排序、可实现。"
        )

    def build_user_prompt(self, analysis_input: RequirementAnalysisInput) -> str:
        payload = {
            "task_id": analysis_input.task_id,
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
            "execution_constraints": {
                "disallow_new_dependencies": analysis_input.execution_constraints.disallow_new_dependencies,
                "preserve_public_api": analysis_input.execution_constraints.preserve_public_api,
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
            "story_units": [
                {
                    "id": "...",
                    "title": "...",
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
            "2. story_units 数量不能超过 max_story_units。\n"
            "3. dependencies 只能引用已有 story id。\n"
            "4. acceptance_criteria 必须可被测试验证。\n\n"
            f"输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"输出结构：\n{json.dumps(output_shape, ensure_ascii=False, indent=2)}"
        )
