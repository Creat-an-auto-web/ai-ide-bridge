# AI IDE Bridge 运行说明

这份文件给出当前仓库里桥接层的最短运行路径。

## 当前已有内容

- `backend-bridge/`
  - mock 后端桥接服务
  - HTTP 任务接口
  - WebSocket 任务事件流

- `frontend/frontend-bridge/`
  - 前端 bridge 模块
  - 可独立运行的 demo UI
  - 不修改原始 `void/`

- `frontend/void/`
  - Void 补丁层与原生启动器
  - 正式的原生 Void 前端启动入口

- `frontend/harness/`
  - 基于 CLI 的 HTTP + WebSocket smoke test

## 1. 启动后端

在仓库根目录执行：

```bash
cd ai-ide-bridge/backend-bridge
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 27182
```

注意：

- 当前 `uvicorn` 运行环境必须带有 WebSocket 后端支持
- 如果任务创建成功但事件流失败，请安装 `websockets` 或 `wsproto`
- 否则 WebSocket 升级请求会退化成普通 HTTP 请求，`/v1/tasks/{taskId}/events` 会表现为 `404`

启动后可检查：

```text
http://127.0.0.1:27182/healthz
```

期望返回：

```json
{"ok": true}
```

## 2. 启动前端 Demo

在另一个终端执行：

```bash
npm run demo --prefix ai-ide-bridge/frontend/frontend-bridge
```

然后打开：

```text
http://127.0.0.1:4310
```

这个前端 demo 服务会：

- 提供 `frontend-bridge/demo/` 下的页面
- 将 `/v1/*` HTTP 请求代理到 `backend-bridge`
- 将 `/v1/*` WebSocket 流量代理到 `backend-bridge`

这样可以在不修改后端的前提下保持浏览器同源。

## 2.5 启动原生 Void 前端

如果你要通过我们的桥接层启动 Void 原生前端，推荐执行：

```bash
npm run install:native-deps --prefix ai-ide-bridge/frontend/void
npm run start:native --prefix ai-ide-bridge/frontend/void
```

这条链路会自动：

- 启动 `backend-bridge`
- 创建 `frontend/.runtime/void-native/` 运行时副本
- 覆盖 `frontend/void` 中的 bridge 补丁
- 映射 `frontend/frontend-bridge/src`
- 在运行时副本中执行 `npm run buildreact`
- 在运行时副本中执行 `npm run watch`
- 调用 Void 自己的 `./scripts/code.sh` 打开原生开发窗口

注意：

- 这不是我们自建的 Web 壳，而是 Void 原生开发窗口
- 首次安装依赖耗时较长
- 原始 `void/` 目录不会被改写，所有运行态内容都在 `frontend/.runtime/void-native/`
- 启动前请先确保 Node 版本符合 `void/.nvmrc`，当前要求为 `20.18.2`
- 如果在 Linux / WSL 安装依赖时报 `gssapi/gssapi.h` 缺失，需要安装 `libkrb5-dev`

如果你还想打开旧的浏览器 demo，可执行：

```bash
npm run start:browser-demo --prefix ai-ide-bridge/frontend/local-ide-shell
```

## 3. Demo 操作流程

在 demo 页面中：

1. 填写 `Repo Root Path`
2. 选择 `Mode`
3. 输入 `Prompt`
4. 点击 `Create Task`

随后你应该能看到：

- 任务状态变化
- 计划步骤
- 日志
- 命令审批请求
- patch 输出
- 测试结果
- 最终结果

## 4. CLI Smoke Test

如果你想走一条不依赖 UI 的验证路径：

```bash
node ai-ide-bridge/frontend/harness/bridge_smoke_test.mjs
```

常用覆盖参数：

```bash
BRIDGE_REPO_PATH=/home/ricebean/ai-agent \
BRIDGE_PROMPT="修复当前失败的测试" \
node ai-ide-bridge/frontend/harness/bridge_smoke_test.mjs
```

## 5. 当前边界

当前可运行的前端位于：

- `ai-ide-bridge/frontend/frontend-bridge`
- `ai-ide-bridge/frontend/void`
- 原始 UI 由 Void 原生前端承载
- 不依赖修改原始 `void/`
- 不依赖 `backend-bridge` 内部实现细节

这是有意为之。

桥接集成主线已经切到：

- 用 `frontend/void` 提供对 Void 原生前端的最小补丁
- 用 `frontend/frontend-bridge` 提供桥接状态机、协议客户端和宿主服务适配
- 用 `frontend/void/scripts/native-launcher.mjs` 把两者注入原始 Void 运行副本

## 6. 排查建议

如果 demo 页面能打开，但任务创建失败：

- 确认 `backend-bridge` 正在监听 `27182`
- 确认 `/healthz` 可访问
- 确认 `Repo Root Path` 不为空

如果任务创建成功，但没有事件出现：

- 确认后端 WebSocket 端点可达
- 检查前端 demo 服务是否仍在运行
- 查看浏览器控制台和后端终端日志
- 如果 `uvicorn` 日志里出现 `No supported WebSocket library detected`，请安装 `websockets` 或 `wsproto` 后重启后端

如果命令审批出现了，但任务没有继续：

- 检查是否启用了自动审批
- 或手动点击批准按钮

如果 `npm run start:native --prefix ai-ide-bridge/frontend/void` 无法启动：

- 先确认 `void/` 依赖已安装成功
- 确认当前 Node 版本接近 `void/.nvmrc` 中要求的 `20.18.2`
- 查看 `frontend/.runtime/void-native/void` 下是否已经生成 `node_modules/`
- 查看终端里 `watch` 是否已经出现 `Finished compilation` 和 `Finished compilation extensions`
- 如果 `npm install` 卡在 `kerberos`，优先检查 `libkrb5-dev` 是否已安装，以及当前 Node 版本是否错误地使用了 `22.x`

## 7. 最小文件地图

- `ai-ide-bridge/backend-bridge/app/main.py`
- `ai-ide-bridge/frontend/frontend-bridge/demo/server.mjs`
- `ai-ide-bridge/frontend/frontend-bridge/demo/index.html`
- `ai-ide-bridge/frontend/frontend-bridge/demo/app.js`
- `ai-ide-bridge/frontend/void/scripts/native-launcher.mjs`
- `ai-ide-bridge/frontend/void/src/vs/workbench/contrib/void/browser/react/src/bridge/useAiIdeBridge.tsx`
- `ai-ide-bridge/frontend/void/src/vs/workbench/contrib/void/browser/react/src/bridge/AiIdeBridgePanel.tsx`
- `ai-ide-bridge/frontend/harness/bridge_smoke_test.mjs`
