from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from app.models.common import gen_id
from app.models.sandbox_execution import SandboxExecutionRunRequest
from app.services.event_bus import EventBus
from app.services.sandbox_execution_service import SandboxExecutionBackendService
from app.services.task_service import TaskService

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tdd_agent_framework.agents.code_implementation import (
    CodeImplementationAgentSettings,
    CodeImplementationInput,
    GeneratedCodeFile,
)
from tdd_agent_framework.agents.requirement_analysis import (
    RequirementAnalysisAgentSettings,
    RequirementAnalysisInput,
)
from tdd_agent_framework.agents.test_case_generation import (
    TestCaseGenerationAgentSettings,
    TestCaseGenerationConstraints,
    TestCaseGenerationInput,
)
from tdd_agent_framework.agents.test_code_generation import (
    TestCodeGenerationAgentSettings,
    TestCodeGenerationConstraints,
    TestCodeGenerationInput,
)
from tdd_agent_framework.core import RunProgressEvent
from tdd_agent_framework.orchestrators import (
    CodeImplementationOrchestrator,
    RequirementAnalysisOrchestrator,
    TestCaseGenerationOrchestrator,
    TestCodeGenerationOrchestrator,
)


logger = logging.getLogger(__name__)


class TddPipelineError(RuntimeError):
    def __init__(self, message: str, *, code: str = "INTERNAL_ERROR") -> None:
        super().__init__(message)
        self.code = code


class WorkspaceContextCollector:
    """Build a bounded, secret-aware source snapshot for implementation prompts."""

    ignored_dirs = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "coverage",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".idea",
        ".vscode",
        "upstream",
    }
    supported_suffixes = {
        ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
        ".java", ".go", ".rs", ".c", ".cc", ".cpp", ".h", ".hpp",
        ".json", ".toml", ".yaml", ".yml", ".md", ".html", ".css",
        ".scss", ".sql", ".sh",
    }
    manifest_names = {
        "package.json", "pyproject.toml", "requirements.txt", "setup.cfg",
        "pytest.ini", "tox.ini", "Cargo.toml", "go.mod", "pom.xml",
        "build.gradle", "Makefile", "README.md",
    }
    sensitive_names = {".env", ".env.local", ".npmrc", ".pypirc", "credentials.json"}

    def __init__(
        self,
        *,
        max_files: int = 48,
        max_total_chars: int = 120_000,
        max_file_chars: int = 12_000,
        max_tree_entries: int = 400,
    ) -> None:
        self.max_files = max_files
        self.max_total_chars = max_total_chars
        self.max_file_chars = max_file_chars
        self.max_tree_entries = max_tree_entries

    def collect(self, root: Path, preferred_paths: list[str]) -> dict[str, str]:
        candidates: list[Path] = []
        seen: set[Path] = set()

        def add(path: Path) -> None:
            try:
                resolved = path.resolve()
                resolved.relative_to(root)
            except (OSError, ValueError):
                return
            if resolved in seen or not resolved.is_file() or self._is_sensitive(resolved):
                return
            if resolved.name not in self.manifest_names and resolved.suffix.lower() not in self.supported_suffixes:
                return
            seen.add(resolved)
            candidates.append(resolved)

        for value in preferred_paths:
            if not value:
                continue
            candidate = Path(value)
            add(candidate if candidate.is_absolute() else root / candidate)

        discovered: list[Path] = []
        tree_entries: list[str] = []
        for current_dir, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            current = Path(current_dir)
            dirnames[:] = [
                name
                for name in dirnames
                if name not in self.ignored_dirs and not (current / name).is_symlink()
            ]
            for name in dirnames:
                if len(tree_entries) < self.max_tree_entries:
                    tree_entries.append((current / name).relative_to(root).as_posix() + "/")
            for name in filenames:
                path = current / name
                if path.is_symlink():
                    continue
                if len(tree_entries) < self.max_tree_entries:
                    tree_entries.append(path.relative_to(root).as_posix())
                discovered.append(path)

        discovered.sort(
            key=lambda item: (
                0 if item.name in self.manifest_names else 1,
                len(item.relative_to(root).parts),
                item.relative_to(root).as_posix(),
            )
        )
        for path in discovered:
            add(path)
            if len(candidates) >= self.max_files:
                break

        result = {"__repository_tree__": "\n".join(tree_entries)}
        remaining = self.max_total_chars
        for path in candidates[: self.max_files]:
            if remaining <= 0:
                break
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            limit = min(self.max_file_chars, remaining)
            rendered = content[:limit]
            if len(content) > limit:
                rendered += "\n[truncated]"
            result[path.relative_to(root).as_posix()] = rendered
            remaining -= len(rendered)
        return result

    def _is_sensitive(self, path: Path) -> bool:
        lowered = path.name.lower()
        return (
            lowered in self.sensitive_names
            or lowered.endswith((".pem", ".key", ".p12", ".pfx", ".crt"))
            or "secret" in lowered
        )


