from __future__ import annotations

import json
from dataclasses import asdict

from .models import CodeImplementationInput


class CodeImplementationPromptBuilder:
    def build_system_prompt(self) -> str:
        return (
            "你是 CodeImplementationAgent，负责严格按 TDD 基线生成或修复业务实现代码。"
            "测试文件是不可修改的规格：不得输出、删除、弱化或绕过测试文件，也不得在业务代码中检测测试环境后伪造结果。"
            "必须输出完整文件内容和合法 JSON 对象，不要输出 markdown。"
        )

    def build_user_prompt(self, data: CodeImplementationInput) -> str:
        is_repair = bool(data.previous_files and data.execution_result)
        payload = {
            "task_id": data.task_id,
            "mode": "repair_implementation" if is_repair else "initial_implementation",
            "iteration": data.iteration,
            "user_prompt": data.user_prompt,
            "requirement_spec": data.requirement_spec,
            "story_units": data.story_units,
            "test_plan": data.test_plan,
            "test_cases": data.test_cases,
            "immutable_test_files": data.test_files,
            "repository_context": data.repository_context,
            "previous_implementation_files": [asdict(item) for item in data.previous_files],
            "last_execution_result": data.execution_result,
        }
        shape = {
            "implementation_plan": ["实现步骤"],
            "files": [
                {
                    "path": "src/example.py",
                    "language": "python",
                    "purpose": "文件职责",
                    "content": "完整文件内容",
                }
            ],
            "changed_files": ["src/example.py"],
            "rationale": "实现或修复为何满足需求与失败诊断",
            "test_command": ["python", "-m", "pytest", "tests/test_example.py", "-q"],
            "warnings": [],
        }
        repair_rules = (
            "这是修复轮次。结合失败测试、stdout/stderr 和之前的实现定位根因；"
            "files 必须返回修复后全部实现文件的完整快照，不能只返回片段。"
            if is_repair
            else "这是首次实现。先理解现有仓库接口，再以最小且完整的改动满足全部测试。"
        )
        return (
            f"{repair_rules}\n"
            "约束：\n"
            "1. files 只能包含业务/生产实现文件，immutable_test_files 中的路径绝不能出现。\n"
            "2. 每个 content 都必须是可直接写入的完整文件，不得使用省略号。\n"
            "3. 优先复用 repository_context 中的架构、依赖和公开接口。\n"
            "4. 不得新增未声明的外部依赖，不得读取或泄露凭据。\n"
            "5. changed_files 必须与 files 路径集合完全一致。\n"
            "6. test_command 必须是 argv 数组，不得包含 shell 管道、重定向或 &&。\n\n"
            f"输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"输出结构：\n{json.dumps(shape, ensure_ascii=False, indent=2)}"
        )

