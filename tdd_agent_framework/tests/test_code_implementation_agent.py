from __future__ import annotations

import unittest

from tdd_agent_framework.agents.code_implementation import (
    CodeImplementationAgent,
    CodeImplementationInput,
)
from tdd_agent_framework.core import AgentRunContext, ModelTarget, ProviderResponse


class StaticProvider:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def generate(self, request):
        return ProviderResponse(raw_text="", parsed_json=self.payload)


def make_input() -> CodeImplementationInput:
    return CodeImplementationInput(
        task_id="task_1",
        user_prompt="实现加法函数",
        requirement_spec={"acceptance_criteria": ["返回两数之和"]},
        story_units=[],
        test_plan="测试正常值与边界值",
        test_cases=[],
        test_files=[{"path": "tests/test_calc.py", "content": "assert add(1, 2) == 3"}],
        repository_context={"src/calc.py": "def add(a, b):\n    pass\n"},
    )


class CodeImplementationAgentTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_complete_production_files(self) -> None:
        agent = CodeImplementationAgent(
            StaticProvider(
                {
                    "implementation_plan": ["实现加法"],
                    "files": [
                        {
                            "path": "src/calc.py",
                            "language": "python",
                            "purpose": "加法实现",
                            "content": "def add(a, b):\n    return a + b\n",
                        }
                    ],
                    "changed_files": ["src/calc.py"],
                    "rationale": "满足固定测试基线",
                    "test_command": ["python", "-m", "pytest", "tests/test_calc.py", "-q"],
                    "warnings": [],
                }
            ),
            ModelTarget("test", "test"),
        )

        result = await agent.run(make_input(), AgentRunContext(task_id="task_1"))

        self.assertEqual(result.files[0].path, "src/calc.py")
        self.assertTrue(result.quality_checks.keeps_test_baseline_immutable)
        self.assertTrue(result.quality_checks.changed_files_match_generated_files)

    async def test_rejects_attempt_to_modify_immutable_tests(self) -> None:
        agent = CodeImplementationAgent(
            StaticProvider(
                {
                    "implementation_plan": ["修改测试"],
                    "files": [
                        {
                            "path": "tests/test_calc.py",
                            "language": "python",
                            "purpose": "弱化断言",
                            "content": "assert True\n",
                        }
                    ],
                    "changed_files": ["tests/test_calc.py"],
                    "rationale": "错误尝试",
                    "test_command": [],
                    "warnings": [],
                }
            ),
            ModelTarget("test", "test"),
        )

        with self.assertRaisesRegex(ValueError, "must not modify immutable test files"):
            await agent.run(make_input(), AgentRunContext(task_id="task_1"))

    async def test_rejects_dot_path_alias_for_immutable_test(self) -> None:
        agent = CodeImplementationAgent(
            StaticProvider(
                {
                    "implementation_plan": ["绕过测试路径"],
                    "files": [
                        {
                            "path": "./tests/test_calc.py",
                            "language": "python",
                            "purpose": "弱化断言",
                            "content": "assert True\n",
                        }
                    ],
                    "changed_files": ["tests/test_calc.py"],
                    "rationale": "错误尝试",
                    "test_command": [],
                    "warnings": [],
                }
            ),
            ModelTarget("test", "test"),
        )

        with self.assertRaisesRegex(ValueError, "must not modify immutable test files"):
            await agent.run(make_input(), AgentRunContext(task_id="task_1"))
