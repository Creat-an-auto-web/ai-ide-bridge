# TDD 多智能体框架原型

这个目录用于承载不依赖 `backend-bridge/` 的后端框架原型代码。

当前目标不是直接接进现有运行链路，而是先把两类能力单独立住：

- 多智能体通用抽象
- 第一环 `RequirementAnalysisAgent`

当前包含：

- `core.py`
  - 通用 agent / provider 抽象
- `registry.py`
  - 智能体注册表
- `providers/`
  - 可绑定不同模型 API 的 provider 适配层
  - 当前先提供 OpenAI-compatible HTTP provider
- `agents/requirement_analysis/`
  - 第一环智能体的输入输出模型、提示词构造、解析器、质量检查器和 agent 实现
  - 已包含第一环专用的 GUI 配置对象与 service 工厂
- `tests/`
  - 最小单元测试

本地启动第一环原型服务：

```bash
cd /home/ricebean/ai-agent/ai-ide-bridge
python -m tdd_agent_framework.server --host 127.0.0.1 --port 27184
```

启动后：

- `GET /healthz`
- `POST /v1/requirement-analysis/runs`

前端 bridge 面板中的“运行第一环原型”按钮会调用这个服务。

这个原型层的设计原则是：

- 每个环节是独立智能体
- 每个智能体可以绑定不同 provider / model
- 编排器未来只做路由和状态流转，不吞并智能体内部逻辑

第一环当前支持的配置思路：

- IDE 图形界面逐项配置 `provider_name`
- IDE 图形界面逐项配置 `model`
- IDE 图形界面逐项配置 `api_base`
- IDE 图形界面逐项配置 `api_key`

当前原型先把这套配置能力落在第一环内部，不要求前端 UI 已经接通。
