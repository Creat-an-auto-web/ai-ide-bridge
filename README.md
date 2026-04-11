# AI IDE Bridge

本项目的目标不是重做一套新的 IDE 前端，而是通过我们自己的桥接层，把 Void 原生客户端接到目标 AI 执行后端。

当前项目已经可以：

- 通过 `frontend/void` 启动 Void 原生开发客户端
- 在 Void 原生前端中挂载我们的桥接侧栏
- 将用户输入与 Void 上下文组装为桥接协议请求
- 通过 HTTP 和 WebSocket 与 `backend-bridge` 通信

当前项目还没有完成：

- 将 `backend-bridge` 真正接到 OpenHands
- 让任务在 OpenHands 中真实执行

这意味着当前链路已经具备“前端桥接联通能力”，但后端执行仍然是 mock。

## 当前状态

截至目前，项目的真实状态如下：

- `frontend/void`
  - 已经是正式的 Void 原生前端入口
  - 不是自建 Web 页面
  - 会以运行时副本方式启动 Void 原生客户端

- `frontend/frontend-bridge`
  - 已实现桥接协议类型
  - 已实现 HTTP / WebSocket 协议客户端
  - 已实现任务状态归约与侧栏状态控制器
  - 已实现从 Void 宿主服务采集上下文并构造请求

- `backend-bridge`
  - 已提供桥接协议接口
  - 已支持任务创建、事件流、命令审批、取消任务
  - 但当前实际执行引擎仍是 `MockEngine`
  - 还没有接 OpenHands

因此，当前实际链路是：

`Void 原生前端输入 -> frontend-bridge -> backend-bridge -> MockEngine`

而不是：

`Void 原生前端输入 -> frontend-bridge -> backend-bridge -> OpenHands`

## 项目结构

- `backend-bridge/`
  - 后端桥接服务
  - 当前提供协议接口与 mock 执行引擎

- `frontend/`
  - 当前项目唯一的前端工作区

- `frontend/frontend-bridge/`
  - 前端桥接模块
  - 负责协议、客户端、状态控制、Void 宿主适配

- `frontend/void/`
  - Void 原生前端补丁层与原生启动器
  - 通过运行时副本方式启动 Void 原生客户端

- `frontend/harness/`
  - 面向桥接协议的最小联通测试脚本

- `frontend/local-ide-shell/`
  - 早期本地壳层尝试
  - 当前正式入口已经切到 `frontend/void`

- `RUNNING.md`
  - 运行路径与排查说明

## 前端实现

前端部分分为两层：

- `frontend/frontend-bridge`
  - 抽象桥接协议与前端状态逻辑
  - 不直接依赖 Void 内部实现细节

- `frontend/void`
  - 将 `frontend-bridge` 接到 Void 原生前端
  - 负责以最小补丁方式把桥接侧栏注入 Void

### 设计原则

前端实现遵循以下原则：

- 不直接修改原始 `/void`
- 所有接入逻辑都放在 `ai-ide-bridge/frontend/` 下
- 不是重做 UI，而是复用 Void 原生前端
- 将“桥接协议逻辑”与“Void 接入逻辑”拆开
- 前端应尽量只依赖稳定的宿主能力，而不是硬编码 Void 内部业务流程

### `frontend-bridge` 的职责

`frontend/frontend-bridge` 是前端桥接层核心。

它当前已经实现：

- 协议类型定义
  - 文件：`src/protocol.ts`
  - 定义任务请求、事件流、审批、补丁、测试结果等结构

- 协议客户端
  - 文件：`src/client.ts`
  - 负责：
    - `POST /v1/tasks`
    - `GET /v1/tasks/{taskId}`
    - `POST /v1/tasks/{taskId}/cancel`
    - `POST /v1/tasks/{taskId}/commands/{commandId}/approval`
    - `WS /v1/tasks/{taskId}/events`

- 状态归约
  - 文件：`src/state.ts`
  - 负责把后端事件流归约成前端可消费状态

- Void 上下文适配骨架
  - 文件：`src/examples/void-source-skeleton.ts`
  - 负责从 Void 宿主采集：
    - 仓库根目录
    - 当前文件
    - 当前选区
    - 已打开文件
    - 诊断信息
    - git diff
    - 终端尾部输出
    - 测试日志

