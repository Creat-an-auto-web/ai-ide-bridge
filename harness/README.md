# harness

`ai-ide-bridge` 的最小联通性验证脚本集合。

## bridge_smoke_test.mjs

这个脚本会验证一条最基本的端到端链路：

1. 通过 HTTP 创建任务
2. 通过 WebSocket 连接任务事件流
3. 打印收到的事件
4. 默认自动批准命令审批请求
5. 等待 `task.final`

它只依赖 Node 22 自带能力：

- `fetch`
- `WebSocket`

## 用法

先启动 `backend-bridge`，再执行：

```bash
node ai-ide-bridge/harness/bridge_smoke_test.mjs
```

可选环境变量：

```bash
BRIDGE_BASE_URL=http://127.0.0.1:27182
BRIDGE_TASK_MODE=fix_test
BRIDGE_REPO_PATH=/path/to/repo
BRIDGE_PROMPT="修复当前失败的测试"
BRIDGE_AUTO_APPROVE=1
BRIDGE_TIMEOUT_MS=30000
```

示例：

```bash
BRIDGE_REPO_PATH=/home/ricebean/ai-agent node ai-ide-bridge/harness/bridge_smoke_test.mjs
```

## WebSocket 前置条件

这个 smoke test 依赖后端支持 WebSocket 升级。

如果任务创建成功，但脚本在事件流阶段只报一个泛化的 `ErrorEvent`，常见原因是当前 `uvicorn` 运行环境缺少 WebSocket 后端支持。

常见修复方式：

```bash
pip install websockets
```

或者：

```bash
pip install wsproto
```

安装后重启后端，再重新执行 harness。

现在脚本会额外打印一次原始升级探测结果，方便直接定位这类问题。
