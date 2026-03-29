# demo

`frontend-bridge` 的可运行前端 demo。

这个 demo 完全位于 `frontend-bridge` 内，不会修改：

- `void/`
- `backend-bridge`

## 工作方式

`server.mjs` 会做两件事：

1. 提供 demo 的 HTML/CSS/JS
2. 代理：
   - HTTP `/v1/*`
   - WebSocket `/v1/*`

到现有的 `backend-bridge` 进程。

这样可以在不修改后端 CORS 的前提下保持浏览器同源。

## 启动方式

1. 先在 `127.0.0.1:27182` 启动 `backend-bridge`
2. 执行：

```bash
npm run demo --prefix ai-ide-bridge/frontend-bridge
```

3. 打开：

```text
http://127.0.0.1:4310
```

## 环境变量

```bash
FRONTEND_BRIDGE_PORT=4310
BACKEND_BRIDGE_HOST=127.0.0.1
BACKEND_BRIDGE_PORT=27182
```