class TddEngine:
    """End-to-end requirement -> tests -> implementation -> repair loop."""

    plan_steps = [
        "分析用户需求与仓库上下文",
        "生成覆盖正常、边界和异常路径的测试用例",
        "生成不可变的可执行测试代码",
        "根据需求和测试生成业务实现代码",
        "在隔离沙箱运行测试并根据失败修复实现",
        "向前端返回最终代码补丁和测试结果",
    ]

    def __init__(
        self,
        task_service: TaskService,
        event_bus: EventBus,
        *,
        requirement_orchestrator: Any | None = None,
        test_case_orchestrator: Any | None = None,
        test_code_orchestrator: Any | None = None,
        implementation_orchestrator: Any | None = None,
        sandbox_service: SandboxExecutionBackendService | None = None,
        context_collector: WorkspaceContextCollector | None = None,
        max_repair_iterations: int | None = None,
    ) -> None:
        self.task_service = task_service
        self.event_bus = event_bus
        self.requirement_orchestrator = requirement_orchestrator or RequirementAnalysisOrchestrator()
        self.test_case_orchestrator = test_case_orchestrator or TestCaseGenerationOrchestrator()
        self.test_code_orchestrator = test_code_orchestrator or TestCodeGenerationOrchestrator()
        self.implementation_orchestrator = implementation_orchestrator or CodeImplementationOrchestrator()
        self.sandbox_service = sandbox_service or SandboxExecutionBackendService()
        self.context_collector = context_collector or WorkspaceContextCollector()
        configured_iterations = (
            int(os.getenv("TDD_MAX_REPAIR_ITERATIONS", "3"))
            if max_repair_iterations is None
            else max_repair_iterations
        )
        self.max_repair_iterations = max(0, configured_iterations)

    async def run_task(self, task_id: str) -> None:
        try:
            await self._run_pipeline(task_id)
        except asyncio.CancelledError:
            await self.task_service.set_status(task_id, "cancelled", "Task cancelled")
            await self.event_bus.publish(
                task_id,
                "task.final",
                {"outcome": "cancelled", "summary": "Task cancelled by user"},
            )
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("TDD pipeline failed for task %s", task_id)
            code = exc.code if isinstance(exc, TddPipelineError) else "INTERNAL_ERROR"
            await self.task_service.set_status(task_id, "failed", str(exc))
            await self.event_bus.publish(
                task_id,
                "task.error",
                {"code": code, "message": str(exc), "retryable": False},
            )
            await self.event_bus.publish(
                task_id,
                "task.final",
                {"outcome": "failed", "summary": f"TDD pipeline failed: {exc}"},
            )

    async def _run_pipeline(self, task_id: str) -> None:
        req = self.task_service.get_request(task_id)
        repo_root = Path(req.repo.rootPath).expanduser().resolve()
        if not repo_root.is_dir():
            raise TddPipelineError(
                f"Workspace does not exist: {repo_root}",
                code="WORKSPACE_ERROR",
            )
        settings = self._load_model_settings()

        await self.task_service.set_status(task_id, "planning", "正在生成 TDD 执行计划")
        await self.event_bus.publish(task_id, "task.plan", {"steps": self.plan_steps})

        await self._log(task_id, "[1/6] 正在分析需求与仓库上下文……\n")
        analysis_input = RequirementAnalysisInput.from_dict(
            {
                "task_id": task_id,
                "mode": req.mode,
                "user_prompt": req.userPrompt,
                "repo_root": str(repo_root),
                "active_file": req.context.activeFile,
                "selection": self._selection_text(req.context.selection),
                "open_files": req.context.openFiles,
                "diagnostics": req.context.diagnostics,
                "recent_test_failures": [req.context.testLogs] if req.context.testLogs else [],
                "git_diff_summary": req.context.gitDiff,
                "execution_constraints": {
                    "disallow_new_dependencies": True,
                    "preserve_public_api": True,
                },
            }
        )
        analysis = await self.requirement_orchestrator.run(
            settings["requirement"],
            analysis_input,
            self._model_progress_callback(task_id),
        )
        if analysis.status not in {
            "paused_content_verified",
            "paused_converged",
            "verified",
            "accepted",
        }:
            raise TddPipelineError(
                f"Requirement analysis could not converge (status={analysis.status})",
                code="MODEL_ERROR",
            )

        await self.task_service.set_status(task_id, "running", "正在生成完整测试用例")
        await self._log(task_id, "[2/6] 正在生成正向、边界、异常和集成测试用例……\n")
        test_case_input = TestCaseGenerationInput(
            task_id=task_id,
            user_prompt=req.userPrompt,
            plan=self._test_plan_from_analysis(analysis),
            story_units=analysis.story_units,
            story_dependency_graph=asdict(analysis.story_dependency_graph),
            story_relationships=[asdict(item) for item in analysis.story_relationships],
            execution_constraints=TestCaseGenerationConstraints(
                max_test_cases_per_story=8,
                require_boundary_cases=True,
                require_negative_cases=True,
            ),
        )
        test_cases = await self.test_case_orchestrator.run(
            settings["test_case"],
            test_case_input,
        )
        if test_cases.completion_check and not test_cases.completion_check.is_complete:
            missing = "; ".join(test_cases.completion_check.missing_items)
            raise TddPipelineError(
                f"Generated test plan is incomplete: {missing}",
                code="MODEL_ERROR",
            )

        await self._log(task_id, "[3/6] 正在把测试用例转换为可执行测试代码……\n")
        repository_context = self.context_collector.collect(
            repo_root,
            [req.context.activeFile or "", *req.context.openFiles],
        )
        test_code_input = TestCodeGenerationInput(
            task_id=task_id,
            user_prompt=req.userPrompt,
            plan=test_case_input.plan,
            story_units=analysis.story_units,
            test_plan=test_cases.test_plan,
            test_cases=test_cases.test_cases,
            repository_context=repository_context,
            execution_constraints=TestCodeGenerationConstraints(
                max_test_files=12,
                framework_hint=self._detect_test_framework(repo_root),
            ),
        )
        test_code = await self.test_code_orchestrator.run(
            settings["test_code"],
            test_code_input,
        )
        immutable_test_files = [asdict(item) for item in test_code.test_files]

        implementation_input = CodeImplementationInput(
            task_id=task_id,
            user_prompt=req.userPrompt,
            requirement_spec=asdict(analysis.requirement_spec),
            story_units=[asdict(item) for item in analysis.story_units],
            test_plan=test_cases.test_plan,
            test_cases=[asdict(item) for item in test_cases.test_cases],
            test_files=immutable_test_files,
            repository_context=repository_context,
        )
        await self._log(task_id, "[4/6] 正在根据固定测试基线生成业务实现……\n")
        implementation = await self.implementation_orchestrator.run(
            settings["implementation"],
            implementation_input,
            self._model_progress_callback(task_id),
        )

        execution: dict[str, Any] | None = None
        attempts: list[dict[str, Any]] = []
        for repair_iteration in range(self.max_repair_iterations + 1):
            await self._log(
                task_id,
                f"[5/6] 测试执行轮次 {repair_iteration + 1}/{self.max_repair_iterations + 1}……\n",
            )
            execution = await self._execute(
                task_id=task_id,
                req=req,
                repo_root=repo_root,
                test_files=immutable_test_files,
                implementation_files=implementation.files,
                test_command=implementation.test_command,
                analysis_package_id=analysis.package_id,
            )
            attempts.append(
                {
                    "iteration": repair_iteration,
                    "status": execution["status"],
                    "exit_code": execution["execution"].get("exit_code"),
                    "failed_tests": execution["test_summary"].get("failed_tests", []),
                }
            )
            summary = execution["test_summary"]
            await self.event_bus.publish(
                task_id,
                "task.test.result",
                {
                    "framework": summary.get("framework") or "unknown",
                    "passed": summary.get("passed", 0),
                    "failed": summary.get("failed", 0) + summary.get("errors", 0),
                    "skipped": summary.get("skipped", 0),
                    "iteration": repair_iteration,
                },
            )
            if execution["status"] == "passed":
                break
            if execution["status"] != "failed":
                reason = execution["execution"].get("termination_reason", execution["status"])
                raise TddPipelineError(
                    f"Sandbox could not complete the tests: {reason}",
                    code="TIMEOUT_ERROR" if execution["status"] == "timed_out" else "TOOL_ERROR",
                )
            if repair_iteration >= self.max_repair_iterations:
                break

            await self._log(
                task_id,
                f"测试失败，正在进行第 {repair_iteration + 1} 轮实现修复（测试文件保持不变）……\n",
                stream="stderr",
            )
            implementation_input = replace(
                implementation_input,
                previous_files=implementation.files,
                execution_result=self._compact_execution(execution),
                iteration=repair_iteration + 1,
            )
            implementation = await self.implementation_orchestrator.run(
                settings["implementation"],
                implementation_input,
                self._model_progress_callback(task_id),
            )

        assert execution is not None
        patch_files = self._build_patch_files(
            repo_root,
            [*implementation.files, *self._test_files_as_code_files(immutable_test_files)],
        )
        await self.task_service.set_status(task_id, "patch_ready", "最终代码已准备好")
        await self.event_bus.publish(
            task_id,
            "task.patch",
            {
                "patchId": gen_id("patch"),
                "summary": (
                    "TDD 测试全部通过，返回业务代码与回归测试"
                    if execution["status"] == "passed"
                    else "已达到最大修复轮次，返回当前代码供人工检查"
                ),
                "files": patch_files,
            },
        )

        artifacts = {
            "requirementSpec": asdict(analysis.requirement_spec),
            "testPlan": test_cases.test_plan,
            "testCases": [asdict(item) for item in test_cases.test_cases],
            "generatedFiles": [item.path for item in implementation.files],
            "testFiles": [item["path"] for item in immutable_test_files],
            "workflowArtifacts": self._build_workflow_artifacts(
                task_id,
                analysis,
                test_cases,
                test_code,
                implementation,
            ),
            "attempts": attempts,
            "finalExecution": self._compact_execution(execution),
        }
        if execution["status"] == "passed":
            await self.task_service.set_status(task_id, "completed", "TDD 流程完成，测试全部通过")
            await self.event_bus.publish(
                task_id,
                "task.final",
                {
                    "outcome": "completed",
                    "summary": f"测试全部通过；共执行 {len(attempts)} 轮。",
                    "artifacts": artifacts,
                },
            )
            return

        await self.task_service.set_status(task_id, "failed", "达到最大修复轮次，测试仍未通过")
        await self.event_bus.publish(
            task_id,
            "task.error",
            {
                "code": "TOOL_ERROR",
                "message": "达到最大实现修复轮次，仍有测试未通过",
                "retryable": True,
            },
        )
        await self.event_bus.publish(
            task_id,
            "task.final",
            {
                "outcome": "failed",
                "summary": f"完成 {len(attempts)} 轮测试/修复，但测试仍未全部通过。",
                "artifacts": artifacts,
            },
        )

    def _load_model_settings(self) -> dict[str, Any]:
        api_key = os.getenv("GLM_API_KEY", "").strip()
        if not api_key:
            raise TddPipelineError(
                "GLM_API_KEY is not configured for the TDD pipeline",
                code="AUTH_ERROR",
            )
        base = {
            "enabled": True,
            "provider_kind": "openai_compatible",
            "provider_name": os.getenv("GLM_PROVIDER_NAME", "zhipu").strip() or "zhipu",
            "model": os.getenv("GLM_MODEL", "GLM-4.7-Flash").strip() or "GLM-4.7-Flash",
            "api_base": os.getenv("GLM_API_BASE", "https://api.z.ai/api/paas/v4").strip().rstrip("/"),
            "api_key": api_key,
            "wire_api": os.getenv("GLM_WIRE_API", "chat_completions").strip() or "chat_completions",
            "temperature": float(os.getenv("TDD_MODEL_TEMPERATURE", "0.2")),
            "max_tokens": int(os.getenv("TDD_MODEL_MAX_TOKENS", "12000")),
            "timeout_seconds": float(os.getenv("TDD_MODEL_TIMEOUT_SECONDS", "60")),
        }
        requirement = {
            **base,
            "max_request_seconds": float(os.getenv("TDD_MODEL_MAX_REQUEST_SECONDS", "900")),
        }
        implementation = {
            key: value for key, value in requirement.items() if key != "enabled" and key != "provider_kind"
        }
        return {
            "requirement": RequirementAnalysisAgentSettings.from_dict(requirement),
            "test_case": TestCaseGenerationAgentSettings.from_dict(base),
            "test_code": TestCodeGenerationAgentSettings.from_dict(base),
            "implementation": CodeImplementationAgentSettings.from_dict(implementation),
        }

    async def _execute(
        self,
        *,
        task_id: str,
        req: Any,
        repo_root: Path,
        test_files: list[dict[str, Any]],
        implementation_files: list[GeneratedCodeFile],
        test_command: list[str],
        analysis_package_id: str,
    ) -> dict[str, Any]:
        runtime = "docker" if req.policy.workspaceMode == "docker" or req.policy.network == "deny" else "local_copy"
        command = self._test_command(test_files, test_command)
        payload = SandboxExecutionRunRequest.model_validate(
            {
                "task_id": task_id,
                "workspace": {"repo_root": str(repo_root)},
                "test_files": test_files,
                "workspace_files": [asdict(item) for item in implementation_files],
                "command": {"argv": command} if command else None,
                "execution_policy": {
                    "runtime": runtime,
                    "network": req.policy.network,
                    "timeout_seconds": min(req.policy.maxDurationSec, 600),
                    "max_output_bytes": req.policy.maxOutputBytes,
                    "retain_artifacts": True,
                    "allow_workspace_changes": False,
                },
                "provenance": {"requirement_package_id": analysis_package_id},
            }
        )

        async def on_progress(event: dict[str, Any]) -> None:
            if event.get("type") == "output" and event.get("text"):
                await self._log(
                    task_id,
                    str(event["text"]),
                    stream=str(event.get("stream", "stdout")),
                )

        result: dict[str, Any] | None = None

        async def capture(event: dict[str, Any]) -> None:
            nonlocal result
            await on_progress(event)
            if event.get("type") == "result":
                result = event.get("data")

        await self.sandbox_service.stream_run(payload, capture)
        if not isinstance(result, dict):
            raise TddPipelineError("Sandbox did not return a result", code="TOOL_ERROR")
        return result

    @staticmethod
    def _safe_test_command(command: list[str]) -> list[str] | None:
        if not command:
            return None
        allowed = {"python", "python3", "pytest", "npm", "npx", "pnpm", "yarn", "go", "cargo"}
        executable = Path(command[0]).name.lower()
        if executable not in allowed or any(item in {"-c", "-e", "--eval"} for item in command[1:]):
            return None
        if any("\x00" in item for item in command):
            return None
        return command

    @classmethod
    def _test_command(
        cls,
        test_files: list[dict[str, Any]],
        model_command: list[str],
    ) -> list[str] | None:
        paths = [str(item["path"]) for item in test_files]
        metadata = " ".join(
            str(item.get("framework", "")).lower()
            for item in test_files
        )
        if "unittest" in metadata:
            return ["python", "-m", "unittest", *paths]
        if "pytest" in metadata:
            return ["python", "-m", "pytest", *paths, "-q"]
        if "vitest" in metadata:
            return ["npx", "vitest", "run", *paths]
        if "jest" in metadata:
            return ["npx", "jest", *paths]
        return cls._safe_test_command(model_command)

    @staticmethod
    def _detect_test_framework(repo_root: Path) -> str:
        package_json = repo_root / "package.json"
        if package_json.is_file():
            try:
                package = json.loads(package_json.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                package = {}
            dependencies = {
                **package.get("dependencies", {}),
                **package.get("devDependencies", {}),
            }
            if "vitest" in dependencies:
                return "vitest"
            if "jest" in dependencies:
                return "jest"
        if any((repo_root / name).is_file() for name in ("pytest.ini", "conftest.py")):
            return "pytest"
        pyproject = repo_root / "pyproject.toml"
        if pyproject.is_file():
            try:
                if "pytest" in pyproject.read_text(encoding="utf-8").lower():
                    return "pytest"
            except OSError:
                pass
        return "unittest"

    def _model_progress_callback(self, task_id: str):
        async def callback(event: RunProgressEvent) -> None:
            if event.type == "status":
                await self._log(task_id, f"{event.message}\n")
        return callback

    async def _log(self, task_id: str, text: str, *, stream: str = "stdout") -> None:
        await self.event_bus.publish(task_id, "task.log", {"stream": stream, "text": text})

    @staticmethod
    def _selection_text(selection: Any | None) -> str | None:
        if selection is None:
            return None
        return (
            f"{selection.startLine}:{selection.startCol}-"
            f"{selection.endLine}:{selection.endCol}"
        )

    @staticmethod
    def _test_plan_from_analysis(analysis: Any) -> str:
        criteria = "\n".join(f"- {item}" for item in analysis.requirement_spec.acceptance_criteria)
        return (
            "为所有 user story 和验收标准生成可自动化测试；必须覆盖正常路径、"
            "边界值和非法输入。仅当需求或仓库上下文确实存在外部依赖、权限/状态机或多个"
            "story 的交互时，才必须覆盖相应的依赖失败、权限/状态约束或跨 story 集成路径；"
            "没有此类上下文时，应在测试计划中标注为不适用，而不能视为缺失。\n"
            f"全局验收标准：\n{criteria}"
        )

    @staticmethod
    def _compact_execution(execution: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": execution.get("status"),
            "command": execution.get("execution", {}).get("command", {}),
            "exit_code": execution.get("execution", {}).get("exit_code"),
            "termination_reason": execution.get("execution", {}).get("termination_reason"),
            "test_summary": execution.get("test_summary", {}),
            "stdout": execution.get("outputs", {}).get("stdout", "")[-12000:],
            "stderr": execution.get("outputs", {}).get("stderr", "")[-12000:],
            "failure": execution.get("failure"),
        }

    @staticmethod
    def _build_workflow_artifacts(
        task_id: str,
        analysis: Any,
        test_cases: Any,
        test_code: Any,
        implementation: Any,
    ) -> dict[str, Any]:
        requirement_result = asdict(analysis)
        test_case_result = asdict(test_cases)
        test_code_result = asdict(test_code)
        implementation_result = asdict(implementation)
        test_files = test_code_result.get("test_files", [])
        implementation_files = implementation_result.get("files", [])

        files = [
            {
                "relativePath": "README.md",
                "stage": "summary",
                "title": "Artifact summary",
                "content": "\n".join(
                    [
                        "# AI IDE workflow artifacts",
                        "",
                        f"Task: {task_id}",
                        "",
                        "## Stage status",
                        "",
                        "- 01 Requirement analysis: complete",
                        "- 02 Test case generation: complete",
                        "- 03 Business implementation: complete",
                        "",
                        "## Test baseline",
                        "",
                        *(
                            [
                                f"- `02-test-cases/test-code/{item['path']}`"
                                for item in test_files
                            ]
                            or ["- No test file draft has been generated."]
                        ),
                        "",
                        "## Generated business implementation",
                        "",
                        *(
                            [
                                f"- `03-implementation/files/{item['path']}`"
                                for item in implementation_files
                            ]
                            or ["- No production implementation has been generated."]
                        ),
                        "",
                        "These files are review snapshots. They do not overwrite workspace source files.",
                        "",
                    ]
                ),
            },
            {
                "relativePath": "01-requirement-analysis/requirement-analysis.json",
                "stage": "requirement_analysis",
                "title": "Stage 1 requirement analysis",
                "content": json.dumps(
                    requirement_result,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
                + "\n",
            },
            {
                "relativePath": "02-test-cases/test-cases.json",
                "stage": "test_case_generation",
                "title": "Stage 2 test cases",
                "content": json.dumps(
                    test_case_result,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
                + "\n",
            },
            {
                "relativePath": "02-test-cases/test-plan.md",
                "stage": "test_case_generation",
                "title": "Stage 2 test plan",
                "content": f"{test_cases.test_plan.rstrip()}\n",
            },
            {
                "relativePath": "02-test-cases/test-code-manifest.json",
                "stage": "test_case_generation",
                "title": "Stage 2 test code baseline manifest",
                "content": json.dumps(
                    {
                        "implementation_plan": test_code_result.get("implementation_plan", []),
                        "changed_files": test_code_result.get("changed_files", []),
                        "rationale": test_code_result.get("rationale", ""),
                        "warnings": test_code_result.get("warnings", []),
                        "quality_checks": test_code_result.get("quality_checks", {}),
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
                + "\n",
            },
        ]

        for index, test_file in enumerate(test_files, start=1):
            path = str(test_file.get("path") or f"generated-test-{index}.txt")
            safe_path = TddEngine._safe_artifact_relative_path(path, index)
            content = str(test_file.get("content") or "")
            files.append(
                {
                    "relativePath": f"02-test-cases/test-code/{safe_path}",
                    "stage": "test_case_generation",
                    "title": path,
                    "content": content if content.endswith("\n") else f"{content}\n",
                }
            )

        files.append(
            {
                "relativePath": "03-implementation/manifest.json",
                "stage": "code_implementation",
                "title": "Stage 3 business implementation manifest",
                "content": json.dumps(
                    {
                        "implementation_plan": implementation_result.get("implementation_plan", []),
                        "changed_files": implementation_result.get("changed_files", []),
                        "rationale": implementation_result.get("rationale", ""),
                        "test_command": implementation_result.get("test_command", []),
                        "warnings": implementation_result.get("warnings", []),
                        "quality_checks": implementation_result.get("quality_checks", {}),
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ) + "\n",
            }
        )
        for index, implementation_file in enumerate(implementation_files, start=1):
            path = str(implementation_file.get("path") or f"generated-code-{index}.txt")
            safe_path = TddEngine._safe_artifact_relative_path(path, index)
            content = str(implementation_file.get("content") or "")
            files.append(
                {
                    "relativePath": f"03-implementation/files/{safe_path}",
                    "stage": "code_implementation",
                    "title": path,
                    "content": content if content.endswith("\n") else f"{content}\n",
                }
            )

        return {
            "taskId": task_id,
            "directoryName": task_id,
            "completedStages": [
                "requirement_analysis",
                "test_case_generation",
                "code_implementation",
            ],
            "files": files,
        }

    @staticmethod
    def _safe_artifact_relative_path(path: str, index: int) -> str:
        parts = []
        for part in path.replace("\\", "/").split("/"):
            normalized = part.strip()
            if normalized and normalized not in {".", ".."}:
                parts.append(normalized.replace(":", "-"))
        return "/".join(parts) or f"generated-test-{index}.txt"

    @staticmethod
    def _test_files_as_code_files(test_files: list[dict[str, Any]]) -> list[GeneratedCodeFile]:
        return [
            GeneratedCodeFile(
                path=str(item["path"]),
                language=str(item.get("language") or "text"),
                purpose=str(item.get("purpose") or "Generated regression tests"),
                content=str(item["content"]),
            )
            for item in test_files
        ]

    @staticmethod
    def _build_patch_files(repo_root: Path, files: list[GeneratedCodeFile]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in files:
            target = (repo_root / item.path).resolve()
            try:
                target.relative_to(repo_root)
            except ValueError as error:
                raise TddPipelineError(
                    f"Generated file escapes repository: {item.path}",
                    code="PATCH_ERROR",
                ) from error
            before = target.read_text(encoding="utf-8") if target.is_file() else ""
            before_lines = before.splitlines()
            after_lines = item.content.splitlines()
            unified = "\n".join(
                difflib.unified_diff(
                    before_lines,
                    after_lines,
                    fromfile=f"a/{item.path}",
                    tofile=f"b/{item.path}",
                    lineterm="",
                )
            )
            result.append(
                {
                    "path": item.path,
                    "changeType": "modify" if target.exists() else "create",
                    "unifiedDiff": unified,
                    "ops": [
                        {
                            "op": "replace_range",
                            "startLine": 1,
                            "endLine": max(1, len(before_lines) + 1),
                            "content": item.content + ("\n" if not item.content.endswith("\n") else ""),
                        }
                    ],
                }
            )
        return result
