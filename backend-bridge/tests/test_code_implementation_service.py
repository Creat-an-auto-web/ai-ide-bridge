from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.models.code_implementation import CodeImplementationRunRequest
from app.services.code_implementation_service import CodeImplementationBackendService
from tdd_agent_framework.agents.code_implementation import (
    CodeImplementationQualityChecks,
    CodeImplementationResult,
    GeneratedCodeFile,
)


class StubOrchestrator:
    def __init__(self, result: CodeImplementationResult) -> None:
        self.result = result
        self.called_with = None

    async def run(self, settings, implementation_input):
        self.called_with = (settings, implementation_input)
        return self.result


class CodeImplementationBackendServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_collects_workspace_context_and_returns_production_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir()
            (root / "src" / "calculator.py").write_text("def add(a, b):\n    pass\n", encoding="utf-8")
            payload = CodeImplementationRunRequest.model_validate({
                "settings": {
                    "provider_name": "openai",
                    "model": "gpt-test",
                    "api_base": "https://api.openai.com/v1",
                    "api_key": "test-key",
                },
                "input": {
                    "task_id": "task_001",
                    "repo_root": str(root),
                    "user_prompt": "实现加法",
                    "requirement_spec": {"acceptance_criteria": ["返回两数之和"]},
                    "story_units": [],
                    "test_plan": "测试加法",
                    "test_cases": [],
                    "test_files": [{"path": "tests/test_calculator.py", "content": "assert add(1, 2) == 3"}],
                },
            })
            orchestrator = StubOrchestrator(CodeImplementationResult(
                implementation_plan=["实现 add"],
                files=[GeneratedCodeFile("src/calculator.py", "python", "加法", "def add(a, b):\n    return a + b\n")],
                changed_files=["src/calculator.py"],
                rationale="满足测试基线",
                test_command=["python", "-m", "pytest", "tests/test_calculator.py"],
                warnings=[],
                quality_checks=CodeImplementationQualityChecks(True, True, True, True),
            ))

            result = await CodeImplementationBackendService(orchestrator).run(payload)

            self.assertEqual(result["changed_files"], ["src/calculator.py"])
            self.assertIn("src/calculator.py", orchestrator.called_with[1].repository_context)
            self.assertNotIn("repo_root", orchestrator.called_with[1].__dict__)