- 侧栏控制器
  - 文件：`src/examples/sidebar-controller.ts`
  - 负责：
    - 管理输入框 prompt
    - 管理任务 mode
    - 点击运行时构造任务请求
    - 监听后端状态变化
    - 管理审批、日志、补丁、最终结果等侧栏状态

- Void 宿主桥
  - 文件：
    - `src/void-runtime.ts`
    - `src/void-host-bridge.ts`
    - `src/void-real-entry.ts`
    - `src/void-real-services.ts`
  - 负责把真实 Void 服务对象转成桥接层可消费的宿主接口

### `frontend-bridge` 的工作逻辑

前端桥接层当前的运行逻辑是：

1. 从 Void 宿主服务采集 IDE 上下文
2. 组装 `CreateTaskRequest`
3. 发起 `POST /v1/tasks`
4. 建立 `WebSocket /v1/tasks/{taskId}/events`
5. 持续接收：
   - 状态变化
   - 计划
   - 日志
   - 命令审批请求
   - 命令结果
   - patch
   - 测试结果
   - 最终结果
6. 将这些事件归约成侧栏状态
7. 在 Void 侧栏中呈现

### 当前前端已经支持的功能

当前前端桥接层已经具备：

- 在 Void 原生前端中显示桥接侧栏
- 输入 prompt 并发起任务
- 选择任务 mode
- 自动采集当前仓库与编辑器上下文
- 展示任务状态与连接状态
- 展示计划步骤
- 展示日志输出
- 展示命令审批卡片
- 审批或拒绝命令
- 展示补丁摘要
- 展示测试结果摘要
- 展示最终结果或错误信息

### 当前前端尚未完成的部分

前端虽然已经可以把请求正确发到后端，但还存在边界：

- 当前显示的 patch / test / final 都来自 mock 后端
- 还没有真正消费 OpenHands 返回的数据结构
- 还没有完成“OpenHands 特有事件流 -> 当前桥接协议”的正式适配
- 还没有完成更深的 Void 原生功能并入
  - 例如更完整的 SCM / 测试运行器 / 终端 / 工作区联动

### `frontend/void` 的职责

`frontend/void` 不是新的前端工程，而是：

- Void 原生前端的补丁层
- 运行时启动器
- 桥接层注入入口

它当前主要负责：

- 将最小必要补丁覆盖到运行时 Void 副本
- 将 `frontend-bridge/src` 映射到运行时副本中
- 启动后端桥接服务
- 构建 Void React 前端
- 构建 Void 客户端主进程产物
- 调用 Void 自己的 `scripts/code.sh`
- 打开 Void 原生开发客户端

### `frontend/void` 的关键入口

- [scripts/native-launcher.mjs](/home/ricebean/ai-agent/ai-ide-bridge/frontend/void/scripts/native-launcher.mjs)
  - 原生启动器

- [useAiIdeBridge.tsx](/home/ricebean/ai-agent/ai-ide-bridge/frontend/void/src/vs/workbench/contrib/void/browser/react/src/bridge/useAiIdeBridge.tsx)
  - Void 侧 React hook 入口

- [AiIdeBridgePanel.tsx](/home/ricebean/ai-agent/ai-ide-bridge/frontend/void/src/vs/workbench/contrib/void/browser/react/src/bridge/AiIdeBridgePanel.tsx)
  - 桥接侧栏面板

- [SidebarWithAiIdeBridge.tsx](/home/ricebean/ai-agent/ai-ide-bridge/frontend/void/src/vs/workbench/contrib/void/browser/react/src/sidebar-tsx/SidebarWithAiIdeBridge.tsx)
  - 将桥接面板并入 Void 侧栏

### Void 原生前端中的桥接逻辑

当前 Void 原生侧的工作逻辑如下：

1. Void React 组件通过 `useAccessor()` 读取 Void 宿主服务
2. `useAiIdeBridge()` 调用 `attachVoidRealIdeSidebarFromAccessor(...)`
3. `frontend-bridge` 将 Void 服务对象映射为宿主接口
4. `BridgeSidebarController` 管理整个桥接侧栏的状态与操作
5. `AiIdeBridgePanel` 负责把这些状态渲染到 Void 侧栏里

这意味着我们并没有绕开 Void，也没有另做一个浏览器壳，而是把桥接能力直接挂进了 Void 原生前端中。

