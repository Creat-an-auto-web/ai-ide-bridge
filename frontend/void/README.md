# void 对照代码

这个目录用于存放从上游 Void 复制过来的、当前桥接项目确实需要参考和对接的代码副本。

当前已复制的文件如下：

- `src/vs/workbench/contrib/void/browser/sidebarPane.ts`
  - Void 侧边栏的真实挂载入口
  - 用于确认本地 IDE 中 sidebar 的注册和挂载方式

- `src/vs/workbench/contrib/void/browser/terminalToolService.ts`
  - Void 现有终端工具服务
  - 用于确认 terminal tail、持久终端和命令执行相关接口

- `src/vs/workbench/contrib/void/browser/react/src/util/services.tsx`
  - Void React 侧服务访问层
  - 用于确认 `useAccessor()` 可拿到哪些真实服务对象

- `src/vs/workbench/contrib/void/browser/react/src/sidebar-tsx/SidebarChat.tsx`
  - Void 现有 sidebar 主组件
  - 用于分析真实 UI 接入点和交互结构

- `src/vs/workbench/contrib/void/browser/react/src/sidebar-tsx/Sidebar.tsx`
- `src/vs/workbench/contrib/void/browser/react/src/sidebar-tsx/index.tsx`
- `src/vs/workbench/contrib/void/browser/react/src/sidebar-tsx/ErrorBoundary.tsx`
- `src/vs/workbench/contrib/void/browser/react/src/util/mountFnGenerator.tsx`
- `src/vs/workbench/contrib/void/browser/react/src/styles.css`
  - 这些文件共同构成 sidebar 的最小挂载链
  - 当前已经在这份副本里接入 `AI IDE Bridge` 面板

- `src/vs/workbench/contrib/void/browser/react/src/bridge/*`
  - 这是我们在项目目录内新增的桥接接入层
  - 它通过 `useAccessor()` 调用真实 Void 风格的服务接口
  - 并把 bridge 面板并入复制出来的 sidebar 接入位

说明：

- 这里复制的是“当前桥接项目需要用到的最小必要文件集”，不是完整镜像原始 `void/`
- 这些文件的作用是为 `ai-ide-bridge` 内的桥接开发提供本地参考副本
- 后续如果桥接层确实需要更多 Void 文件，再按实际依赖继续补充
- 目前这份副本已经不是单纯参考代码，而是包含了“并入 Void 接口后的最小联调版本”
