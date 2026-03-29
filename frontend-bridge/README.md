# frontend-bridge

用于把 Void 与 `backend-bridge` 连接起来的前端桥接模块。

## 范围

这个包被有意放在 `void/` 之外。

它提供：

- 面向协议的 TypeScript 类型
- bridge 的 HTTP/WebSocket 客户端
- 任务事件状态归约器
- 面向 Void 的上下文适配接口

它不会直接修改 Void 内部实现。

## 快速开始

如果要运行独立的前端 demo：

1. 先在 `127.0.0.1:27182` 启动 `backend-bridge`
2. 执行：

```bash
npm run demo --prefix ai-ide-bridge/frontend-bridge
```

3. 打开：

```text
http://127.0.0.1:4310
```

如果要看最短运行路径，请看：

- [RUNNING.md](/home/ricebean/ai-agent/ai-ide-bridge/RUNNING.md)

## 主要入口

- `src/protocol.ts`
- `src/client.ts`
- `src/state.ts`
- `src/void-adapter.ts`

## 预期用法

1. 通过调用现有 Void 服务实现 `VoidBridgeContextSource`
2. 用 `buildVoidTaskRequest(...)` 构造 `CreateTaskRequest`
3. 使用 `BridgeClient`：
   - 创建任务
   - 订阅任务状态
   - 监听任务事件
   - 批准命令
   - 取消任务

## 最小示例

```ts
import { BridgeClient, buildVoidTaskRequest } from '@ai-ide-bridge/frontend-bridge'

const client = new BridgeClient({ baseUrl: 'http://127.0.0.1:27182' })

client.subscribe({
  onStateChange(state) {
    console.log(state)
  },
})

const request = await buildVoidTaskRequest(voidContextSource, {
  mode: 'fix_test',
  userPrompt: '修复当前失败的测试',
})

await client.createTask(request)
```
