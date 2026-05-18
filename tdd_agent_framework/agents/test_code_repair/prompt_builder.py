from __future__ import annotations

import json

from .models import TestCodeRepairInput


class TestCodeRepairPromptBuilder:
    def build_system_prompt(self) -> str:
        return (
            "你是 TestCodeRepairAgent。"
            "你的任务是根据失败的测试执行结果修复测试代码。"
            "只允许修改测试文件，不允许生成业务实现代码。"
            "输出必须是合法 JSON 对象，不要输出 markdown，不要解释。"
        )

    def build_user_prompt(self, repair_input: TestCodeRepairInput) -> str:
        payload = {
            "task_id": repair_input.task_id,
            "user_prompt": repair_input.user_prompt,
            "plan": repair_input.plan,
            "test_plan": repair_input.test_plan,
            "test_cases": [
                {
                    "id": test_case.id,
                    "title": test_case.title,
                    "level": test_case.level,
                    "category": test_case.category,
                    "expected_result": test_case.expected_result,
                }
                for test_case in repair_input.test_cases
            ],
            "current_test_files": [
                {
                    "path": test_file.path,
                    "framework": test_file.framework,
                    "purpose": test_file.purpose,
                    "related_test_case_ids": test_file.related_test_case_ids,
                    "content": test_file.content,
                }
                for test_file in repair_input.test_files
            ],
            "execution_result": {
                "command": repair_input.execution_result.command,
                "exit_code": repair_input.execution_result.exit_code,
                "failed_tests": repair_input.execution_result.failed_tests,
                "stdout": repair_input.execution_result.stdout,
                "stderr": repair_input.execution_result.stderr,
                "workspace_diff": repair_input.execution_result.workspace_diff,
            },
        }
        output_shape = {
            "repair_plan": [
                "先修什么，再修什么",
            ],
            "test_files": [
                {
                    "path": "tests/test_registration_flow.py",
                    "language": "python|typescript|javascript",
                    "framework": "pytest|vitest|jest",
                    "purpose": "该文件覆盖哪些失败点",
                    "related_test_case_ids": ["tc_registration_success"],
                    "content": "修复后的完整测试文件内容",
                }
            ],
            "changed_files": ["tests/test_registration_flow.py"],
            "reasoning_summary": "说明本轮修复依据了哪些失败信息",
            "warnings": ["可选告警"],
        }
        return (
            "请根据失败的测试执行结果修复测试代码。\n"
            "要求：\n"
            "1. 输出必须是 JSON 对象。\n"
            "2. 只允许修改输入中的测试文件，不生成业务实现代码。\n"
            "3. 返回的 test_files 必须是修复后的完整文件内容。\n"
            "4. changed_files 必须与 test_files.path 对齐。\n"
            "5. 修复目标应优先围绕语法错误、导入错误、fixture 错误、断言错误和测试命令不兼容问题。\n\n"
            f"输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"输出结构：\n{json.dumps(output_shape, ensure_ascii=False, indent=2)}"
        )
