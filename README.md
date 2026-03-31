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

当前前后端通过桥接协议通信。

前端发起：

- `POST /v1/tasks`
  - 创建任务

- `GET /v1/tasks/{taskId}`
  - 查询任务

- `POST /v1/tasks/{taskId}/cancel`
  - 取消任务

- `POST /v1/tasks/{taskId}/commands/{commandId}/approval`
  - 提交命令审批结果

- `WS /v1/tasks/{taskId}/events`
  - 订阅任务事件流

后端返回事件包括：

- `task.status`
- `task.plan`
- `task.log`
- `task.command.request`
- `task.command.result`
- `task.patch`
- `task.test.result`
- `task.error`
- `task.final`

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
