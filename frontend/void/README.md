# frontend/void 说明

这个目录不是重新实现一套前端，而是我们项目里的 Void 补丁层与启动器。

## 目录职责

- `src/vs/workbench/contrib/void/...`
  - 存放从原始 `void/` 复制进来的最小必要补丁文件
  - 这些文件会覆盖到运行时 Void 副本里
  - 其中真正属于桥接层的核心入口是：
    - `react/src/bridge/useAiIdeBridge.tsx`
    - `react/src/bridge/AiIdeBridgePanel.tsx`
    - `react/src/sidebar-tsx/SidebarWithAiIdeBridge.tsx`

- `scripts/native-launcher.mjs`
  - 原生 Void 启动器
  - 负责创建运行时副本、覆盖 bridge 补丁、映射 `frontend-bridge/src`，并按 Void 官方开发模式启动

- `scripts/build.mjs`
  - 仅用于之前的调试壳构建
  - 不是正式交付入口

- `src/local-host/*`
  - 仅保留为历史调试代码
  - 不再作为正式本地 IDE 入口继续推进

## 正式启动路径

当前推荐的正式启动方式是直接通过原生 Void 开发窗口启动：

```bash
npm run install:native-deps --prefix ai-ide-bridge/frontend/void
npm run start:native --prefix ai-ide-bridge/frontend/void
```

启动前请先确认：

- 当前 Node 版本与 `void/.nvmrc` 一致，当前要求是 `20.18.2`
- Linux / WSL 环境已经安装 Void 所需原生编译依赖
- 如果缺少 `gssapi/gssapi.h`，需要补齐 Kerberos 开发头文件

在 Debian / Ubuntu / WSL Ubuntu 上，至少应包含：

```bash
sudo apt-get install build-essential g++ libx11-dev libxkbfile-dev libsecret-1-dev libkrb5-dev python-is-python3
```

这条链路会做几件事：

1. 在 `ai-ide-bridge/frontend/.runtime/void-native/` 下创建一个 Void 运行时副本
2. 将本目录下的 Void 补丁文件覆盖到运行时副本
3. 将 `frontend/frontend-bridge/src` 映射到运行时副本旁路目录，供桥接层源码直接引用
4. 启动 `backend-bridge`
5. 在运行时副本里执行 `npm run buildreact`
6. 在运行时副本里执行 `npm run watch`
7. 调用运行时副本里的 `./scripts/code.sh`，打开 Void 原生开发窗口

## 重要边界

- 不修改原始 `../..../void/` 目录
- 不在这里重做一套 Web 前端
- 最终承载 UI 的是 Void 原生前端
- 我们只提供桥接补丁层和启动流程
