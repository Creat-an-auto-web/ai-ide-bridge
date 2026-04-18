# AI IDE Bridge React 接入层

这个目录存放的是基于复制进来的 Void React 代码副本补出来的接入层文件。

当前包含：

- `useAiIdeBridge.tsx`
  - 基于 `useAccessor()` 取到的真实服务对象创建 bridge
  - 维护 bridge 面板状态、通知、patch review、workspace edit、最终摘要和错误信息

- `AiIdeBridgePanel.tsx`
  - 一个最小可运行的本地 IDE 面板骨架
  - 展示任务摘要、审批卡、计划、补丁预览、日志和最终结果
  - 已包含第一环 RequirementAnalysis 智能体的本地配置表单
    - 用户可在 IDE 图形界面中逐项填写 `provider`、`model`、`base_url`、`api_key`
  - 已包含“运行第一环原型”入口
    - 直接调用本地 `tdd_agent_framework.server` 原型服务

这两份文件的目标不是替代现有 `SidebarChat.tsx`，而是把：

- `ai-ide-bridge/frontend/frontend-bridge`
- `ai-ide-bridge/frontend/void/` 中复制出来的真实 Void 结构

接成一条更接近最终产品落位方式的路径。

后续如果要真正接进产品侧：

1. 在真实 Void 的 React sidebar 入口中调用 `useAiIdeBridge`
2. 或把 `AiIdeBridgePanel.tsx` 的状态绑定方式并入现有 sidebar 组件
3. 再根据产品需求决定是并行存在，还是替换现有某一块面板区域

当前在复制出来的 Void 副本里，还额外补了一个接近最终落位方式的容器：

- `../sidebar-tsx/SidebarWithAiIdeBridge.tsx`
  - 提供 `AI IDE Bridge` 和 `原始 Chat` 双视图切换
  - 用于模拟把 bridge 面板真正接入 sidebar 之后的产品形态
