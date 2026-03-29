# Sidebar Controller 说明

这份说明解释如何使用面向 UI 的 controller 骨架，相关文件在：

- `src/examples/sidebar-controller.ts`

这个文件的意义在于，避免你在每个 sidebar 组件里都从原始 bridge 事件重新推导一遍 UI 状态。

## 1. 它解决什么问题

原始 bridge 状态是面向协议的。

而 sidebar 通常更想拿到面向 UI 的状态，例如：

- 当前 prompt
- 已选择的任务模式
- Run 按钮是否可用
- 当前任务的高层摘要
- 是否应该显示审批卡片
- 可直接渲染的扁平日志列表
- patch 预览数据
- 最终摘要文本

`BridgeSidebarController` 会把后端任务状态转换成这种形态。

## 2. 状态结构

这个 controller 会产出 `BridgeSidebarPanelState`，其中包含：

- `composer`
- `summary`
- `approval`
- `planSteps`
- `logs`
- `patch`
- `testSummary`
- `finalSummary`
- `errorMessage`

这个结构被有意设计得贴近 sidebar 组件真正需要渲染的数据。

## 3. 推荐用法

1. Create a `VoidBridgeContextSource`
2. 创建 `BridgeSidebarController`
3. 订阅 controller 的状态变化
4. 将 UI 事件绑定到：
   - `setPrompt(...)`
   - `setMode(...)`
   - `runCurrentPrompt(...)`
   - `approvePendingCommand(...)`
   - `rejectPendingCommand(...)`
   - `cancelTask()`

## 4. Host 侧最小示例

```ts
import {
  BridgeSidebarController,
  BridgeClient,
  createVoidBridgeContextSource,
} from '@ai-ide-bridge/frontend-bridge'

const client = new BridgeClient({ baseUrl: 'http://127.0.0.1:27182' })
const contextSource = createVoidBridgeContextSource(voidHostServices)

const controller = new BridgeSidebarController({
  bridgeClient: client,
  contextSource,
})

const dispose = controller.subscribe((state) => {
  renderSidebar(state)
})

controller.setPrompt('修复当前失败的测试')
controller.setMode('fix_test')
await controller.runCurrentPrompt()
```

## 5. 为什么这一层很重要

没有这一层的话，你的 Void sidebar 胶水代码通常会把这些东西混在一起：

- prompt 输入状态
- 后端连接状态
- 协议事件处理
- UI 派生布尔值
- 审批动作绑定

这样很快就会变得难以维护。

这个 controller 把职责拆成：

- `BridgeClient` 负责协议逻辑
- `VoidBridgeContextSource` 负责收集 Void 上下文
- `BridgeSidebarController` 负责 sidebar 渲染状态

这三层最好保持彼此分离。
