from __future__ import annotations

import json

from .models import TestCodeGenerationInput


class TestCodeGenerationPromptBuilder:
    def build_system_prompt(self) -> str:
        return (
            "你是 TestCodeGenerationAgent。"
            "你的任务是根据既有测试计划和测试用例，生成可直接落地为测试文件的测试代码草案。"
            "只生成测试代码，不生成业务实现代码。"
            "输出必须是合法 JSON 对象，不要输出 markdown，不要解释。"
        )

    def build_user_prompt(self, generation_input: TestCodeGenerationInput) -> str:
        payload = {
            "task_id": generation_input.task_id,
            "user_prompt": generation_input.user_prompt,
            "plan": generation_input.plan,
            "story_units": [
                {
                    "id": story.id,
                    "title": story.title,
                    "acceptance_criteria": story.acceptance_criteria,
                    "test_focus": story.test_focus,
                }
                for story in generation_input.story_units
            ],
            "test_plan": generation_input.test_plan,
            "test_cases": [
                {
                    "id": test_case.id,
                    "story_id": test_case.story_id,
                    "title": test_case.title,
                    "level": test_case.level,
                    "category": test_case.category,
                    "purpose": test_case.purpose,
                    "preconditions": test_case.preconditions,
                    "test_input": test_case.test_input,
                    "steps": test_case.steps,
                    "expected_result": test_case.expected_result,
                    "acceptance_criteria_refs": test_case.acceptance_criteria_refs,
                    "priority": test_case.priority,
                    "automatable": test_case.automatable,
                }
                for test_case in generation_input.test_cases
            ],
            "execution_constraints": {
                "max_test_files": generation_input.execution_constraints.max_test_files,
                "prefer_existing_test_stack": generation_input.execution_constraints.prefer_existing_test_stack,
                "include_fixtures": generation_input.execution_constraints.include_fixtures,
                "framework_hint": generation_input.execution_constraints.framework_hint,
            },
        }
        output_shape = {
            "implementation_plan": [
                "按什么顺序把测试用例转成测试代码",
            ],
            "test_files": [
                {
                    "path": "tests/test_registration_flow.py",
                    "language": "python|typescript|javascript",
                    "framework": "pytest|vitest|jest",
                    "purpose": "该文件覆盖哪些测试目标",
                    "related_test_case_ids": ["tc_xxx_001"],
                    "content": "完整测试代码内容",
                }
            ],
            "changed_files": ["tests/test_registration_flow.py"],
            "rationale": "为什么这样拆分文件与测试结构",
            "warnings": ["可选告警"],
        }
        return (
            "请把输入中的测试计划和测试用例转换成测试代码草案。\n"
            "要求：\n"
            "1. 输出必须是 JSON 对象。\n"
            "2. 只生成测试代码，不生成生产实现代码。\n"
            "3. test_files 中的 content 必须是完整测试文件内容，而不是片段。\n"
            "4. related_test_case_ids 必须覆盖输入 test_cases。\n"
            "5. changed_files 必须包含所有 test_files.path。\n"
            "6. 如果 execution_constraints.framework_hint 不为空，优先使用该测试框架。\n"
            "7. 如果没有明确框架提示，选择最合理的测试框架，并在 rationale 里说明。\n\n"
            f"输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"输出结构：\n{json.dumps(output_shape, ensure_ascii=False, indent=2)}"
        )
