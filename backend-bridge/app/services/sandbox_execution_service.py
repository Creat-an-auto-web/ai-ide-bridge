from __future__ import annotations

import asyncio
import difflib
import os
import re
import shlex
import shutil
import signal
import tempfile
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models.sandbox_execution import (
    SandboxCommandPayload,
    DockerRuntimeStatusPayload,
    SandboxExecutionPolicyPayload,
    SandboxExecutionResultPayload,
    SandboxExecutionRunRequest,
    SandboxFailurePayload,
    SandboxOutputsPayload,
    SandboxProvenancePayload,
    SandboxTestFilePayload,
    SandboxTestSummaryPayload,
    SandboxExecutionSummaryPayload,
)
from app.models.test_code_execution import TestCodeExecutionRunRequest


ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


class SandboxExecutionBackendService:
    """Executes tests through the versioned sandbox protocol."""

    _ignored_workspace_names = {
        ".git",
        ".venv",
        "venv",
        ".runtime",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".tox",
        "dist",
        "build",
    }
    _environment_key_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def __init__(
        self,
        *,
        docker_command: str | None = None,
        docker_image: str | None = None,
        docker_check_timeout_seconds: float = 5.0,
    ) -> None:
        self.docker_command = (
            docker_command
            or os.getenv("AI_IDE_BRIDGE_DOCKER_COMMAND")
            or "docker"
        )
        self.docker_image_override = docker_image or os.getenv("AI_IDE_BRIDGE_DOCKER_IMAGE")
        self.docker_image = (
            self.docker_image_override
            or "python:3.12-slim"
        )
        self.docker_check_timeout_seconds = docker_check_timeout_seconds

    async def check_docker_runtime(self) -> dict[str, Any]:
        """Check that both the Docker CLI and its server are available."""
        try:
            process = await asyncio.create_subprocess_exec(
                self.docker_command,
                "info",
                "--format",
                "{{.ServerVersion}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=os.name == "posix",
            )
        except FileNotFoundError:
            return DockerRuntimeStatusPayload(
                available=False,
                command=self.docker_command,
                detail="未找到 docker 命令。请安装并启动 Docker Desktop。",
            ).model_dump(mode="json")
        except OSError as error:
            return DockerRuntimeStatusPayload(
                available=False,
                command=self.docker_command,
                detail=f"无法启动 Docker CLI：{error}",
            ).model_dump(mode="json")

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.docker_check_timeout_seconds,
            )
        except TimeoutError:
            self._terminate_process(process)
            await self._wait_for_process_exit(process)
            return DockerRuntimeStatusPayload(
                available=False,
                command=self.docker_command,
                detail="Docker Desktop 响应超时，可能尚未启动完成。",
            ).model_dump(mode="json")

        if process.returncode == 0:
            server_version = stdout.decode("utf-8", errors="replace").strip() or None
            return DockerRuntimeStatusPayload(
                available=True,
                command=self.docker_command,
                server_version=server_version,
                detail="Docker Desktop 已启动且 Docker 引擎可用。",
            ).model_dump(mode="json")

        detail = (
            stderr.decode("utf-8", errors="replace").strip()
            or stdout.decode("utf-8", errors="replace").strip()
            or "Docker 引擎不可用。"
        )
        return DockerRuntimeStatusPayload(
            available=False,
            command=self.docker_command,
            detail=(
                "Docker Desktop 未启动或 Docker 引擎不可用："
                f"{self._truncate_text(detail, 1200)}"
            ),
        ).model_dump(mode="json")

    async def run(self, payload: SandboxExecutionRunRequest) -> dict[str, Any]:
        return await self._run(payload)

    async def stream_run(
        self,
        payload: SandboxExecutionRunRequest,
        event_callback: ProgressCallback,
    ) -> None:
        started_at = time.perf_counter()
        send_lock = asyncio.Lock()

        async def emit(event: dict[str, Any]) -> None:
            event.setdefault(
                "elapsed_ms",
                int((time.perf_counter() - started_at) * 1000),
            )
            async with send_lock:
                await event_callback(event)

        await emit(
            {
                "type": "status",
                "stage": "accepted",
                "message": "已收到沙箱运行测试请求。",
            },
        )
        result = await self._run(payload, event_callback=emit)
        await emit(
            {
                "type": "result",
                "stage": "completed",
                "message": "沙箱运行测试已完成。",
                "data": result,
            },
        )

    async def run_legacy(self, payload: TestCodeExecutionRunRequest) -> dict[str, Any]:
        canonical_request = self.legacy_request_to_sandbox_request(payload)
        result = await self.run(canonical_request)
        return self.to_legacy_result(result, canonical_request)

    async def _run(
        self,
        payload: SandboxExecutionRunRequest,
        event_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        sandbox_id = f"sandbox_{uuid4().hex[:12]}"
        command = payload.command or self._infer_command(payload.test_files)
        policy = payload.execution_policy

        await self._emit(
            event_callback,
            {
                "type": "status",
                "stage": "validating_request",
                "message": "正在校验工作区、测试文件和执行策略。",
            },
        )
        self._validate_workspace(payload.workspace.repo_root)
        self._validate_test_file_paths(payload.test_files)
        self._validate_command_cwd(command.cwd)

        if policy.runtime == "docker":
            await self._emit(
                event_callback,
                {
                    "type": "status",
                    "stage": "docker_check_started",
                    "message": "正在检查 Docker Desktop 和 Docker 引擎状态。",
                },
            )
            docker_status = await self.check_docker_runtime()
            if not docker_status["available"]:
                await self._emit(
                    event_callback,
                    {
                        "type": "status",
                        "stage": "docker_unavailable",
                        "message": "Docker Desktop 不可用，等待选择运行方式。",
                        "metadata": {
                            "user_action_required": "docker_runtime_choice",
                            "options": [
                                "use_local_copy",
                                "retry_docker",
                                "cancel",
                            ],
                            "docker_status": docker_status,
                        },
                    },
                )
                return self._build_infrastructure_error(
                    payload=payload,
                    command=command,
                    sandbox_id=sandbox_id,
                    started_at=started_at,
                    kind="docker_runtime_unavailable",
                    summary=docker_status["detail"],
                    warning="请启动 Docker Desktop 后重试，或改用临时工作区测试。",
                    workspace_isolated=False,
                    network_isolated=False,
                )
            await self._emit(
                event_callback,
                {
                    "type": "status",
                    "stage": "docker_ready",
                    "message": (
                        "Docker Desktop 已就绪，准备创建隔离容器。"
                        + (
                            f" 服务端版本：{docker_status['server_version']}。"
                            if docker_status.get("server_version")
                            else ""
                        )
                    ),
                },
            )

        if policy.runtime == "local_copy" and policy.network == "deny":
            return self._build_infrastructure_error(
                payload=payload,
                command=command,
                sandbox_id=sandbox_id,
                started_at=started_at,
                kind="network_isolation_unavailable",
                summary="local_copy 运行时不能强制隔离网络，已拒绝在非隔离网络中执行。",
                warning="当前本地临时目录执行器只隔离工作区写入；需要网络隔离时请选择 Docker runtime。",
                workspace_isolated=False,
                network_isolated=False,
            )

        source_root = Path(payload.workspace.repo_root).expanduser().resolve()
        is_docker = policy.runtime == "docker"
        warnings = (
            [
                "当前使用 Docker runtime：源工作区不会直接被测试写入。",
                "容器使用独立文件系统、资源限制和网络策略；运行结束后自动清理。",
            ]
            if is_docker
            else [
                "当前使用 local_copy 运行时：工作区写入不会回写原项目。",
                "当前 local_copy 运行时不隔离网络；正式执行应使用 Docker runtime。",
            ]
        )

        with tempfile.TemporaryDirectory(prefix=f"{sandbox_id}_") as temp_dir:
            sandbox_root = Path(temp_dir) / "workspace"
            await self._emit(
                event_callback,
                {
                    "type": "status",
                    "stage": "workspace_copy_started",
                    "message": "正在复制项目到隔离临时工作区。",
                },
            )
            try:
                await self._copy_workspace(
                    source_root,
                    sandbox_root,
                    Path(temp_dir),
                    event_callback,
                )
            except (OSError, shutil.Error) as error:
                return self._build_infrastructure_error(
                    payload=payload,
                    command=command,
                    sandbox_id=sandbox_id,
                    started_at=started_at,
                    kind="workspace_copy_failed",
                    summary=self._format_workspace_copy_error(error),
                    warning="请检查工作区可读性、符号链接和临时目录空间后重试。",
                    workspace_isolated=False,
                    network_isolated=False,
                )
            await self._emit(
                event_callback,
                {
                    "type": "status",
                    "stage": "workspace_ready",
                    "message": "隔离临时工作区已准备完成。",
                },
            )
            original_contents = self._write_test_files(sandbox_root, payload.test_files)
            await self._emit(
                event_callback,
                {
                    "type": "status",
                    "stage": "test_files_ready",
                    "message": f"已写入 {len(payload.test_files)} 个测试文件副本。",
                    "metadata": {"test_file_count": len(payload.test_files)},
                },
            )
            command_cwd = self._safe_relative_path(
                sandbox_root,
                command.cwd,
                field_name="command.cwd",
            )
            command_cwd.mkdir(parents=True, exist_ok=True)
            environment = self._build_environment(
                command.environment,
                sandbox_root,
            )
            if not is_docker:
                return await self._execute_command(
                    command=command,
                    cwd=command_cwd,
                    environment=environment,
                    timeout_seconds=policy.timeout_seconds,
                    max_output_bytes=policy.max_output_bytes,
                    payload=payload,
                    sandbox_id=sandbox_id,
                    original_contents=original_contents,
                    sandbox_root=sandbox_root,
                    warnings=warnings,
                    started_at=started_at,
                    event_callback=event_callback,
                    runtime="local_copy",
                    network_isolated=False,
                )

            container_name = f"ai-ide-bridge-{sandbox_id}"
            relative_command_cwd = command_cwd.relative_to(sandbox_root).as_posix()
            docker_argv = self._build_docker_run_command(
                payload=payload,
                command=command,
                sandbox_root=sandbox_root,
                container_name=container_name,
                relative_command_cwd=relative_command_cwd,
            )
            await self._emit(
                event_callback,
                {
                    "type": "status",
                    "stage": "container_starting",
                    "message": "正在创建 Docker 沙箱容器。",
                    "metadata": {
                        "image": self._docker_image_for(payload, command),
                        "network": policy.network,
                    },
                },
            )
            return await self._execute_command(
                command=command,
                cwd=command_cwd,
                environment=environment,
                timeout_seconds=policy.timeout_seconds,
                max_output_bytes=policy.max_output_bytes,
                payload=payload,
                sandbox_id=sandbox_id,
                original_contents=original_contents,
                sandbox_root=sandbox_root,
                warnings=warnings,
                started_at=started_at,
                event_callback=event_callback,
                runtime="docker",
                network_isolated=policy.network == "deny",
                process_argv=docker_argv,
                process_cwd=Path(temp_dir),
                process_environment=os.environ.copy(),
                docker_container_name=container_name,
            )

    def _docker_image_for(
        self,
        payload: SandboxExecutionRunRequest,
        command: SandboxCommandPayload,
    ) -> str:
        if self.docker_image_override:
            return self.docker_image

        metadata = " ".join(
            [
                *(item.language.lower() for item in payload.test_files),
                *(item.framework.lower() for item in payload.test_files),
                *command.argv,
            ],
        )
        if any(
            marker in metadata
            for marker in (
                "node",
                "npm",
                "pnpm",
                "yarn",
                "jest",
                "vitest",
                "typescript",
            )
        ):
            return "node:22-bookworm-slim"
        return self.docker_image

    def _build_docker_run_command(
        self,
        *,
        payload: SandboxExecutionRunRequest,
        command: SandboxCommandPayload,
        sandbox_root: Path,
        container_name: str,
        relative_command_cwd: str = ".",
    ) -> list[str]:
        container_workdir = (
            "/workspace"
            if relative_command_cwd in ("", ".")
            else f"/workspace/{relative_command_cwd}"
        )
        docker_argv = [
            self.docker_command,
            "run",
            "--rm",
            "--init",
            "--name",
            container_name,
            "--workdir",
            container_workdir,
            "--mount",
            f"type=bind,source={sandbox_root},target=/workspace",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,size=512m",
            "--tmpfs",
            "/dev/shm:rw,nosuid,size=64m",
            "--network",
            "none" if payload.execution_policy.network == "deny" else "bridge",
            "--cpus",
            os.getenv("AI_IDE_BRIDGE_DOCKER_CPUS", "2"),
            "--memory",
            os.getenv("AI_IDE_BRIDGE_DOCKER_MEMORY", "2g"),
            "--pids-limit",
            os.getenv("AI_IDE_BRIDGE_DOCKER_PIDS_LIMIT", "256"),
            "--security-opt",
            "no-new-privileges:true",
            "--cap-drop",
            "ALL",
        ]
        if hasattr(os, "getuid") and hasattr(os, "getgid"):
            docker_argv.extend(["--user", f"{os.getuid()}:{os.getgid()}"])

        for key, value in self._build_container_environment(
            command.environment,
        ).items():
            docker_argv.extend(["--env", f"{key}={value}"])

        docker_argv.extend(
            [
                self._docker_image_for(payload, command),
                *command.argv,
            ],
        )
        return docker_argv

    def _build_container_environment(
        self,
        requested: dict[str, str],
    ) -> dict[str, str]:
        environment = {
            "HOME": "/tmp",
            "TMPDIR": "/tmp",
            "TEMP": "/tmp",
            "TMP": "/tmp",
        }
        for key in ("LANG", "LC_ALL"):
            value = os.environ.get(key)
            if value:
                environment[key] = value
        for key, value in requested.items():
            if not self._environment_key_pattern.fullmatch(key):
                raise ValueError(f"command.environment contains invalid key: {key}")
            if "\x00" in value:
                raise ValueError(f"command.environment.{key} must not contain NUL characters")
            environment[key] = value
        return environment

    async def _remove_docker_container(self, container_name: str) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                self.docker_command,
                "rm",
                "--force",
                container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=os.name == "posix",
            )
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                self._terminate_process(process)
                await self._wait_for_process_exit(process)
        except (OSError, TimeoutError):
            return

    @staticmethod
    async def _wait_for_process_exit(
        process: asyncio.subprocess.Process,
        timeout_seconds: float = 2.0,
    ) -> None:
        try:
            await asyncio.wait_for(asyncio.shield(process.wait()), timeout=timeout_seconds)
        except TimeoutError:
            try:
                process.kill()
            except (OSError, ProcessLookupError):
                return
            try:
                await asyncio.wait_for(asyncio.shield(process.wait()), timeout=1.0)
            except TimeoutError:
                return

    async def _execute_command(
        self,
        *,
        command: SandboxCommandPayload,
        cwd: Path,
        environment: dict[str, str],
        timeout_seconds: int,
        max_output_bytes: int,
        payload: SandboxExecutionRunRequest,
        sandbox_id: str,
        original_contents: dict[str, str | None],
        sandbox_root: Path,
        warnings: list[str],
        started_at: float,
        event_callback: ProgressCallback | None = None,
        runtime: str = "local_copy",
        network_isolated: bool = False,
        process_argv: list[str] | None = None,
        process_cwd: Path | None = None,
        process_environment: dict[str, str] | None = None,
        docker_container_name: str | None = None,
    ) -> dict[str, Any]:
        process: asyncio.subprocess.Process | None = None
        timed_out = False
        command_error: OSError | None = None
        stdout_bytes = b""
        stderr_bytes = b""
        stdout_truncated = False
        stderr_truncated = False
        output_limit = max(1, max_output_bytes)
        stdout_limit = (output_limit + 1) // 2
        stderr_limit = output_limit - stdout_limit

        stdout_reader: asyncio.Task[tuple[bytes, bool]] | None = None
        stderr_reader: asyncio.Task[tuple[bytes, bool]] | None = None
        wait_task: asyncio.Task[int] | None = None
        docker_container_removed = False

        async def stop_process() -> None:
            if process is None:
                return
            if process.returncode is None:
                self._terminate_process(process)
            await self._wait_for_process_exit(process)
            if wait_task is not None and not wait_task.done():
                await wait_task

        async def collect_reader_results(
            *,
            ignore_errors: bool = False,
        ) -> None:
            nonlocal stdout_bytes, stderr_bytes
            nonlocal stdout_truncated, stderr_truncated

            readers = [reader for reader in (stdout_reader, stderr_reader) if reader is not None]
            if not readers:
                return
            results = await asyncio.gather(*readers, return_exceptions=True)
            if not ignore_errors:
                for result in results:
                    if isinstance(result, BaseException):
                        raise result
            if len(results) == 2:
                if not isinstance(results[0], BaseException):
                    stdout_bytes, stdout_truncated = results[0]
                if not isinstance(results[1], BaseException):
                    stderr_bytes, stderr_truncated = results[1]

        async def cleanup_after_error() -> None:
            nonlocal docker_container_removed
            await stop_process()
            await collect_reader_results(ignore_errors=True)
            if docker_container_name and not docker_container_removed:
                docker_container_removed = True
                await self._remove_docker_container(docker_container_name)

        try:
            await self._emit(
                event_callback,
                {
                    "type": "status",
                    "stage": "command_starting",
                    "message": f"准备执行测试命令：{shlex.join(command.argv)}",
                    "metadata": {"argv": list(command.argv), "cwd": command.cwd},
                },
            )
            process = await asyncio.create_subprocess_exec(
                *(process_argv or command.argv),
                cwd=str(process_cwd or cwd),
                env=process_environment or environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=os.name == "posix",
            )
            assert process.stdout is not None
            assert process.stderr is not None
            await self._emit(
                event_callback,
                {
                    "type": "status",
                    "stage": "command_started",
                    "message": "测试命令已启动，正在等待执行结果。",
                },
            )
            stdout_reader = asyncio.create_task(
                self._read_stream_with_limit(
                    process.stdout,
                    stdout_limit,
                    "stdout",
                    event_callback,
                ),
            )
            stderr_reader = asyncio.create_task(
                self._read_stream_with_limit(
                    process.stderr,
                    stderr_limit,
                    "stderr",
                    event_callback,
                ),
            )
            wait_task = asyncio.create_task(process.wait())
            command_started_at = time.perf_counter()
            while not wait_task.done():
                elapsed_seconds = time.perf_counter() - command_started_at
                remaining_seconds = timeout_seconds - elapsed_seconds
                if remaining_seconds <= 0:
                    timed_out = True
                    await stop_process()
                    break
                try:
                    await asyncio.wait_for(
                        asyncio.shield(wait_task),
                        timeout=min(1.0, remaining_seconds),
                    )
                except TimeoutError:
                    await self._emit(
                        event_callback,
                        {
                            "type": "heartbeat",
                            "stage": "command_running",
                            "message": "测试命令仍在运行。",
                            "metadata": {
                                "command_elapsed_ms": int(elapsed_seconds * 1000),
                            },
                        },
                    )
                except asyncio.CancelledError:
                    await cleanup_after_error()
                    raise
            if not timed_out:
                await wait_task
            await collect_reader_results()
            if (
                docker_container_name
                and (
                    timed_out
                    or (
                        process.returncode is not None
                        and process.returncode == 125
                    )
                )
            ):
                docker_container_removed = True
                await self._remove_docker_container(docker_container_name)
        except (FileNotFoundError, PermissionError, OSError) as error:
            await cleanup_after_error()
            command_error = error
        except BaseException:
            await cleanup_after_error()
            raise

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        stdout = self._decode_output(stdout_bytes, stdout_truncated)
        stderr = self._decode_output(stderr_bytes, stderr_truncated)
        output_truncated = stdout_truncated or stderr_truncated

        if command_error is not None:
            status = "infrastructure_error"
            exit_code = None
            signal_number = None
            if runtime == "docker":
                termination_reason = (
                    "docker_runtime_unavailable"
                    if isinstance(command_error, FileNotFoundError)
                    else "docker_execution_failed"
                )
                command_error_summary = self._format_command_error(command, command_error)
                failure_summary = f"Docker 沙箱启动失败：{command_error_summary}"
            else:
                termination_reason = (
                    "command_not_found"
                    if isinstance(command_error, FileNotFoundError)
                    else "command_start_failed"
                )
                failure_summary = self._format_command_error(command, command_error)
            failure = SandboxFailurePayload(
                kind=termination_reason,
                summary=failure_summary,
                repair_targets=[item.path for item in payload.test_files],
                related_test_case_ids=self._related_test_case_ids(payload.test_files),
            )
            test_summary = SandboxTestSummaryPayload(
                framework=self._detect_framework(payload.test_files),
            )
        else:
            assert process is not None
            exit_code = process.returncode
            signal_number = -exit_code if exit_code is not None and exit_code < 0 else None
            docker_execution_failed = runtime == "docker" and exit_code == 125
            if timed_out:
                status = "timed_out"
                termination_reason = "timeout"
            elif docker_execution_failed:
                status = "infrastructure_error"
                termination_reason = "docker_execution_failed"
            elif exit_code == 0:
                status = "passed"
                termination_reason = "test_passed"
            else:
                status = "failed"
                termination_reason = "test_failure"

            test_summary = self._build_test_summary(
                payload.test_files,
                stdout_bytes,
                stderr_bytes,
            )
            docker_failure_summary = self._summarize_failure(stdout, stderr)
            failure = None
            if status != "passed":
                failure = SandboxFailurePayload(
                    kind=termination_reason,
                    summary=(
                        "测试执行超时。"
                        if status == "timed_out"
                        else (
                            (
                                "Docker 容器未能启动或测试命令未能在容器中执行。"
                                if docker_failure_summary
                                == "测试执行失败，但没有返回可解析的错误信息。"
                                else (
                                    "Docker 容器启动失败："
                                    f"{docker_failure_summary}"
                                )
                            )
                            if status == "infrastructure_error"
                            else self._summarize_failure(stdout, stderr)
                        )
                    ),
                    repair_targets=[item.path for item in payload.test_files],
                    related_test_case_ids=self._related_test_case_ids(payload.test_files),
                )

        await self._emit(
            event_callback,
            {
                "type": "status",
                "stage": "command_finished",
                "message": (
                    "测试命令执行超时。"
                    if timed_out
                    else "测试命令执行完成。"
                    if command_error is None
                    else "测试命令未能启动。"
                ),
                "metadata": {
                    "exit_code": exit_code,
                    "timed_out": timed_out,
                },
            },
        )

        execution = SandboxExecutionSummaryPayload(
            command=(
                {
                    "argv": list(command.argv),
                    "cwd": command.cwd,
                }
            ),
            runtime=runtime,
            sandbox_id=sandbox_id,
            workspace_isolated=True,
            network_isolated=network_isolated,
            duration_ms=duration_ms,
            exit_code=exit_code,
            signal=signal_number,
            termination_reason=termination_reason,
        )
        outputs = SandboxOutputsPayload(
            stdout=stdout,
            stderr=stderr,
            output_truncated=output_truncated,
            workspace_diff=self._collect_workspace_diff(
                sandbox_root,
                original_contents,
            ),
            artifacts=(
                [item.path for item in payload.test_files]
                if payload.execution_policy.retain_artifacts
                else []
            ),
        )
        if output_truncated:
            warnings.append(
                f"标准输出和错误输出合计超过 {max_output_bytes} 字节，已截断返回内容。",
            )
        warnings.append("临时执行目录会在本次运行结束后清理，当前不保留可再次挂载的沙箱实例。")

        result = SandboxExecutionResultPayload(
            protocol_version=payload.protocol_version,
            task_id=payload.task_id,
            run_id=payload.run_id,
            status=status,
            execution=execution,
            test_summary=test_summary,
            outputs=outputs,
            failure=failure,
            warnings=warnings,
            provenance=payload.provenance,
        )
        return result.to_dict()

    async def _copy_workspace(
        self,
        source_root: Path,
        sandbox_root: Path,
        runtime_root: Path,
        event_callback: ProgressCallback | None,
    ) -> None:
        sandbox_root.mkdir(parents=True, exist_ok=True)
        runtime_root = runtime_root.resolve()

        copied_files = 0
        for current_dir, dirnames, filenames in os.walk(
            source_root,
            topdown=True,
            followlinks=False,
        ):
            current_path = Path(current_dir)
            relative_dir = current_path.relative_to(source_root)
            target_dir = sandbox_root / relative_dir
            target_dir.mkdir(parents=True, exist_ok=True)

            retained_dirs: list[str] = []
            for name in dirnames:
                source_path = current_path / name
                if self._should_ignore_workspace_path(
                    source_path,
                    runtime_root,
                ):
                    continue
                if source_path.is_symlink():
                    continue
                retained_dirs.append(name)
            dirnames[:] = retained_dirs

            for name in filenames:
                source_path = current_path / name
                if self._should_ignore_workspace_path(
                    source_path,
                    runtime_root,
                ) or source_path.is_symlink():
                    continue
                target_path = target_dir / name
                shutil.copy2(source_path, target_path)
                copied_files += 1
                if copied_files == 1 or copied_files % 100 == 0:
                    await self._emit(
                        event_callback,
                        {
                            "type": "status",
                            "stage": "workspace_copy_progress",
                            "message": f"已复制 {copied_files} 个项目文件。",
                            "metadata": {"copied_file_count": copied_files},
                        },
                    )
                await asyncio.sleep(0)

    def _should_ignore_workspace_path(
        self,
        source_path: Path,
        runtime_root: Path,
    ) -> bool:
        if source_path.name in self._ignored_workspace_names:
            return True
        try:
            runtime_root.relative_to(source_path.resolve())
        except ValueError:
            return False
        return True

    @staticmethod
    def _terminate_process(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except (OSError, ProcessLookupError):
            return

    @staticmethod
    async def _read_stream_with_limit(
        stream: asyncio.StreamReader,
        limit: int,
        stream_name: str,
        event_callback: ProgressCallback | None = None,
    ) -> tuple[bytes, bool]:
        retained = bytearray()
        truncated = False
        while chunk := await stream.read(65536):
            available = max(0, limit - len(retained))
            if available:
                retained.extend(chunk[:available])
            if len(chunk) > available:
                truncated = True
            if event_callback and available:
                preview = chunk[: min(available, 4096)].decode(
                    "utf-8",
                    errors="replace",
                )
                if preview:
                    await SandboxExecutionBackendService._emit(
                        event_callback,
                        {
                            "type": "output",
                            "stage": "command_output",
                            "message": f"收到 {stream_name} 输出。",
                            "stream": stream_name,
                            "text": preview,
                        },
                    )
        return bytes(retained), truncated

    @staticmethod
    async def _emit(
        event_callback: ProgressCallback | None,
        event: dict[str, Any],
    ) -> None:
        if event_callback:
            await event_callback(event)

    def _build_infrastructure_error(
        self,
        *,
        payload: SandboxExecutionRunRequest,
        command: SandboxCommandPayload,
        sandbox_id: str,
        started_at: float,
        kind: str,
        summary: str,
        warning: str,
        workspace_isolated: bool,
        network_isolated: bool,
    ) -> dict[str, Any]:
        result = SandboxExecutionResultPayload(
            protocol_version=payload.protocol_version,
            task_id=payload.task_id,
            run_id=payload.run_id,
            status="infrastructure_error",
            execution=SandboxExecutionSummaryPayload(
                command={
                    "argv": list(command.argv),
                    "cwd": command.cwd,
                },
                runtime=payload.execution_policy.runtime,
                sandbox_id=sandbox_id,
                workspace_isolated=workspace_isolated,
                network_isolated=network_isolated,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
                termination_reason=kind,
            ),
            test_summary=SandboxTestSummaryPayload(
                framework=self._detect_framework(payload.test_files),
            ),
            outputs=SandboxOutputsPayload(),
            failure=SandboxFailurePayload(
                kind=kind,
                summary=summary,
                repair_targets=[],
                related_test_case_ids=self._related_test_case_ids(payload.test_files),
            ),
            warnings=[warning],
            provenance=payload.provenance,
        )
        return result.to_dict()

    def _write_test_files(
        self,
        sandbox_root: Path,
        test_files: list[SandboxTestFilePayload],
    ) -> dict[str, str | None]:
        original_contents: dict[str, str | None] = {}
        for test_file in test_files:
            target = self._safe_relative_path(
                sandbox_root,
                test_file.path,
                field_name="test_file.path",
            )
            if target.is_symlink():
                raise ValueError(f"test_file.path points to a symlink: {test_file.path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            original_contents[test_file.path] = (
                target.read_text(encoding="utf-8")
                if target.exists()
                else None
            )
            target.write_text(test_file.content, encoding="utf-8")
        return original_contents

    def _build_environment(
        self,
        requested: dict[str, str],
        sandbox_root: Path,
    ) -> dict[str, str]:
        temp_home = sandbox_root / ".sandbox-home"
        temp_dir = sandbox_root / ".sandbox-tmp"
        temp_home.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        environment: dict[str, str] = {}
        for key in ("PATH", "LANG", "LC_ALL"):
            value = os.environ.get(key)
            if value:
                environment[key] = value
        environment["HOME"] = str(temp_home)
        environment["TMPDIR"] = str(temp_dir)
        environment["TEMP"] = str(temp_dir)
        environment["TMP"] = str(temp_dir)

        for key, value in requested.items():
            if not self._environment_key_pattern.fullmatch(key):
                raise ValueError(f"command.environment contains invalid key: {key}")
            if "\x00" in value:
                raise ValueError(f"command.environment.{key} must not contain NUL characters")
            environment[key] = value
        return environment

    @staticmethod
    def _validate_workspace(repo_root: str) -> None:
        path = Path(repo_root).expanduser()
        if not path.exists() or not path.is_dir():
            raise ValueError("workspace.repo_root must point to an existing directory")

    def _validate_test_file_paths(self, test_files: list[SandboxTestFilePayload]) -> None:
        seen: set[str] = set()
        for test_file in test_files:
            normalized = test_file.path.strip()
            if normalized in seen:
                raise ValueError(f"duplicate test_file.path: {normalized}")
            seen.add(normalized)

    @staticmethod
    def _validate_command_cwd(cwd: str) -> None:
        if Path(cwd).is_absolute():
            raise ValueError("command.cwd must be relative to the sandbox workspace")

    @staticmethod
    def _safe_relative_path(root: Path, relative_path: str, *, field_name: str) -> Path:
        raw_path = relative_path.strip()
        if not raw_path:
            raise ValueError(f"{field_name} must be non-empty")
        if "\x00" in raw_path:
            raise ValueError(f"{field_name} must not contain NUL characters")
        candidate = (root / raw_path).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError as error:
            raise ValueError(f"{field_name} escapes the sandbox workspace: {relative_path}") from error
        return candidate

    @staticmethod
    def _infer_command(test_files: list[SandboxTestFilePayload]) -> SandboxCommandPayload:
        first_file = test_files[0]
        framework = first_file.framework.lower()
        language = first_file.language.lower()
        paths = [item.path for item in test_files]
        if "vitest" in framework:
            argv = ["npx", "vitest", "run", *paths]
        elif "jest" in framework:
            argv = ["npx", "jest", *paths]
        elif "pytest" in framework or language == "python":
            argv = ["python", "-m", "pytest", *paths]
        else:
            argv = ["python", "-m", "pytest", *paths]
        return SandboxCommandPayload(argv=argv)

    @staticmethod
    def _decode_output(raw: bytes, truncated: bool) -> str:
        output = raw.decode("utf-8", errors="replace")
        return output + ("\n[output truncated]" if truncated else "")

    @staticmethod
    def _format_command_error(
        command: SandboxCommandPayload,
        error: OSError,
    ) -> str:
        command_text = shlex.join(command.argv)
        if isinstance(error, FileNotFoundError):
            return f"找不到可执行文件：{command.argv[0]}（命令：{command_text}）"
        return f"启动测试命令失败：{error}（命令：{command_text}）"

    @staticmethod
    def _format_workspace_copy_error(error: OSError | shutil.Error) -> str:
        if isinstance(error, shutil.Error):
            return f"无法创建隔离工作区副本：复制过程中出现 {len(error.args[0])} 个文件错误。"
        return f"无法创建隔离工作区副本：{error}"

    @staticmethod
    def _detect_framework(test_files: list[SandboxTestFilePayload]) -> str | None:
        frameworks = [item.framework.strip() for item in test_files if item.framework.strip()]
        return frameworks[0] if frameworks else None

    def _build_test_summary(
        self,
        test_files: list[SandboxTestFilePayload],
        stdout: bytes,
        stderr: bytes,
    ) -> SandboxTestSummaryPayload:
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        combined = f"{stdout_text}\n{stderr_text}"
        failed_tests = self._parse_test_ids(combined, "FAILED")
        passed_tests = self._parse_test_ids(combined, "PASSED")
        failed = self._parse_count(combined, r"(\d+)\s+failed")
        passed = self._parse_count(combined, r"(\d+)\s+passed")
        skipped = self._parse_count(combined, r"(\d+)\s+skipped")
        errors = self._parse_count(combined, r"(\d+)\s+errors?")
        total = passed + failed + skipped + errors
        return SandboxTestSummaryPayload(
            framework=self._detect_framework(test_files),
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            failed_tests=failed_tests,
            passed_tests=passed_tests,
        )

    @staticmethod
    def _parse_count(text: str, pattern: str) -> int:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        return sum(int(item) for item in matches)

    @staticmethod
    def _parse_test_ids(text: str, marker: str) -> list[str]:
        matches = re.findall(rf"{marker}\s+([^\s]+)", text)
        result: list[str] = []
        for item in matches:
            if item not in result:
                result.append(item)
        return result

    @staticmethod
    def _summarize_failure(stdout: str, stderr: str) -> str:
        content = (stderr.strip() or stdout.strip()).splitlines()
        if not content:
            return "测试执行失败，但没有返回可解析的错误信息。"
        return "\n".join(content[-12:])

    @staticmethod
    def _truncate_text(value: str, max_chars: int) -> str:
        normalized = value.strip()
        if len(normalized) <= max_chars:
            return normalized
        return f"{normalized[:max_chars]}…"

    @staticmethod
    def _related_test_case_ids(test_files: list[SandboxTestFilePayload]) -> list[str]:
        result: list[str] = []
        for test_file in test_files:
            for test_case_id in test_file.related_test_case_ids:
                if test_case_id not in result:
                    result.append(test_case_id)
        return result

    @staticmethod
    def _collect_workspace_diff(
        sandbox_root: Path,
        original_contents: dict[str, str | None],
    ) -> str:
        diff_parts: list[str] = []
        for relative_path, before in original_contents.items():
            target = sandbox_root / relative_path
            after = target.read_text(encoding="utf-8") if target.exists() else ""
            before_lines = (before or "").splitlines()
            after_lines = after.splitlines()
            unified = difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
                lineterm="",
            )
            diff = "\n".join(unified)
            if diff:
                diff_parts.append(diff)
        return "\n\n".join(diff_parts)

    @classmethod
    def legacy_request_to_sandbox_request(
        cls,
        payload: TestCodeExecutionRunRequest,
    ) -> SandboxExecutionRunRequest:
        test_files = [
            SandboxTestFilePayload.model_validate(test_file.model_dump())
            for test_file in payload.input.test_files
        ]
        command_text = payload.input.test_command
        if command_text and command_text.strip():
            argv = shlex.split(command_text)
            if not argv:
                raise ValueError("test_command must contain an executable")
            command = SandboxCommandPayload(argv=argv)
        else:
            command = cls._infer_command(test_files)
        return SandboxExecutionRunRequest(
            protocol_version="sandbox-execution.v1",
            task_id=payload.input.task_id,
            workspace={"repo_root": payload.input.repo_root},
            test_files=test_files,
            command=command,
            execution_policy=SandboxExecutionPolicyPayload(
                runtime="local_copy",
                network="allow",
                timeout_seconds=payload.input.timeout_seconds,
                max_output_bytes=262144,
                retain_artifacts=True,
                allow_workspace_changes=False,
            ),
        )

    @staticmethod
    def to_legacy_result(
        result: dict[str, Any],
        request: SandboxExecutionRunRequest,
    ) -> dict[str, Any]:
        canonical = SandboxExecutionResultPayload.model_validate(result)
        written_files = [item.path for item in request.test_files]
        passed = canonical.status == "passed"
        repairable = canonical.status == "failed"
        return {
            "task_id": canonical.task_id,
            "repo_root": request.workspace.repo_root,
            "written_files": written_files,
            "command": shlex.join(canonical.execution.command.argv),
            "exit_code": canonical.execution.exit_code,
            "passed": passed,
            "failed_tests": canonical.test_summary.failed_tests,
            "passed_tests": canonical.test_summary.passed_tests,
            "stdout": canonical.outputs.stdout,
            "stderr": canonical.outputs.stderr,
            "duration_ms": canonical.execution.duration_ms,
            "artifacts": {
                "written_files": written_files,
            },
            "workspace_diff": canonical.outputs.workspace_diff,
            "evaluation": {
                "decision": (
                    "success"
                    if passed
                    else "repair"
                    if repairable
                    else "blocked"
                ),
                "failure_summary": canonical.failure.summary if canonical.failure else None,
                "repair_targets": canonical.failure.repair_targets if canonical.failure else [],
                "stop_reason": canonical.execution.termination_reason,
            },
            "sandbox": canonical.to_dict(),
        }
