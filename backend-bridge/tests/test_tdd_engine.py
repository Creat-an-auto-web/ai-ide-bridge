from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

from app.models.task import CreateTaskRequest
from app.services.event_bus import EventBus
from app.services.task_service import TaskService
from app.services.tdd_engine import TddEngine
from tdd_agent_framework.agents.code_implementation import (
    CodeImplementationQualityChecks,
    CodeImplementationResult,
    GeneratedCodeFile,
)


@dataclass
class RequirementSpecStub:
    task_id: str = "task"
    acceptance_criteria: list[str] = field(default_factory=lambda: ["add(1, 2) returns 3"])
    problem_statement: str = "Implement addition"


@dataclass
class StoryStub:
    id: str = "story_add"
    title: str = "Add numbers"
    acceptance_criteria: list[str] = field(default_factory=lambda: ["returns the sum"])


@dataclass
class GraphStub:
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)


@dataclass
class AnalysisStub:
    status: str = "paused_content_verified"
    package_id: str = "pkg_1"
    requirement_spec: RequirementSpecStub = field(default_factory=RequirementSpecStub)
    story_units: list[StoryStub] = field(default_factory=lambda: [StoryStub()])
    story_dependency_graph: GraphStub = field(default_factory=GraphStub)
    story_relationships: list = field(default_factory=list)


@dataclass
class TestCaseStub:
    id: str = "tc_add"
    story_id: str = "story_add"
    title: str = "adds two numbers"


@dataclass
class TestCasesStub:
    test_plan: str = "test addition"
    test_cases: list[TestCaseStub] = field(default_factory=lambda: [TestCaseStub()])
    completion_check: object | None = None


@dataclass
class TestFileStub:
    path: str = "tests/test_calc.py"
    language: str = "python"
    framework: str = "pytest"
    purpose: str = "addition regression"
    related_test_case_ids: list[str] = field(default_factory=lambda: ["tc_add"])
    content: str = "from src.calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"


@dataclass
class TestCodeStub:
    test_files: list[TestFileStub] = field(default_factory=lambda: [TestFileStub()])


class StaticOrchestrator:
    def __init__(self, result) -> None:
        self.result = result

    async def run(self, *_args):
        return self.result


class ImplementationOrchestratorStub:
    def __init__(self) -> None:
        self.inputs = []

    async def run(self, _settings, data, _progress=None):
        self.inputs.append(data)
        content = (
            "def add(a, b):\n    return a - b\n"
            if len(self.inputs) == 1
            else "def add(a, b):\n    return a + b\n"
        )
        return CodeImplementationResult(
            implementation_plan=["implement addition"],
            files=[GeneratedCodeFile("src/calc.py", "python", "addition", content)],
            changed_files=["src/calc.py"],
            rationale="implementation",
            test_command=["python", "-m", "pytest", "tests/test_calc.py", "-q"],
            warnings=[],
            quality_checks=CodeImplementationQualityChecks(True, True, True, True),
        )


class SandboxStub:
    def __init__(self) -> None:
        self.requests = []

    async def stream_run(self, payload, callback) -> None:
        self.requests.append(payload)
        iteration = len(self.requests)
        status = "failed" if iteration == 1 else "passed"
        failed = 1 if status == "failed" else 0
        passed = 0 if status == "failed" else 1
        await callback(
            {
                "type": "result",
                "data": {
                    "status": status,
                    "execution": {
                        "command": {"argv": payload.command.argv, "cwd": "."},
                        "exit_code": failed,
                        "termination_reason": "test_failure" if failed else "test_passed",
                    },
                    "test_summary": {
                        "framework": "pytest",
                        "passed": passed,
                        "failed": failed,
                        "errors": 0,
                        "skipped": 0,
                        "failed_tests": ["tests/test_calc.py::test_add"] if failed else [],
                    },
                    "outputs": {
                        "stdout": "1 failed" if failed else "1 passed",
                        "stderr": "expected 3, got -1" if failed else "",
                    },
                    "failure": {"summary": "expected 3, got -1"} if failed else None,
                },
            }
        )


