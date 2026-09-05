# 沙箱执行协议 v1

状态：草案  
最后更新：`2026-09-05`

## 1. 目标与边界

第四阶段只负责接收第三阶段交付的测试文件，在受控环境中执行，并返回可供 Repair 或人工审核消费的结构化结果。

它不负责：

- 重新拆解需求或修改 user story。
- 重新生成测试用例。
- 生成或修改生产实现代码。
- 自动决定是否接受需求分析结果。

当前协议名称为：

```text
sandbox-execution.v1
```

## 2. 与前序阶段的关系

第三阶段交付给第四阶段的最小稳定产物是：

- `test_files`
  - `path`
  - `content`
  - `language`
  - `framework`
  - `purpose`
  - `related_test_case_ids`

第四阶段不依赖第二、三阶段的内部实现类。需求包、测试用例结果和测试代码结果只能通过 `provenance` 追踪，不参与执行逻辑。

## 3. 标准请求

```json
{
  "protocol_version": "sandbox-execution.v1",
  "task_id": "task_login_001",
  "run_id": "exec_login_001",
  "workspace": {
    "repo_root": "/workspace/forum",
    "base_revision": "optional-git-sha"
  },
  "test_files": [
    {
      "path": "tests/test_login.py",
      "content": "def test_login():\n    assert True\n",
      "language": "python",
      "framework": "pytest",
      "purpose": "覆盖登录主流程",
      "related_test_case_ids": ["tc_login_success"]
    }
  ],
  "command": {
    "argv": ["python", "-m", "pytest", "tests/test_login.py", "-q"],
    "cwd": ".",
    "environment": {}
  },
  "execution_policy": {
    "runtime": "local_copy",
    "network": "allow",
    "timeout_seconds": 120,
    "max_output_bytes": 262144,
    "retain_artifacts": true,
    "allow_workspace_changes": false
  },
  "provenance": {
    "requirement_package_id": "ra_pkg_001",
    "test_case_result_id": "tc_result_001",
    "test_code_result_id": "code_result_001"
  }
}
```

### 3.1 命令规则

正式协议必须使用 `command.argv`，而不是以 shell 字符串作为核心接口。

```json
{
  "argv": ["python", "-m", "pytest", "tests/test_login.py"]
}
```

执行器不会使用 `bash -lc`。`cwd` 必须是相对沙箱工作区的路径，不能使用绝对路径或逃逸路径。

### 3.2 执行策略

`runtime` 当前预留：

- `local_copy`：将源工作区复制到临时目录后执行。隔离源工作区写入，但不能保证网络隔离。
- `docker`：未来正式沙箱运行时。目标是隔离网络、文件系统和资源。

当 `runtime=local_copy` 且 `network=deny` 时，服务会拒绝执行并返回 `infrastructure_error`，不会假装已隔离网络。

## 4. 标准响应

```json
{
  "protocol_version": "sandbox-execution.v1",
  "task_id": "task_login_001",
  "run_id": "exec_login_001",
  "status": "failed",
  "execution": {
    "command": {
      "argv": ["python", "-m", "pytest", "tests/test_login.py", "-q"],
      "cwd": "."
    },
    "runtime": "local_copy",
    "sandbox_id": "sandbox_001",
    "workspace_isolated": true,
    "network_isolated": false,
    "duration_ms": 1840,
    "exit_code": 1,
    "signal": null,
    "termination_reason": "test_failure"
  },
  "test_summary": {
    "framework": "pytest",
    "total": 4,
    "passed": 3,
    "failed": 1,
    "skipped": 0,
    "errors": 0,
    "failed_tests": ["tests/test_login.py::test_duplicate_email"],
    "passed_tests": []
  },
  "outputs": {
    "stdout": "",
    "stderr": "FAILED tests/test_login.py::test_duplicate_email",
    "output_truncated": false,
    "workspace_diff": "",
    "artifacts": ["tests/test_login.py"]
  },
  "failure": {
    "kind": "test_failure",
    "summary": "重复邮箱注册未返回预期错误。",
    "repair_targets": ["tests/test_login.py"],
    "related_test_case_ids": ["tc_login_duplicate"]
  },
  "warnings": [],
  "provenance": {
    "requirement_package_id": "ra_pkg_001",
    "test_case_result_id": "tc_result_001",
    "test_code_result_id": "code_result_001"
  }
}
```