## 前后端通信方式

当前前后端不是“直接把一段自然语言扔给后端然后等结果”，而是通过一套显式的桥接协议通信。

这套桥接协议由两部分组成：

- 控制面
  - 通过 HTTP 发起任务、审批命令、取消任务、查询任务

- 事件面
  - 通过 WebSocket 持续接收任务生命周期事件

也就是说，桥接层的通信模型是：

1. 前端先用 HTTP 创建任务
2. 后端返回 `taskId`
3. 前端再基于 `taskId` 建立 WebSocket 事件流
4. 后端不断把该任务的状态变化推送回来
5. 如果中途需要用户批准命令，前端再用 HTTP 把批准结果发回后端

### 协议文件在哪里

这套协议的前端定义在：

- [protocol.ts](/home/ricebean/ai-agent/ai-ide-bridge/frontend/frontend-bridge/src/protocol.ts)

前端客户端实现在：

- [client.ts](/home/ricebean/ai-agent/ai-ide-bridge/frontend/frontend-bridge/src/client.ts)

后端接口实现在：

- [tasks.py](/home/ricebean/ai-agent/ai-ide-bridge/backend-bridge/app/api/tasks.py)

后端任务管理与审批状态实现在：

- [task_service.py](/home/ricebean/ai-agent/ai-ide-bridge/backend-bridge/app/services/task_service.py)

后端事件总线实现在：

- [event_bus.py](/home/ricebean/ai-agent/ai-ide-bridge/backend-bridge/app/services/event_bus.py)

前端事件归约实现在：

- [state.ts](/home/ricebean/ai-agent/ai-ide-bridge/frontend/frontend-bridge/src/state.ts)

### 传输层是怎么分工的

#### 1. HTTP 负责命令式操作

前端通过 HTTP 执行这些一次性动作：

- `POST /v1/tasks`
  - 创建任务

- `GET /v1/tasks/{taskId}`
  - 查询任务当前快照

- `POST /v1/tasks/{taskId}/cancel`
  - 取消任务

- `POST /v1/tasks/{taskId}/commands/{commandId}/approval`
  - 提交命令审批结果

这些动作都带有明确的请求体和响应体，适合“我要发起一个动作”的场景。

#### 2. WebSocket 负责连续事件流

前端通过：

- `WS /v1/tasks/{taskId}/events`

建立长连接，持续接收任务过程中的事件。

这适合：

- 状态变化
- 日志流
- 计划步骤
- 审批请求
- patch
- 测试结果
- 最终结果

如果只用 HTTP 轮询，这些信息会变得很笨重；当前桥接层明确选择了“创建任务走 HTTP，过程事件走 WebSocket”的模型。

### 前端到底发了什么

当用户在 Void 侧栏里输入 prompt 并点击运行时，前端不会只发一段字符串，而是会组装一个 `CreateTaskRequest`。

它包含几个核心部分：

- `requestId`
  - 前端生成的请求 ID
  - 便于跟踪一次发起动作

- `sessionId`
  - 可选会话 ID

- `protocolVersion`
  - 当前为 `v1alpha1`

- `mode`
  - 任务模式
  - 例如 `fix_test`、`edit_selection`、`repo_chat`

- `userPrompt`
  - 用户在 Void 中输入的自然语言任务

- `repo`
  - 仓库信息
  - 包括：
    - `rootPath`
    - `branch`

- `context`
  - IDE 上下文
  - 包括：
    - `activeFile`
    - `selection`
    - `openFiles`
    - `diagnostics`
    - `gitDiff`
    - `terminalTail`
    - `testLogs`

- `policy`
  - 执行策略
  - 包括：
    - `workspaceMode`
    - `network`
    - `requireApprovalFor`
    - `maxDurationSec`
    - `maxOutputBytes`
    - `writablePaths`
    - `envAllowlist`

这些字段不是后端自己猜的，而是由前端桥接层通过 `VoidBridgeContextSource` 主动采集，再调用 `buildVoidTaskRequest(...)` 组装出来。

对应实现可看：

- [void-adapter.ts](/home/ricebean/ai-agent/ai-ide-bridge/frontend/frontend-bridge/src/void-adapter.ts)
- [void-source-skeleton.ts](/home/ricebean/ai-agent/ai-ide-bridge/frontend/frontend-bridge/src/examples/void-source-skeleton.ts)

