from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import httpx

from app.main import app
from app.models.sandbox_execution import SandboxExecutionRunRequest
from app.models.test_code_execution import TestCodeExecutionRunRequest
from app.services.sandbox_execution_service import SandboxExecutionBackendService
from app.services.test_code_execution_service import TestCodeExecutionBackendService


class TestCodeExecutionBackendServiceTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _write_fake_docker(
        path: Path,
        *,
        sleep_on_info: bool = False,
        sleep_on_run: bool = False,
        run_exit_code: int = 0,
        run_stderr: str = "",
    ) -> None:
        info_body = "time.sleep(10)" if sleep_on_info else "print('27.5.1')"
        run_body = "time.sleep(10)" if sleep_on_run else "print('fake docker run')"
        path.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import sys",
                    "import time",
                    "",
                    "command = sys.argv[1] if len(sys.argv) > 1 else ''",
                    "if command == 'info':",
                    f"    {info_body}",
                    "    raise SystemExit(0)",
                    "if command == 'rm':",
                    "    raise SystemExit(0)",
                    "if command == 'run':",
                    f"    {run_body}",
                    f"    print({run_stderr!r}, file=sys.stderr)" if run_stderr else "",
                    f"    raise SystemExit({run_exit_code})",
                    "raise SystemExit(2)",
                    "",
                ],
            ),
            encoding="utf-8",
        )
        path.chmod(0o755)

    async def test_legacy_run_keeps_source_workspace_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            payload = TestCodeExecutionRunRequest.model_validate(
                {
                    "input": {
                        "task_id": "task_exec_success",
                        "repo_root": str(repo_root),
                        "test_files": [
                            {
                                "path": "tests/test_sample.py",
                                "language": "python",
                                "framework": "pytest",
                                "purpose": "验证文件写入",
                                "related_test_case_ids": ["tc_001"],
                                "content": "def test_sample():\n    assert True\n",
                            }
                        ],
                        "test_command": "python -c \"from pathlib import Path; assert Path('tests/test_sample.py').exists()\"",
                        "timeout_seconds": 10,
                    }
                },
            )

            service = TestCodeExecutionBackendService()
            result = await service.run(payload)

            self.assertFalse((repo_root / "tests/test_sample.py").exists())
            self.assertTrue(result["passed"])
            self.assertEqual(result["evaluation"]["decision"], "success")
            self.assertEqual(result["artifacts"]["written_files"], ["tests/test_sample.py"])
            self.assertEqual(result["sandbox"]["status"], "passed")
            self.assertTrue(result["sandbox"]["execution"]["workspace_isolated"])

    async def test_run_collects_failure_summary_for_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            payload = TestCodeExecutionRunRequest.model_validate(
                {
                    "input": {
                        "task_id": "task_exec_failure",
                        "repo_root": str(repo_root),
                        "test_files": [
                            {
                                "path": "tests/test_failure.py",
                                "language": "python",
                                "framework": "pytest",
                                "purpose": "验证失败收集",
                                "related_test_case_ids": ["tc_002"],
                                "content": "def test_failure():\n    assert False\n",
                            }
                        ],
                        "test_command": "python -c \"import sys; sys.stderr.write('FAILED tests/test_failure.py::test_failure\\\\nboom\\\\n'); sys.exit(1)\"",
                        "timeout_seconds": 10,
                    }
                },
            )

            service = TestCodeExecutionBackendService()
            result = await service.run(payload)

            self.assertFalse(result["passed"])
            self.assertEqual(result["evaluation"]["decision"], "repair")
            self.assertEqual(result["failed_tests"], ["tests/test_failure.py::test_failure"])
            self.assertIn("boom", result["evaluation"]["failure_summary"])

    async def test_legacy_run_blocks_repair_for_execution_infrastructure_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = TestCodeExecutionRunRequest.model_validate(
                {
                    "input": {
                        "task_id": "task_exec_missing_command",
                        "repo_root": temp_dir,
                        "test_files": [
                            {
                                "path": "tests/test_sample.py",
                                "language": "python",
                                "framework": "pytest",
                                "purpose": "验证运行环境错误",
                                "content": "def test_sample():\n    assert True\n",
                            }
                        ],
                        "test_command": "not-a-real-test-command",
                    }
                },
            )

            result = await TestCodeExecutionBackendService().run(payload)

            self.assertFalse(result["passed"])
            self.assertEqual(result["sandbox"]["status"], "infrastructure_error")
            self.assertEqual(result["evaluation"]["decision"], "blocked")
            self.assertEqual(
                result["evaluation"]["stop_reason"],
                "command_not_found",
            )

    async def test_sandbox_execution_runs_in_copy_and_returns_structured_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            (repo_root / "source.txt").write_text("source", encoding="utf-8")
            payload = SandboxExecutionRunRequest.model_validate(
                {
                    "task_id": "sandbox_success",
                    "run_id": "exec_success",
                    "workspace": {"repo_root": str(repo_root)},
                    "test_files": [
                        {
                            "path": "tests/test_sample.py",
                            "language": "python",
                            "framework": "pytest",
                            "purpose": "验证隔离写入",
                            "related_test_case_ids": ["tc_001"],
                            "content": "def test_sample():\n    assert True\n",
                        }
                    ],
                    "command": {
                        "argv": [
                            "python",
                            "-c",
                            "from pathlib import Path; assert Path('source.txt').read_text() == 'source'; assert Path('tests/test_sample.py').exists()",
                        ]
                    },
                    "execution_policy": {
                        "runtime": "local_copy",
                        "network": "allow",
                        "timeout_seconds": 10,
                    },
                    "provenance": {
                        "test_code_result_id": "test_code_001",
                    },
                },
            )

            result = await SandboxExecutionBackendService().run(payload)

            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["execution"]["workspace_isolated"])
            self.assertFalse(result["execution"]["network_isolated"])
            self.assertFalse((repo_root / "tests/test_sample.py").exists())
            self.assertIn("tests/test_sample.py", result["outputs"]["workspace_diff"])
            self.assertEqual(result["provenance"]["test_code_result_id"], "test_code_001")

    async def test_sandbox_stream_emits_progress_and_final_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = SandboxExecutionRunRequest.model_validate(
                {
                    "task_id": "sandbox_stream",
                    "workspace": {"repo_root": temp_dir},
                    "test_files": [
                        {
                            "path": "tests/test_stream.py",
                            "language": "python",
                            "framework": "pytest",
                            "content": "def test_stream():\n    assert True\n",
                        }
                    ],
                    "command": {
                        "argv": [
                            "python",
                            "-c",
                            "import time; print('stream output'); time.sleep(1.2)",
                        ]
                    },
                    "execution_policy": {
                        "runtime": "local_copy",
                        "network": "allow",
                        "timeout_seconds": 5,
                    },
                },
            )
            events: list[dict] = []

            async def collect(event: dict) -> None:
                events.append(event)

            await SandboxExecutionBackendService().stream_run(payload, collect)

            stages = [event["stage"] for event in events]
            self.assertIn("workspace_copy_started", stages)
            self.assertIn("workspace_ready", stages)
            self.assertIn("command_started", stages)
            self.assertIn("command_running", stages)
            self.assertIn("command_output", stages)
            self.assertEqual(events[-1]["type"], "result")
            self.assertEqual(events[-1]["data"]["status"], "passed")

    async def test_sandbox_execution_rejects_network_deny_without_docker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = SandboxExecutionRunRequest.model_validate(
                {
                    "task_id": "sandbox_network",
                    "workspace": {"repo_root": temp_dir},
                    "test_files": [
                        {
                            "path": "tests/test_sample.py",
                            "content": "def test_sample():\n    assert True\n",
                        }
                    ],
                    "command": {"argv": ["definitely-not-run"]},
                    "execution_policy": {
                        "runtime": "local_copy",
                        "network": "deny",
                    },
                },
            )

            result = await SandboxExecutionBackendService().run(payload)

            self.assertEqual(result["status"], "infrastructure_error")
            self.assertEqual(result["failure"]["kind"], "network_isolation_unavailable")

    async def test_sandbox_execution_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = SandboxExecutionRunRequest.model_validate(
                {
                    "task_id": "sandbox_escape",
                    "workspace": {"repo_root": temp_dir},
                    "test_files": [
                        {
                            "path": "../escape.py",
                            "content": "raise RuntimeError('should not write')\n",
                        }
                    ],
                    "execution_policy": {
                        "runtime": "local_copy",
                        "network": "allow",
                    },
                },
            )

            with self.assertRaisesRegex(ValueError, "escapes the sandbox workspace"):
                await SandboxExecutionBackendService().run(payload)

    async def test_sandbox_execution_reports_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = SandboxExecutionRunRequest.model_validate(
                {
                    "task_id": "sandbox_timeout",
                    "workspace": {"repo_root": temp_dir},
                    "test_files": [
                        {
                            "path": "tests/test_sample.py",
                            "content": "def test_sample():\n    assert True\n",
                        }
                    ],
                    "command": {
                        "argv": ["python", "-c", "import time; time.sleep(5)"],
                    },
                    "execution_policy": {
                        "runtime": "local_copy",
                        "network": "allow",
                        "timeout_seconds": 1,
                    },
                },
            )

            result = await SandboxExecutionBackendService().run(payload)

            self.assertEqual(result["status"], "timed_out")
            self.assertEqual(result["execution"]["termination_reason"], "timeout")

    async def test_docker_status_reports_available_server(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docker_path = Path(temp_dir) / "fake-docker"
            self._write_fake_docker(docker_path)

            result = await SandboxExecutionBackendService(
                docker_command=str(docker_path),
            ).check_docker_runtime()

            self.assertTrue(result["available"])
            self.assertEqual(result["server_version"], "27.5.1")

    async def test_docker_status_reports_missing_cli_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_docker = Path(temp_dir) / "missing-docker"

            result = await SandboxExecutionBackendService(
                docker_command=str(missing_docker),
            ).check_docker_runtime()

            self.assertFalse(result["available"])
            self.assertIn("未找到 docker 命令", result["detail"])

    async def test_docker_status_reports_timeout_without_leaking_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docker_path = Path(temp_dir) / "slow-docker"
            self._write_fake_docker(docker_path, sleep_on_info=True)

            result = await SandboxExecutionBackendService(
                docker_command=str(docker_path),
                docker_check_timeout_seconds=0.05,
            ).check_docker_runtime()

            self.assertFalse(result["available"])
            self.assertIn("响应超时", result["detail"])

    async def test_docker_unavailable_is_returned_through_the_standard_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = SandboxExecutionRunRequest.model_validate(
                {
                    "task_id": "sandbox_docker_unavailable",
                    "workspace": {"repo_root": temp_dir},
                    "test_files": [
                        {
                            "path": "tests/test_docker_unavailable.py",
                            "content": "assert True\n",
                        }
                    ],
                    "command": {"argv": ["python", "-c", "print('unused')"]},
                    "execution_policy": {
                        "runtime": "docker",
                        "network": "deny",
                    },
                },
            )

            result = await SandboxExecutionBackendService(
                docker_command=str(Path(temp_dir) / "missing-docker"),
            ).run(payload)

            self.assertEqual(result["status"], "infrastructure_error")
            self.assertEqual(result["execution"]["runtime"], "docker")
            self.assertEqual(result["failure"]["kind"], "docker_runtime_unavailable")
            self.assertFalse(result["execution"]["workspace_isolated"])
            self.assertFalse(result["execution"]["network_isolated"])

            events: list[dict] = []

            async def collect(event: dict) -> None:
                events.append(event)

            await SandboxExecutionBackendService(
                docker_command=str(Path(temp_dir) / "missing-docker"),
            ).stream_run(payload, collect)
            unavailable_event = next(
                event for event in events if event["stage"] == "docker_unavailable"
            )
            self.assertEqual(
                unavailable_event["metadata"]["user_action_required"],
                "docker_runtime_choice",
            )
            self.assertEqual(
                unavailable_event["metadata"]["options"],
                ["use_local_copy", "retry_docker", "cancel"],
            )

    async def test_docker_command_preserves_relative_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            payload = SandboxExecutionRunRequest.model_validate(
                {
                    "task_id": "sandbox_docker_cwd",
                    "workspace": {"repo_root": str(repo_root)},
                    "test_files": [
                        {
                            "path": "tests/test_docker_cwd.py",
                            "content": "assert True\n",
                        }
                    ],
                    "command": {
                        "argv": ["python", "-m", "pytest", "tests"],
                        "cwd": "backend",
                    },
                    "execution_policy": {
                        "runtime": "docker",
                        "network": "deny",
                    },
                },
            )
            service = SandboxExecutionBackendService(
                docker_command="/usr/bin/docker",
            )

            docker_argv = service._build_docker_run_command(
                payload=payload,
                command=payload.command,
                sandbox_root=repo_root / "copy",
                container_name="ai-ide-bridge-test",
                relative_command_cwd="backend",
            )

            self.assertEqual(docker_argv[docker_argv.index("--workdir") + 1], "/workspace/backend")
            self.assertIn("--network", docker_argv)
            self.assertEqual(docker_argv[docker_argv.index("--network") + 1], "none")

    async def test_docker_runtime_executes_through_the_same_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            docker_path = repo_root / "fake-docker"
            self._write_fake_docker(docker_path)
            payload = SandboxExecutionRunRequest.model_validate(
                {
                    "task_id": "sandbox_docker",
                    "workspace": {"repo_root": str(repo_root)},
                    "test_files": [
                        {
                            "path": "tests/test_docker.py",
                            "language": "python",
                            "framework": "pytest",
                            "content": "def test_docker():\n    assert True\n",
                        }
                    ],
                    "command": {
                        "argv": [
                            "python",
                            "-c",
                            "print('test command')",
                        ]
                    },
                    "execution_policy": {
                        "runtime": "docker",
                        "network": "deny",
                        "timeout_seconds": 10,
                    },
                },
            )
            events: list[dict] = []

            async def collect(event: dict) -> None:
                events.append(event)

            service = SandboxExecutionBackendService(
                docker_command=str(docker_path),
            )
            await service.stream_run(payload, collect)
            result = events[-1]["data"]

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["execution"]["runtime"], "docker")
            self.assertTrue(result["execution"]["workspace_isolated"])
            self.assertTrue(result["execution"]["network_isolated"])
            self.assertIn(
                "docker_check_started",
                [event["stage"] for event in events],
            )
            self.assertIn(
                "container_starting",
                [event["stage"] for event in events],
            )

    async def test_docker_runtime_timeout_uses_standard_timeout_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            docker_path = repo_root / "fake-docker"
            self._write_fake_docker(docker_path, sleep_on_run=True)
            payload = SandboxExecutionRunRequest.model_validate(
                {
                    "task_id": "sandbox_docker_timeout",
                    "workspace": {"repo_root": str(repo_root)},
                    "test_files": [
                        {
                            "path": "tests/test_docker_timeout.py",
                            "content": "def test_docker_timeout():\n    assert True\n",
                        }
                    ],
                    "command": {
                        "argv": ["python", "-c", "print('unused by fake docker')"],
                    },
                    "execution_policy": {
                        "runtime": "docker",
                        "network": "deny",
                        "timeout_seconds": 1,
                    },
                },
            )

            result = await SandboxExecutionBackendService(
                docker_command=str(docker_path),
            ).run(payload)

            self.assertEqual(result["status"], "timed_out")
            self.assertEqual(result["execution"]["runtime"], "docker")
            self.assertEqual(result["execution"]["termination_reason"], "timeout")

    async def test_docker_run_failure_is_infrastructure_error_with_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            docker_path = repo_root / "fake-docker"
            self._write_fake_docker(
                docker_path,
                run_exit_code=125,
                run_stderr="Cannot connect to the Docker daemon",
            )
            payload = SandboxExecutionRunRequest.model_validate(
                {
                    "task_id": "sandbox_docker_failure",
                    "workspace": {"repo_root": str(repo_root)},
                    "test_files": [
                        {
                            "path": "tests/test_docker_failure.py",
                            "content": "assert True\n",
                        }
                    ],
                    "command": {"argv": ["python", "tests/test_docker_failure.py"]},
                    "execution_policy": {
                        "runtime": "docker",
                        "network": "deny",
                        "timeout_seconds": 10,
                    },
                },
            )

            result = await SandboxExecutionBackendService(
                docker_command=str(docker_path),
            ).run(payload)

            self.assertEqual(result["status"], "infrastructure_error")
            self.assertEqual(
                result["execution"]["termination_reason"],
                "docker_execution_failed",
            )
            self.assertEqual(result["failure"]["kind"], "docker_execution_failed")
            self.assertIn("Cannot connect to the Docker daemon", result["failure"]["summary"])

    async def test_sandbox_execution_api_and_legacy_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            (repo_root / "source.txt").write_text("source", encoding="utf-8")
            async with app.router.lifespan_context(app):
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                ) as client:
                    standard_response = await client.post(
                        "/v1/sandbox-execution/runs",
                        json={
                            "task_id": "api_standard",
                            "workspace": {"repo_root": str(repo_root)},
                            "test_files": [
                                {
                                    "path": "tests/test_api.py",
                                    "content": "def test_api():\n    assert True\n",
                                }
                            ],
                            "command": {
                                "argv": [
                                    "python",
                                    "-c",
                                    "from pathlib import Path; "
                                    "assert Path('source.txt').read_text() == 'source'",
                                ]
                            },
                            "execution_policy": {
                                "network": "allow",
                                "timeout_seconds": 10,
                            },
                        },
                    )
                    standard_body = standard_response.json()
                    self.assertEqual(standard_response.status_code, 200)
                    self.assertTrue(standard_body["success"])
                    self.assertEqual(standard_body["data"]["status"], "passed")

                    validation_response = await client.post(
                        "/v1/sandbox-execution/runs",
                        json={
                            "task_id": "api_invalid_path",
                            "workspace": {"repo_root": str(repo_root)},
                            "test_files": [
                                {
                                    "path": "../outside.py",
                                    "content": "raise AssertionError\n",
                                }
                            ],
                            "execution_policy": {"network": "allow"},
                        },
                    )
                    validation_body = validation_response.json()
                    self.assertFalse(validation_body["success"])
                    self.assertEqual(
                        validation_body["error"]["code"],
                        "VALIDATION_ERROR",
                    )

                    legacy_response = await client.post(
                        "/v1/test-code-execution/runs",
                        json={
                            "input": {
                                "task_id": "api_legacy",
                                "repo_root": str(repo_root),
                                "test_files": [
                                    {
                                        "path": "tests/test_legacy.py",
                                        "language": "python",
                                        "framework": "pytest",
                                        "purpose": "兼容接口验证",
                                        "content": "def test_legacy():\n    assert True\n",
                                    }
                                ],
                                "test_command": "python -c \"print('legacy')\"",
                                "timeout_seconds": 10,
                            }
                        },
                    )
                    legacy_body = legacy_response.json()
                    self.assertTrue(legacy_body["success"])
                    self.assertTrue(legacy_body["data"]["passed"])
                    self.assertEqual(
                        legacy_body["data"]["sandbox"]["status"],
                        "passed",
                    )


if __name__ == "__main__":
    unittest.main()