## 5. 状态与终止原因

`status`：

- `passed`
- `failed`
- `timed_out`
- `cancelled`
- `blocked`
- `infrastructure_error`

常用 `termination_reason`：

- `test_passed`
- `test_failure`
- `timeout`
- `command_not_found`
- `command_start_failed`
- `network_isolation_unavailable`
- `docker_runtime_unavailable`
- `workspace_copy_failed`

测试断言失败、超时和运行环境不可用必须区分，Repair 只能针对可修复的测试失败继续运行。

## 6. 当前兼容路径

现有接口仍保留：

```text
POST /v1/test-code-execution/runs
```

它接收历史字段：

```json
{
  "input": {
    "task_id": "task_001",
    "repo_root": "/workspace/project",
    "test_files": [],
    "test_command": "python -m pytest tests/test_login.py",
    "timeout_seconds": 120
  }
}
```

后端会将其转换为 `sandbox-execution.v1` 请求，在 `local_copy + network=allow` 模式执行，并在原有响应中附带 `sandbox` 标准结果。

该兼容路径只用于现有前端和同事尚未交付的第三阶段代码。新接入应直接调用：

```text
POST /v1/sandbox-execution/runs
```

## 6.1 IDE 沙箱运行测试入口

IDE 提供“沙箱运行测试”入口，用于在第二、三阶段尚未可用、上游模型请求失败或上游输出格式不稳定时验证本阶段。

该入口：

- 不要求存在需求分析结果、测试用例生成结果或测试代码生成结果。
- 默认加载一个最小测试文件样例，也允许用户编辑测试文件路径、内容和命令。
- 通过 `WebSocket /v1/sandbox-execution/ws` 直接调用标准协议，不经过旧兼容接口。
- 在执行过程中推送工作区复制、测试文件准备、命令启动、命令运行心跳和命令输出事件。
- 展示执行状态、退出码、隔离状态、标准输出、标准错误、工作区差异和基础设施警告。
- 只验证第四阶段的执行协议与运行时，不代表第二、三阶段已经完成。

正式产品流程仍保持前序阶段门禁：

```text
测试用例生成 -> 测试代码生成 -> 沙箱执行
```

独立联调入口只是额外的测试接缝，不会放宽正式流程的阶段依赖。

事件的最小结构如下：

```json
{
  "type": "heartbeat",
  "stage": "command_running",
  "message": "测试命令仍在运行。",
  "elapsed_ms": 4200,
  "metadata": {
    "command_elapsed_ms": 4100
  }
}
```

最终结果通过 `type=result` 事件的 `data` 字段返回。同步接口
`POST /v1/sandbox-execution/runs` 仍然保留，适合不需要过程事件的服务端调用。

## 7. 当前限制与后续

当前已经做到：

- 测试文件只写入临时工作区副本，不回写用户源工作区。
- 本地项目中的 `node_modules` 会随副本复制，确保 JavaScript/TypeScript 测试命令可解析项目依赖；因此大型前端项目的本地副本准备时间会更长。
- 禁止测试文件路径逃逸。
- 结构化 `argv` 执行。
- 执行命令采用异步子进程管理，超时后终止进程组，不阻塞 API 事件循环等待测试结束。
- 最小环境变量白名单。
- 输出大小限制。
- 结构化失败与 Repair 目标。

当前尚未做到：

- Docker 容器隔离。
- 网络强制禁止。
- CPU、内存、进程数限制。
- 长时间保留沙箱和产物下载。
- 运行中取消接口与事件流。

`local_copy` 是用于联调和闭环验证的兼容运行时，不应作为不可信代码的正式隔离边界。正式环境应切换到 Docker runtime，并默认使用 `network=deny`。

Docker runtime 完成后，`network=deny` 才能成为默认安全策略。
