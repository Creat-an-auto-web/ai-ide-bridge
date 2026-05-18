from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.models.test_code_execution import TestCodeExecutionRunRequest
from app.services.test_code_execution_service import TestCodeExecutionBackendService


class TestCodeExecutionBackendServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_writes_files_and_collects_success_result(self) -> None:
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

            self.assertTrue((repo_root / "tests/test_sample.py").exists())
            self.assertTrue(result["passed"])
            self.assertEqual(result["evaluation"]["decision"], "success")
            self.assertEqual(result["artifacts"]["written_files"], ["tests/test_sample.py"])

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


if __name__ == "__main__":
    unittest.main()