### 一次完整通信是怎么发生的

当前桥接协议的一次完整交互，大致是下面这个顺序：

1. 用户在 Void 面板输入 prompt
2. `BridgeSidebarController` 调用 `VoidBridgeController.runTask(...)`
3. 前端从 Void 宿主采集上下文
4. 前端构造 `CreateTaskRequest`
5. `BridgeClient.createTask(...)` 发送 `POST /v1/tasks`
6. 后端创建 `taskId`，保存任务请求，并立即返回任务记录
7. 前端拿到 `taskId` 后，马上连接 `WS /v1/tasks/{taskId}/events`
8. 后端通过 `EventBus` 推送：
   - `task.status`
   - `task.plan`
   - `task.log`
   - `task.command.request`
   - `task.command.result`
   - `task.patch`
   - `task.test.result`
   - `task.error`
   - `task.final`
9. 前端每收到一个事件，就用 `applyBridgeEvent(...)` 归约到本地状态
10. 侧栏 UI 根据归约后的状态刷新显示

这就是 README 里说的“通过桥接协议通信”的具体含义。

### 响应体和事件体长什么样

#### 1. HTTP 响应统一包一层 `ResponseEnvelope`

后端不会直接返回裸数据，而是统一返回：

- `success`
- `requestId`
- `data`
- `error`
- `protocolVersion`

这样前端可以统一处理成功与失败。

#### 2. WebSocket 事件统一包一层 `EventEnvelope`

每个事件都至少带这些字段：

- `eventId`
- `taskId`
- `seq`
- `type`
- `timestamp`
- `payload`

这里最关键的是：

- `taskId`
  - 用来说明这个事件属于哪个任务

- `seq`
  - 用来保证同一任务事件的顺序

- `type`
  - 用来决定这是什么事件

- `payload`
  - 真正的业务内容

### 事件顺序是怎么保证的

后端不是随便往 WebSocket 里写消息，而是先经过 `EventBus`。

`EventBus` 当前做了三件事：

- 为每个 `taskId` 分配独立的订阅队列
- 为每个 `taskId` 维护递增的 `seq`
- 为每个 `taskId` 保存一份历史事件列表

这意味着：

- 每个任务的事件都有单独序号
- WebSocket 新连接建立后，后端会先把该任务的历史事件补发一遍
- 再继续推送新的实时事件

这能解决两个问题：

- 前端连接建立得稍晚，也不会错过前面的状态
- 前端可以用 `seq` 避免重复处理旧事件

对应实现见：

- [event_bus.py](/home/ricebean/ai-agent/ai-ide-bridge/backend-bridge/app/services/event_bus.py)
- [tasks.py](/home/ricebean/ai-agent/ai-ide-bridge/backend-bridge/app/api/tasks.py)

前端在 `applyBridgeEvent(...)` 里也会检查：

- 如果 `event.seq <= prev.highestSeq`
  - 直接忽略

这就是当前协议层的幂等保护。

### 命令审批是怎么往返的

命令审批是当前桥接协议里最重要的一条闭环。

执行顺序如下：

1. 后端在任务执行过程中发现某个命令需要审批
2. 后端调用 `request_command_approval(...)`
3. 后端：
   - 把任务状态设为 `awaiting_approval`
   - 发布 `task.command.request`
   - 为该命令创建一个 `Future`
4. 前端通过 WebSocket 收到 `task.command.request`
5. 前端侧栏显示审批卡片
6. 用户点击“批准”或“拒绝”
7. 前端发送：
   - `POST /v1/tasks/{taskId}/commands/{commandId}/approval`
8. 后端收到 HTTP 请求后：
   - 找到对应命令记录
   - 更新命令状态
   - 结束等待中的 `Future`
9. 执行引擎继续向下运行

也就是说：

- 审批请求是事件流下发
- 审批结果是 HTTP 回传

这是一个典型的“异步请求 + 显式确认”的桥接协议回路。

### 前端是怎么把事件变成 UI 的

前端不会把 WebSocket 收到的 JSON 直接渲染。

当前流程是：

