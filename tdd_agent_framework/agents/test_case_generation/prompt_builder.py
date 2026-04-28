from __future__ import annotations

import json

from .models import TestCaseGenerationInput


class TestCaseGenerationPromptBuilder:
    def build_system_prompt(self) -> str:
        return (
            "你是 TestCaseGenerationAgent。"
            "你的任务是基于标准化 User Story 生成全面、可执行、可校验的测试用例。"
            "输出必须是合法 JSON 对象，不要输出 markdown，不要解释。"
            "每条测试用例必须包含测试输入和预期结果。"
        )

    def build_user_prompt(self, generation_input: TestCaseGenerationInput) -> str:
        payload = {
            "task_id": generation_input.task_id,
            "user_prompt": generation_input.user_prompt,
            "story_units": [
                {
                    "id": story.id,
                    "title": story.title,
                    "acceptance_criteria": story.acceptance_criteria,
                    "priority": story.priority,
                    "risk": story.risk,
                    "test_focus": story.test_focus,
                }
                for story in generation_input.story_units
            ],
            "execution_constraints": {
                "max_test_cases_per_story": generation_input.execution_constraints.max_test_cases_per_story,
                "require_boundary_cases": generation_input.execution_constraints.require_boundary_cases,
                "require_negative_cases": generation_input.execution_constraints.require_negative_cases,
            },
        }
        output_shape = {
            "test_plan": "覆盖策略摘要",
            "test_cases": [
                {
                    "id": "tc_story_xxx_001",
                    "story_id": "story_xxx",
                    "title": "标题",
                    "level": "unit|integration|e2e",
                    "category": "positive|negative|boundary|regression",
                    "purpose": "该用例验证什么行为",
                    "preconditions": ["..."],
                    "test_input": {"field": "value"},
                    "steps": ["step1", "step2"],
                    "expected_result": "可验证结果",
                    "acceptance_criteria_refs": ["原 story 的 AC 片段"],
                    "priority": "low|medium|high",
                    "automatable": True,
                }
            ],
            "warnings": ["可选告警"],
        }
        return (
            "请基于输入生成测试用例。\n"
            "要求：\n"
            "1. 输出必须是 JSON 对象。\n"
            "2. 每个 story 至少 1 条测试用例。\n"
            "3. 每条测试用例必须有 test_input 和 expected_result。\n"
            "4. 单个 story 的测试用例数量不能超过 max_test_cases_per_story。\n"
            "5. 如果 require_boundary_cases=true，至少有 1 条 boundary 用例。\n"
            "6. 如果 require_negative_cases=true，至少有 1 条 negative 用例。\n\n"
            f"输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"输出结构：\n{json.dumps(output_shape, ensure_ascii=False, indent=2)}"
        )
