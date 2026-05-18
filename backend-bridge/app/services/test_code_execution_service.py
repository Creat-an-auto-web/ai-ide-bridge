from __future__ import annotations

import difflib
import os
import re
import subprocess
import time
from pathlib import Path

from app.models.test_code_execution import TestCodeExecutionRunRequest


class TestCodeExecutionBackendService:
    async def run(self, payload: TestCodeExecutionRunRequest) -> dict:
        repo_root = Path(payload.input.repo_root).expanduser().resolve()
        if not repo_root.exists() or not repo_root.is_dir():
            raise ValueError("repo_root must point to an existing directory")

        if not payload.input.test_files:
            raise ValueError("test_files must be a non-empty list")

        original_contents: dict[str, str | None] = {}
        written_paths: list[str] = []
        relative_paths: list[str] = []

        for test_file in payload.input.test_files:
            target_path = (repo_root / test_file.path).resolve()
            try:
                target_path.relative_to(repo_root)
            except ValueError as exc:
                raise ValueError(f"test file path escapes repo_root: {test_file.path}") from exc

            target_path.parent.mkdir(parents=True, exist_ok=True)
            original_contents[test_file.path] = (
                target_path.read_text(encoding="utf-8")
                if target_path.exists()
                else None
            )
            target_path.write_text(test_file.content, encoding="utf-8")
            written_paths.append(str(target_path))
            relative_paths.append(test_file.path)

        command = payload.input.test_command or self._infer_test_command(payload.input.test_files)
        started_at = time.perf_counter()
        try:
            completed = subprocess.run(
                ["bash", "-lc", command],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=payload.input.timeout_seconds,
                check=False,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = exc.stdout or ""
            stderr = (exc.stderr or "") + "\nCommand timed out."
        duration_ms = int((time.perf_counter() - started_at) * 1000)

        failed_tests = self._parse_failed_tests(stdout, stderr)
        passed_tests = self._parse_passed_tests(stdout, stderr)
        workspace_diff = self._collect_workspace_diff(repo_root, relative_paths, original_contents)

        evaluation = {
            "decision": "success" if exit_code == 0 else "repair",
            "failure_summary": None if exit_code == 0 else self._summarize_failure(stdout, stderr),
            "repair_targets": relative_paths if exit_code != 0 else [],
            "stop_reason": None if exit_code == 0 else "test_execution_failed",
        }

        return {
            "task_id": payload.input.task_id,
            "repo_root": str(repo_root),
            "written_files": written_paths,
            "command": command,
            "exit_code": exit_code,
            "passed": exit_code == 0,
            "failed_tests": failed_tests,
            "passed_tests": passed_tests,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": duration_ms,
            "artifacts": {
                "written_files": relative_paths,
            },
            "workspace_diff": workspace_diff,
            "evaluation": evaluation,
        }

    def _infer_test_command(self, test_files) -> str:
        first_framework = (test_files[0].framework or "").lower()
        paths = " ".join(self._quote_shell_arg(test_file.path) for test_file in test_files)
        if "pytest" in first_framework or test_files[0].language.lower() == "python":
            return f"python -m pytest {paths}".strip()
        if "vitest" in first_framework:
            return f"npx vitest run {paths}".strip()
        if "jest" in first_framework:
            return f"npx jest {paths}".strip()
        return f"python -m pytest {paths}".strip()

    @staticmethod
    def _quote_shell_arg(value: str) -> str:
        return "'" + value.replace("'", "'\"'\"'") + "'"

    @staticmethod
    def _parse_failed_tests(stdout: str, stderr: str) -> list[str]:
        combined = f"{stdout}\n{stderr}"
        matches = re.findall(r"FAILED\s+([^\s]+)", combined)
        seen: list[str] = []
        for match in matches:
            normalized = match.strip()
            if normalized and normalized not in seen:
                seen.append(normalized)
        return seen

    @staticmethod
    def _parse_passed_tests(stdout: str, stderr: str) -> list[str]:
        combined = f"{stdout}\n{stderr}"
        matches = re.findall(r"PASSED\s+([^\s]+)", combined)
        seen: list[str] = []
        for match in matches:
            normalized = match.strip()
            if normalized and normalized not in seen:
                seen.append(normalized)
        return seen

    @staticmethod
    def _summarize_failure(stdout: str, stderr: str) -> str:
        content = (stderr.strip() or stdout.strip()).splitlines()
        if not content:
            return "测试执行失败，但没有返回可解析的错误信息。"
        return "\n".join(content[-12:])

    @staticmethod
    def _collect_workspace_diff(
        repo_root: Path,
        relative_paths: list[str],
        original_contents: dict[str, str | None],
    ) -> str:
        git_dir = repo_root / ".git"
        if git_dir.exists():
            try:
                diff = subprocess.run(
                    ["git", "diff", "--", *relative_paths],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if diff.stdout.strip():
                    return diff.stdout
            except Exception:
                pass

        diff_parts: list[str] = []
        for relative_path in relative_paths:
            target_path = repo_root / relative_path
            before = original_contents.get(relative_path) or ""
            after = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
            unified = difflib.unified_diff(
                before.splitlines(),
                after.splitlines(),
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
                lineterm="",
            )
            diff_parts.append("\n".join(unified))
        return "\n\n".join(part for part in diff_parts if part.strip())
