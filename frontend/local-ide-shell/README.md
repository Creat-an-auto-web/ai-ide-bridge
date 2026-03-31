# 本地 IDE 启动壳

这个目录提供一个最小桌面壳，用来把：

- `backend-bridge`
- `frontend/void`

组合成一个可以直接启动的本地界面窗口。

## 作用

它不是最终产品形态，也不是要替代真正的 Void 桌面应用。

它的目标是让当前桥接项目先达到下面这个状态：

- 可以一条命令启动
- 会自动拉起后端
- 会自动构建 `frontend/void`
- 会打开本地桌面窗口
- 可以在窗口里直接验证 bridge 任务流

## 启动方式

先安装依赖：

```bash
npm install --prefix ai-ide-bridge/frontend/local-ide-shell
```

然后启动：

```bash
npm run start --prefix ai-ide-bridge/frontend/local-ide-shell
```

这条命令会：

- 启动后端
- 构建 `frontend/void` 本地前端
- 打开 Electron 桌面窗口

如果你只是想保留旧的浏览器 demo 路径，也可以执行：

```bash
npm run start:browser-demo --prefix ai-ide-bridge/frontend/local-ide-shell
```

## 可选环境变量

```bash
BRIDGE_PYTHON=python
BRIDGE_BACKEND_PORT=27182
BRIDGE_FRONTEND_PORT=4310
```

## 说明

- 默认会在本机启动 `backend-bridge`
- 默认会在本机构建并加载 `frontend/void/dist/index.html`
- `start` 与 `start:desktop` 都走 Electron 桌面窗口路径
- `start:browser-demo` 才会走旧的浏览器 demo 路径
- 结束进程时会尝试一起关闭后台子进程
