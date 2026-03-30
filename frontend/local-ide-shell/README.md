# 本地 IDE 启动壳

这个目录提供一个最小桌面壳，用来把：

- `backend-bridge`
- `frontend-bridge/demo`

组合成一个可以直接启动的本地界面窗口。

## 作用

它不是最终产品形态，也不是要替代真正的 Void 桌面应用。

它的目标是让当前桥接项目先达到下面这个状态：

- 可以一条命令启动
- 会自动拉起后端和前端代理
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
- 启动前端代理
- 调用系统默认浏览器打开本地界面

如果本机的 Electron 已正确安装，也可以启动桌面窗口版本：

```bash
npm run start:desktop --prefix ai-ide-bridge/frontend/local-ide-shell
```

## 可选环境变量

```bash
BRIDGE_PYTHON=python
BRIDGE_BACKEND_PORT=27182
BRIDGE_FRONTEND_PORT=4310
```

## 说明

- 默认会在本机启动 `backend-bridge`
- 默认会在本机启动 `frontend-bridge/demo/server.mjs`
- 默认界面地址是 `http://127.0.0.1:4310`
- `start` 走系统浏览器打开路径
- `start:desktop` 走 Electron 桌面窗口路径
- 结束进程时会尝试一起关闭后台子进程