1. `BridgeClient` 收到原始事件
2. 调用 `applyBridgeEvent(...)`
3. 归约到 `BridgeState`
4. `BridgeSidebarController` 再把 `BridgeState` 映射成面板状态
5. `AiIdeBridgePanel` 用这个面板状态渲染 UI

例如：

- `task.plan`
  - 会变成侧栏里的计划步骤列表

- `task.command.request`
  - 会变成审批卡片

- `task.patch`
  - 会变成 patch 摘要与文件列表

- `task.final`
  - 会变成最终结果摘要

所以桥接协议不只是“传消息”，还负责把后端任务过程转换成前端可消费的状态机。

### 这套协议目前的真实边界

当前这套协议已经在“前端桥接到后端”的层面打通了，但还有两个边界要明确：

- 第一，当前后端引擎仍是 mock
  - 协议是通的
  - 执行不是真的 OpenHands

- 第二，当前协议是我们项目内部定义的桥接协议
  - 不是 OpenHands 原生协议
  - 如果后续接 OpenHands，需要再做一层后端适配

所以当前 README 中说“通过桥接协议通信”，准确含义是：

- Void 原生前端不直接对接 OpenHands
- 而是先把用户输入和 IDE 上下文包装成我们定义的桥接协议
- 再由 `backend-bridge` 根据这套协议接收、编排、回传事件

## 当前与 OpenHands 的关系

这个问题必须明确：

- 当前前端已经能把 Void 客户端输入发送到我们的桥接后端
- 当前后端还不能把它真正交给 OpenHands 执行

原因是：

- `backend-bridge` 当前挂接的是 `MockEngine`
- 它只会模拟计划、日志、审批、patch 和最终结果
- 还没有实现 `OpenHandsEngine` 或等价适配层

所以当前真实能力是：

- Void 输入可以发到桥接后端
- 但不能真正驱动 OpenHands 执行任务

## 当前最短启动方式

如果要启动 Void 原生客户端并带上桥接层：

```bash
npm run install:native-deps --prefix ai-ide-bridge/frontend/void
npm run start:native --prefix ai-ide-bridge/frontend/void
```

这条链路当前会：

1. 创建或复用 `frontend/.runtime/void-native/void` 运行时副本
2. 覆盖 `frontend/void` 中的补丁文件
3. 映射 `frontend/frontend-bridge/src`
4. 自动启动 `backend-bridge`
5. 构建 Void React 前端
6. 构建 Void 客户端主进程产物
7. 调用 Void 原生 `code.sh`
8. 打开 Void 原生开发客户端

## 环境要求

当前已知要求包括：

- Node 版本与 `void/.nvmrc` 一致
  - 当前要求 `20.18.2`

- Python 环境可运行 `backend-bridge`
  - 当前启动器会优先使用仓库根目录 `.venv/bin/python`

- Linux / WSL 需要安装原生依赖

在 Debian / Ubuntu / WSL Ubuntu 上，至少建议：

```bash
sudo apt-get install build-essential g++ libx11-dev libxkbfile-dev libsecret-1-dev libkrb5-dev python-is-python3
```

如果后端事件流无法建立，还需要确认当前 Python 环境中已安装：

```bash
websockets
wsproto
```

## 当前限制

当前项目最重要的限制有三条：

- 后端仍是 mock，不能真实调用 OpenHands
- 前端桥接虽然已嵌入 Void，但仍处于联调阶段
- 当前启动链主要面向开发态，而不是最终打包分发态

## 下一阶段工作

如果要把项目推进到真正可交付，后续重点应放在：

- 将 `backend-bridge` 从 `MockEngine` 切换到 OpenHands 适配实现
- 建立 OpenHands 任务接口到当前桥接协议的映射
- 明确命令审批、日志、patch、测试结果、最终总结的字段转换
- 继续完善 Void 宿主上下文采集
- 补充启动说明、联调说明与错误排查文档

## 相关文档

- [RUNNING.md](/home/ricebean/ai-agent/ai-ide-bridge/RUNNING.md)
- [frontend/README.md](/home/ricebean/ai-agent/ai-ide-bridge/frontend/README.md)
- [frontend/frontend-bridge/README.md](/home/ricebean/ai-agent/ai-ide-bridge/frontend/frontend-bridge/README.md)
- [frontend/void/README.md](/home/ricebean/ai-agent/ai-ide-bridge/frontend/void/README.md)