class TddEngineTest(unittest.IsolatedAsyncioTestCase):
    def test_test_plan_marks_unrelated_coverage_as_not_applicable(self) -> None:
        plan = TddEngine._test_plan_from_analysis(AnalysisStub())

        self.assertIn("仅当需求或仓库上下文确实存在", plan)
        self.assertIn("不能视为缺失", plan)

    async def test_runs_failure_repair_success_and_returns_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir()
            (root / "src/calc.py").write_text("def add(a, b):\n    pass\n", encoding="utf-8")
            event_bus = EventBus()
            task_service = TaskService(event_bus)
            implementation = ImplementationOrchestratorStub()
            sandbox = SandboxStub()
            engine = TddEngine(
                task_service,
                event_bus,
                requirement_orchestrator=StaticOrchestrator(AnalysisStub()),
                test_case_orchestrator=StaticOrchestrator(TestCasesStub()),
                test_code_orchestrator=StaticOrchestrator(TestCodeStub()),
                implementation_orchestrator=implementation,
                sandbox_service=sandbox,
                max_repair_iterations=2,
            )
            task_service.set_engine(engine)
            request = CreateTaskRequest.model_validate(
                {
                    "mode": "repo_chat",
                    "userPrompt": "implement add",
                    "repo": {"rootPath": str(root)},
                    "context": {"openFiles": ["src/calc.py"]},
                    "policy": {"workspaceMode": "local", "network": "allow"},
                }
            )

            with patch.dict(
                "os.environ",
                {
                    "GLM_API_KEY": "test-key",
                    "GLM_MODEL": "test-model",
                    "GLM_API_BASE": "https://example.invalid/v1",
                },
                clear=False,
            ):
                task = await task_service.create_task(request)
                await asyncio.wait_for(task_service.background_tasks[task.taskId], timeout=2)

            self.assertEqual(task_service.get_task(task.taskId).status, "completed")
            self.assertEqual(len(sandbox.requests), 2)
            self.assertEqual(len(implementation.inputs), 2)
            self.assertEqual(
                implementation.inputs[1].previous_files[0].content,
                "def add(a, b):\n    return a - b\n",
            )
            for sandbox_request in sandbox.requests:
                self.assertEqual(sandbox_request.test_files[0].path, "tests/test_calc.py")
                self.assertEqual(sandbox_request.workspace_files[0].path, "src/calc.py")
            events = event_bus.get_history(task.taskId)
            self.assertEqual([event.type for event in events].count("task.test.result"), 2)
            patch_event = next(event for event in events if event.type == "task.patch")
            paths = {item["path"] for item in patch_event.payload["files"]}
            self.assertEqual(paths, {"src/calc.py", "tests/test_calc.py"})
            final = next(event for event in events if event.type == "task.final")
            self.assertEqual(final.payload["outcome"], "completed")
            self.assertEqual(len(final.payload["artifacts"]["attempts"]), 2)
            workflow_artifacts = final.payload["artifacts"]["workflowArtifacts"]
            self.assertEqual(
                workflow_artifacts["completedStages"],
                [
                    "requirement_analysis",
                    "test_case_generation",
                    "code_implementation",
                ],
            )
            artifact_files = {
                item["relativePath"]: item["content"]
                for item in workflow_artifacts["files"]
            }
            self.assertIn(
                "01-requirement-analysis/requirement-analysis.json",
                artifact_files,
            )
            self.assertIn("02-test-cases/test-cases.json", artifact_files)
            self.assertIn("02-test-cases/test-plan.md", artifact_files)
            self.assertIn("02-test-cases/test-code-manifest.json", artifact_files)
            self.assertIn("02-test-cases/test-code/tests/test_calc.py", artifact_files)
            self.assertIn("03-implementation/manifest.json", artifact_files)
            self.assertIn("03-implementation/files/src/calc.py", artifact_files)
            self.assertIn("test_add", artifact_files["02-test-cases/test-code/tests/test_calc.py"])
