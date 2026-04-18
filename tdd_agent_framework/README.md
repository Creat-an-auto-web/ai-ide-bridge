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
- `agents/requirement_analysis/`
  - 第一环智能体的输入输出模型、提示词构造、解析器、质量检查器和 agent 实现
- `tests/`
  - 最小单元测试

这个原型层的设计原则是：

- 每个环节是独立智能体
- 每个智能体可以绑定不同 provider / model
- 编排器未来只做路由和状态流转，不吞并智能体内部逻辑
