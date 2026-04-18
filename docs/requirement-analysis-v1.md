# RequirementAnalysis v1 设计草案

状态：草案  
最后更新：`2026-04-18`

## 1. 目标

这份文档只讨论 TDD 智能体框架中的第一环：

- 接收用户原始需求
- 结合 IDE 与仓库上下文进行需求归一化
- 将大需求拆成可测试、可实现、可排序的 `StoryUnit`
- 输出给后续测试生成阶段消费

这里要开发的不是“聊天智能体”，而是一个稳定的后端阶段能力。

## 2. v1 交付目标

v1 只要求做到下面这些事情：

1. 定义稳定输入与输出 schema
2. 实现 `RequirementAnalysisService`
3. 输出 `RequirementSpec` 与 `StoryUnit[]`
4. 对输出结果做结构校验与质量校验
5. 产出可回放的阶段事件
6. 用金标样例做回归测试

v1 不要求做到：

- 多模型协同分析
- 自动查询外部知识库
- 自动改写测试
- 自主拆分成复杂任务图
- 高级长期记忆

## 3. 第一环的职责边界

第一环负责：

- 理解用户到底要解决什么问题
- 明确范围、约束、假设和非目标
- 把大需求拆成最小可执行需求单元
- 为每个需求单元补齐验收标准和测试关注点
- 输出依赖关系和优先级

第一环不负责：

- 直接生成测试代码
- 直接生成业务实现
- 直接运行沙箱
- 自己判断测试是否通过

## 4. 输入模型

建议第一环统一接收 `RequirementAnalysisInput`。

```json
{
  "task_id": "task_001",
  "mode": "repo_chat",
  "user_prompt": "修复登录后 token 刷新失效的问题，并保证失败时安全退出",
  "repo_root": "/workspace/project",
  "workspace_summary": {
    "languages": ["python"],
    "frameworks": ["fastapi", "pytest"],
    "key_modules": ["app/auth", "app/api", "tests/auth"]
  },
  "active_file": "app/auth/service.py",
  "selection": null,
  "open_files": ["app/auth/service.py", "tests/test_auth.py"],
  "diagnostics": [],
  "recent_test_failures": [
    "test_refresh_success expected token but got None"
  ],
  "git_diff_summary": "",
  "execution_constraints": {
    "disallow_new_dependencies": true,
    "preserve_public_api": true,
    "max_story_units": 8
  }
}
```

### 4.1 输入字段说明

- `task_id`
  - 任务标识
- `mode`
  - 当前 IDE 任务模式
- `user_prompt`
  - 用户原始需求
- `repo_root`
  - 仓库根目录
- `workspace_summary`
  - IDE 侧提供的仓库摘要，不要求很完整，但要足以辅助理解上下文
- `active_file`
  - 用户当前聚焦文件
- `selection`
  - 当前选区
- `open_files`
  - 用户当前打开文件
- `diagnostics`
  - 当前诊断信息
- `recent_test_failures`
  - 最近失败测试摘要
- `git_diff_summary`
  - 用户未提交改动的摘要
- `execution_constraints`
  - 来自任务策略或用户意图的执行约束

## 5. 输出模型

第一环建议同时输出两层结构：

- `RequirementSpec`
- `StoryUnit[]`

这样做的原因是：

- `RequirementSpec` 保留全局任务语义
- `StoryUnit[]` 给后续测试生成阶段直接消费

## 6. RequirementSpec

`RequirementSpec` 负责描述全局任务边界。

```json
{
  "task_id": "task_001",
  "version": 1,
  "problem_statement": "当前登录态在 access token 过期后无法自动刷新，导致用户被异常中断。",
  "product_goal": "恢复 token 自动刷新能力，并在刷新失败时安全退出。",
  "scope": [
    "refresh token 校验",
    "access token 刷新",
    "刷新失败后的会话处理"
  ],
  "out_of_scope": [
    "登录页 UI 改版",
    "权限系统重构"
  ],
  "constraints": [
    "保持现有对外接口不变",
    "不引入新的外部依赖"
  ],
  "assumptions": [
    "项目已有 refresh token 机制",
    "测试框架使用 pytest"
  ],
  "interfaces_or_contracts": [
    "refresh_session(user_id, refresh_token) -> SessionResult",
    "刷新失败时必须清理本地登录状态"
  ],
  "acceptance_criteria": [
    "access token 过期时系统会自动触发刷新",
    "刷新成功后新 token 会持久化",
    "刷新失败时用户会被安全登出"
  ],
  "decomposition_strategy": "按用户会话生命周期拆分 story unit"
}
```

### 6.1 RequirementSpec 质量要求

- 不允许空泛表述
- `scope` 与 `out_of_scope` 不能冲突
- `acceptance_criteria` 必须可被测试验证
- `interfaces_or_contracts` 应尽量贴近代码边界
- `constraints` 必须可被后续实现阶段使用

## 7. StoryUnit

`StoryUnit` 是后续测试生成阶段的最小消费单元。

