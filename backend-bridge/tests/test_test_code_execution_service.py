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
