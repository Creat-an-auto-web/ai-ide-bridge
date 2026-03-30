# Void 接入说明

这份文档说明当前仓库中的前端 bridge 应当如何连接到现有 Void 接口，同时不在这里直接修改 `void/`。

## 1. 集成边界

`frontend-bridge` 不是 UI。

它是一个独立的适配层，负责：

- 理解 bridge 协议载荷
- 根据来自 Void 的上下文构造请求
- 与 `backend-bridge` 通信

真正的 Void 侧集成代码应当写在你们产品侧自己的 bridge 胶水层里，再去调用这个模块。

## 2. 推荐的 Void 服务映射

### 2.1 当前文件与选区

可使用：

- `ICodeEditorService.getActiveCodeEditor()`
- `editor.getModel()`
- `editor.getSelection()`

映射为：

- `model.uri.fsPath` -> `context.activeFile`
- 编辑器选区 -> 协议里的 `Selection`

### 2.2 已打开文件

可使用：

- `IModelService.getModels()`

映射为：

- 每个 `model.uri.fsPath` -> `context.openFiles[]`

### 2.3 仓库根目录

可使用：

- `IWorkspaceContextService.getWorkspace().folders[0]?.uri.fsPath`

映射为：

- 根目录路径 -> `repo.rootPath`

### 2.4 诊断信息

可使用：

- `IMarkerService.read({ resource })`

映射为：

- marker 列表 -> `context.diagnostics[]`

### 2.5 终端输出

可使用：

- `ITerminalToolService.listPersistentTerminalIds()`
- `ITerminalToolService.readTerminal(id)`

映射为：

- 最近的终端文本 -> `context.terminalTail`

### 2.6 Git Diff

第一阶段：

- 如果你还没有稳定的 SCM 集成，可以先允许这里为空字符串

后续：

- 增加专门的 SCM 适配层，并把 diff 文本映射到 `context.gitDiff`

### 2.7 测试日志

第一阶段：

- 允许为空字符串，或者直接从终端输出中提取

后续：

- 增加专门的测试运行器适配层，并把结构化输出映射到 `context.testLogs`

## 3. 第一阶段集成闭环

1. Implement `VoidHostServices`
2. 用 `createVoidBridgeContextSource(...)` 创建 `VoidBridgeContextSource`
3. 用 `buildVoidTaskRequest(...)` 构造请求
4. 调用 `BridgeClient.createTask(...)`
5. 订阅 client 状态和事件
6. 渲染：
   - 任务状态
   - 计划
   - 日志
   - 命令审批
   - patch 预览
   - 最终结果

## 4. 最小示例

```ts
import {
  BridgeClient,
  VoidBridgeController,
  createVoidBridgeContextSource,
} from '@ai-ide-bridge/frontend-bridge'

const client = new BridgeClient({ baseUrl: 'http://127.0.0.1:27182' })

const contextSource = createVoidBridgeContextSource({
  getRepoRootPath: () => workspaceRoot,
  getActiveModel: () => activeModel,
  getActiveSelection: () => activeSelection,
  getOpenModels: () => openModels,
  getDiagnosticsForFile: (filePath) => readMarkers(filePath),
  getGitDiff: () => '',
  getTerminalTail: () => terminalTail,
  getTestLogs: () => '',
})

const controller = new VoidBridgeController(client, contextSource)

client.subscribe({
  onStateChange(state) {
    console.log(state)
  },
})

await controller.runTask({
  mode: 'fix_test',
  userPrompt: '修复当前失败的测试',
})
```