```json
{
  "id": "story_auth_refresh_success",
  "title": "过期 token 自动刷新",
  "actor": "已登录用户",
  "goal": "在 access token 过期后自动完成刷新并恢复会话",
  "business_value": "减少用户登录中断",
  "scope": [
    "token expiry detection",
    "refresh session update"
  ],
  "out_of_scope": [
    "登录入口改造"
  ],
  "acceptance_criteria": [
    "当 access token 过期且 refresh token 有效时，系统自动请求新 token",
    "新 token 会写回存储",
    "刷新后后续请求使用新 token"
  ],
  "dependencies": [],
  "priority": "high",
  "risk": "medium",
  "test_focus": [
    "刷新成功路径",
    "token 持久化",
    "刷新后请求状态"
  ],
  "implementation_hints": [
    "优先检查 app/auth/service.py 中的 refresh_session 流程"
  ]
}
```

### 7.1 StoryUnit 最低字段

- `id`
- `title`
- `actor`
- `goal`
- `scope`
- `out_of_scope`
- `acceptance_criteria`
- `dependencies`
- `priority`
- `risk`
- `test_focus`

### 7.2 StoryUnit 质量要求

- 每个 `StoryUnit` 只描述一个清晰子能力
- `acceptance_criteria` 建议 3 到 7 条
- `dependencies` 不能形成明显环
- `test_focus` 必须服务于测试设计，不能只是业务口号
- 一个 `StoryUnit` 最好能在单轮实现-测试-修复中收敛

## 8. 输出封装对象

建议第一环最终返回：

```json
{
  "requirement_spec": {},
  "story_units": [],
  "analysis_summary": {
    "story_unit_count": 3,
    "high_priority_count": 1,
    "high_risk_count": 1
  },
  "warnings": [],
  "quality_checks": {
    "has_clear_scope": true,
    "has_testable_ac": true,
    "dependency_graph_valid": true,
    "story_count_within_limit": true
  }
}
```

## 9. 建议模块拆分

v1 不需要复杂，但需要边界清晰。

推荐拆成下面这些模块：

### 9.1 `domain/requirement_models.py`

职责：

- 定义 `RequirementAnalysisInput`
- 定义 `RequirementSpec`
- 定义 `StoryUnit`
- 定义 `RequirementAnalysisResult`

### 9.2 `services/requirement_analysis_service.py`

职责：

- 对外暴露 `analyze()` 主入口
- 串起整个第一环流程

### 9.3 `services/requirement_prompt_builder.py`

职责：

- 将 IDE 输入与约束整理成模型提示词
- 控制输出格式要求

### 9.4 `services/requirement_output_parser.py`

职责：

- 解析模型原始输出
- 做 schema 校验
- 转为内部对象

### 9.5 `services/requirement_quality_checker.py`

职责：

- 做非 schema 层面的质量校验
- 如：
  - story 是否过粗
  - acceptance criteria 是否不可测试
  - story 依赖是否异常

### 9.6 `services/story_dependency_resolver.py`

职责：

- 校验 `dependencies`
- 输出排序后的 story 顺序

### 9.7 `tests/requirement_analysis/`

职责：

- 存放金标样例
- 存放单元测试
- 存放质量校验测试

## 10. 建议流程

第一环的服务流程建议固定为：

```text
Input Normalize
  -> Prompt Build
  -> LLM Generate
  -> Output Parse
  -> Schema Validate
  -> Quality Check
  -> Dependency Resolve
  -> Emit Artifact
```

### 10.1 为什么需要 Quality Check

只做 schema 校验不够，因为模型很容易输出“结构对了但内容废了”的结果，比如：

- acceptance criteria 全是空话
- 一个 story 包含多个相互独立能力
- dependencies 乱写
- `out_of_scope` 和 `scope` 冲突

所以 v1 就应该加入质量检查层。

## 11. 服务接口建议

### 11.1 内部 Python 服务接口

```python
class RequirementAnalysisService:
    async def analyze(
        self,
        analysis_input: RequirementAnalysisInput,
    ) -> RequirementAnalysisResult:
        ...
```

### 11.2 编排器调用接口

建议编排器把第一环当作一个阶段能力调用：

```python
result = await requirement_analysis_service.analyze(analysis_input)
```

### 11.2.1 第一环模型配置来源

第一环不应把模型配置硬编码在后端代码里，而应允许 IDE 图形界面逐项配置。

建议第一环最小配置项为：

- `provider_kind`
- `provider_name`
- `model`
- `api_base`
- `api_key`
- `temperature`
- `max_tokens`
- `timeout_seconds`

其中：

- `api_base`
  - 由用户在 IDE 中填写，例如 OpenAI-compatible 网关地址
- `api_key`
  - 由用户在 IDE 中填写
- `provider_name`
  - 用于前端显示和后端路由
- `model`
  - 指定第一环实际使用的模型

这样后续即使测试生成智能体或代码生成智能体使用不同模型，也不会和第一环耦合。

