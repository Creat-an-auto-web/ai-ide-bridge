# 前端目录说明

`ai-ide-bridge/frontend/` 是当前项目唯一的前端工作区。

目录分工如下：

- `frontend-bridge/`
  - 前端桥接协议、客户端、状态归约器与独立 demo

- `void/`
  - 从上游 Void 复制进来的前端相关代码副本
  - 只在这份副本上做接入与联调，不直接改原始 `void/`
  - 当前本地 IDE 桌面前端入口也落在这里

- `local-ide-shell/`
  - 用于本地启动前端界面的壳层
  - 负责拉起 `backend-bridge` 与 `frontend-bridge/demo`

- `harness/`
  - 用于做前后端最小联通性验证的脚本

约束：

- 所有属于前端的代码、文档、测试壳、参考副本都应放在这个目录下
- `backend-bridge/` 仅保留后端桥接服务本身
