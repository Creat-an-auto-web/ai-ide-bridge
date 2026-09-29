# 端到端 TDD 后端流程

状态：已实现  
最后更新：`2026-09-07`

## 1. 对外入口

前端继续使用原有桥接协议：

```text
POST /v1/tasks
WS   /v1/tasks/{taskId}/events
```

`POST /v1/tasks` 接收用户需求、仓库路径、IDE 上下文和执行策略。默认
`BRIDGE_ENGINE=tdd`，因此同一个任务会由后端自动完成下面的全流程，不再要求
前端逐个调用阶段接口。

## 2. 状态机

```text
RequirementAnalysis
  -> TestCaseGeneration
  -> TestCodeGeneration (immutable baseline)
  -> CodeImplementation
  -> SandboxExecution
      -> passed -> PatchReady -> Completed
      -> failed -> CodeImplementationRepair -> SandboxExecution
      -> infrastructure/timeout -> Failed
      -> repair limit reached -> PatchReady -> Failed
```

关键规则：

- 测试用例覆盖正常、边界、非法输入、依赖失败和跨 story 集成路径。
- 测试代码先于业务实现生成，并在全部修复轮次中保持不变。
- 实现模型只能返回仓库内的业务文件完整内容，不能修改测试文件。
- 测试与实现文件只覆盖到隔离工作区副本，源仓库不会在执行过程中被写入。
- 每次失败都会把结构化测试摘要、失败测试和截断后的 stdout/stderr 交给实现修复阶段。
- 修复次数由 `TDD_MAX_REPAIR_ITERATIONS` 限制，默认 `3`，因此最多执行四轮测试。
- 只有 `passed` 会产生成功结果；超时和运行环境错误不会被误判为代码缺陷。

## 3. 前端收到的事件

后端沿用稳定的 bridge event：

- `task.plan`：六个端到端阶段。
- `task.log`：模型阶段、测试 stdout/stderr 和修复轮次。
- `task.test.result`：每轮测试的 passed / failed / skipped 统计，并附带 `iteration`。
- `task.patch`：最终业务实现和新增回归测试；每个文件包含 unified diff 与完整替换操作。
- `task.final`：最终 outcome 与结构化 artifacts。

`task.final.artifacts` 包含：

- `requirementSpec`
- `testPlan`
- `testCases`
- `generatedFiles`
- `testFiles`
- `attempts`
- `finalExecution`
- `workflowArtifacts`：一、二、三阶段的可预览文件清单与完整内容。IDE 可先写入
  `.preview-<task-id>` 目录供用户查看，再由用户选择保留到
  `ai-ide-artifacts/<task-id>/` 或清理预览文件。

## 4. 模型配置

最小配置：

```bash
export GLM_API_KEY=...
export GLM_MODEL=GLM-4.7-Flash
export GLM_API_BASE=https://api.z.ai/api/paas/v4
export BRIDGE_ENGINE=tdd
```

可选配置：

```bash
export GLM_PROVIDER_NAME=zhipu
export GLM_WIRE_API=chat_completions
export TDD_MODEL_TEMPERATURE=0.2
export TDD_MODEL_MAX_TOKENS=12000
export TDD_MODEL_TIMEOUT_SECONDS=60
export TDD_MODEL_MAX_REQUEST_SECONDS=900
export TDD_MAX_REPAIR_ITERATIONS=3
```

兼容模式：

```bash
export BRIDGE_ENGINE=openhands  # 使用旧 OpenHandsEngine
export BRIDGE_ENGINE=mock       # 使用联调 MockEngine
```

旧的 `USE_MOCK_ENGINE=true` 仍然生效。

## 5. 沙箱策略

- `workspaceMode=docker`：使用 Docker。
- `network=deny`：即使 workspaceMode 是 local，也升级到 Docker 以真正隔离网络。
- `workspaceMode=local` 且 `network=allow`：使用 `local_copy` 临时副本。

Docker 默认镜像只提供基础语言运行时。复杂项目应通过
`AI_IDE_BRIDGE_DOCKER_IMAGE` 指定已经安装项目依赖的镜像。Python 项目没有既有
pytest 配置时，测试代码阶段优先使用标准库 `unittest`，避免基础镜像缺少 pytest。

## 6. 代码位置

- 编排器：`backend-bridge/app/services/tdd_engine.py`
- 实现生成/修复代理：`tdd_agent_framework/agents/code_implementation/`
- 沙箱实现文件覆盖：`backend-bridge/app/models/sandbox_execution.py` 和
  `backend-bridge/app/services/sandbox_execution_service.py`
- 端到端测试：`backend-bridge/tests/test_tdd_engine.py`