建议前端对外展示时使用脱敏摘要对象，而不是直接回显完整 `api_key`。

### 11.3 阶段事件建议

第一环至少发出下面几类事件：

- `task.stage_changed`
- `task.artifact`
- `task.warning`
- `task.failed`

推荐事件载荷：

```json
{
  "type": "task.artifact",
  "taskId": "task_001",
  "stage": "requirement_analysis",
  "artifactType": "requirement_spec",
  "payload": {
    "problem_statement": "...",
    "story_unit_count": 3
  }
}
```

## 12. 金标测试设计

第一环最值得投入的是样例测试，而不是先追求大规模集成。

建议至少准备 10 到 20 个金标样例，覆盖下面几类任务：

### 12.1 缺陷修复类

示例：

- token 刷新失效
- 文件上传在边界条件下报错
- 缓存未失效导致旧数据展示

测试目标：

- 是否能提炼明确问题陈述
- 是否能拆出修复路径相关 story
- 是否能识别非目标

### 12.2 新功能类

示例：

- 增加导出 CSV 能力
- 为任务列表增加过滤条件
- 支持用户重试失败任务

测试目标：

- 是否能拆出多个独立 story
- 是否能识别依赖顺序
- 是否能给出可测试验收标准

### 12.3 重构类

示例：

- 拆分过大的 service 模块
- 统一错误处理逻辑

测试目标：

- 是否能识别行为不变约束
- 是否能把“重构”与“行为变更”分开

### 12.4 含上下文约束类

示例：

- 保持接口不变
- 不新增依赖
- 只修改指定目录

测试目标：

- 是否正确保留约束
- 是否把约束写进 `constraints`

## 13. 单元测试建议

建议至少覆盖下面这些测试。

### 13.1 schema 解析测试

验证：

- 缺字段时失败
- 字段类型错误时失败
- 枚举值非法时失败

### 13.2 质量校验测试

验证：

- acceptance criteria 是否可测试
- story 是否过粗
- scope / out_of_scope 是否冲突
- dependency 是否成环

### 13.3 金标回归测试

验证：

- 给定固定输入，输出满足预期结构和关键语义
- 关键 story 标题、依赖顺序、验收标准不漂移

### 13.4 降级测试

验证：

- 模型输出不合法 JSON 时是否能失败返回
- 输出 story 数量超限时是否会被拦截
- 某些字段缺失时是否有明确信息

## 14. 推荐目录草案

如果后端未来要实现这部分能力，建议目录大致这样组织：

```text
backend/
  requirement_analysis/
    domain/
      requirement_models.py
    services/
      requirement_analysis_service.py
      requirement_prompt_builder.py
      requirement_output_parser.py
      requirement_quality_checker.py
      story_dependency_resolver.py
    tests/
      fixtures/
        bugfix_token_refresh_input.json
        bugfix_token_refresh_expected.json
      test_output_parser.py
      test_quality_checker.py
      test_dependency_resolver.py
      test_requirement_analysis_golden.py
```

这里的目录只是推荐，不要求与现有 `backend-bridge` 目录一一对应。

## 15. v1 开发顺序

建议严格按下面顺序推进：

1. 先定义 schema
2. 再写 parser 和 quality checker
3. 再准备 10 到 20 个金标样例
4. 再实现 `RequirementAnalysisService`
5. 最后再接到 orchestrator 和前端事件

原因是：

- schema 不稳，后面都会漂
- quality checker 不先立住，模型输出会看起来“像对的”
- 没有金标样例，就无法判断第一环是否真的稳定

## 16. v1 成功标准

第一环 v1 做完后，至少应达到：

- 能稳定把原始需求转成 `RequirementSpec`
- 能输出一组可测试的 `StoryUnit`
- 输出结果可被 schema 校验与质量校验双重约束
- 关键样例的拆解结果可回归测试
- 前端或日志中能看到第一环阶段产物摘要

## 16.1 系统级评估标准

除了单次运行可用，还需要定义第一环的系统级评估标准。

建议至少统计：

- `title_recall`
  - 预期 story 标题的召回率
- `has_testable_ac`
  - 是否持续产出可测试的验收标准
- `dependency_graph_valid`
  - 依赖关系是否稳定合法
- `story_count_within_limit`
  - story 数量是否持续受控
- `pass_rate`
  - 在整组样例上达到“可接受拆解质量”的比例

当前建议阈值：

- `pass_rate >= 0.8`
- `title_recall >= 0.7`
- `has_testable_ac == 1.0`
- `dependency_graph_valid == 1.0`

评估脚本可独立执行，不依赖 IDE UI。

## 17. 结论

第一环现在完全可以开工，而且应该优先开工。

但第一环真正要做的不是“更会写 user story”，而是：

- 让需求结构化
- 让拆解可测试
- 让后续阶段有稳定输入
- 让整个 TDD 框架从第一步开始就可控

只要这一步做稳，后面的测试生成智能体就不是在“猜需求”，而是在消费一个已经被规整过的、可以执行的需求模型。
