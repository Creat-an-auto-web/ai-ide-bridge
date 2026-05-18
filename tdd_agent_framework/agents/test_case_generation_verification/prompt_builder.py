from __future__ import annotations

import json

from .models import TestCaseGenerationVerificationInput


class TestCaseGenerationVerificationPromptBuilder:
    def build_system_prompt(self) -> str:
        return (
            "你是 TestCaseGenerationVerificationAgent。"
            "你必须独立检查测试用例生成结果是否已经完成前端提供的 plan。"
            "输出必须是合法 json 对象，不要输出 markdown，不要解释。"
            "只有在 plan 中的关键覆盖点都已被测试计划和测试用例覆盖时，才能判定为 complete。"
        )

    def build_user_prompt(
        self,
        verification_input: TestCaseGenerationVerificationInput,
    ) -> str:
        generation_input = verification_input.generation_input
        generation_result = verification_input.generation_result
        payload = {
            "task_id": generation_input.task_id,
            "plan": verification_input.plan,
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
            "generated_result": {
                "test_plan": generation_result.test_plan,
                "test_cases": [
                    {
                        "id": case.id,
                        "story_id": case.story_id,
                        "title": case.title,
                        "category": case.category,
                        "purpose": case.purpose,
                        "steps": case.steps,
                        "expected_result": case.expected_result,
                        "acceptance_criteria_refs": case.acceptance_criteria_refs,
                    }
                    for case in generation_result.test_cases
                ],
                "quality_checks": {
                    "has_inputs_and_expected_results": (
                        generation_result.quality_checks.has_inputs_and_expected_results
                    ),
                    "covers_all_stories": generation_result.quality_checks.covers_all_stories,
                    "has_boundary_cases": generation_result.quality_checks.has_boundary_cases,
                    "has_negative_cases": generation_result.quality_checks.has_negative_cases,
                    "case_count_within_limit": (
                        generation_result.quality_checks.case_count_within_limit
                    ),
                },
                "warnings": generation_result.warnings,
            },
        }
        output_shape = {
            "status": "complete|incomplete|blocked",
            "summary": "一句话总结完成度判断",
            "missing_items": ["未覆盖的计划点或缺失项"],
            "notes": ["补充说明，可为空"],
        }
        return (
            "请检查下面的测试用例生成结果是否完成了前端提供的 plan。\n"
            "要求：\n"
            "1. 输出必须是 json 对象。\n"
            "2. 如果 plan 中的关键覆盖点都已落到 test_plan 或 test_cases 中，status 设为 complete。\n"
            "3. 如果仍缺少计划中的覆盖点，status 设为 incomplete，并把缺失项写入 missing_items。\n"
            "4. 如果 plan 本身缺少关键上下文、无法判断，status 设为 blocked。\n"
            "5. missing_items 与 notes 要聚焦真正缺失内容，不要泛泛而谈。\n\n"
            f"输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"输出结构：\n{json.dumps(output_shape, ensure_ascii=False, indent=2)}"
        )
