# Requirement Composition Verification v1 草案

状态：草案
最后更新：`2026-05-11`

## 1. 目标

这份文档定义需求分析阶段中的“组合合理性验证”会话。

它对应当前推进计划中的第 3 步：

- 在需求分析的验证闭环里设计一个新会话
- 根据原始需求
- 从集成测试角度检查整组 `User Story` 组合起来是否合理

这里要解决的问题不是“单条 story 写得好不好”，而是：

- 这组 story 能不能拼成完整业务闭环
- 是否遗漏关键路径
- capability 分组与 story 切分是否一致
- 依赖顺序是否支撑端到端交付
- 从集成测试视角是否存在关键断点

## 2. 为什么不能直接复用 RequirementVerification

当前已有的 `RequirementVerification` 更偏向：

- 检查单轮需求拆解是否清晰
- 检查 story 是否可测试
- 检查 story 粒度、依赖和叙事质量

它的关注点仍然主要是“单条 story 质量”和“单轮拆解质量”。

而组合合理性验证的关注点不同：

- 检查整组 story 是否覆盖原始需求主路径
- 检查 capability group 与 story 集合是否形成完整能力域
- 检查多个 story 拼起来是否能支撑集成测试闭环
- 检查缺失的跨 story 场景、权限场景、异常场景和顺序场景

因此建议将它定义为独立会话，而不是硬塞进现有 `RequirementVerificationAgent`。

## 3. 职责边界

组合合理性验证负责：

- 审查 `RequirementSpec`、`capability_groups`、`story_units` 的整体覆盖性
- 审查主流程、异常流程、权限流程是否被 story 集合覆盖
- 审查依赖顺序是否能支持端到端交付
- 提出缺失 story、冗余 story、冲突 story、顺序错误等问题
- 输出从集成测试视角构造出的关键验证场景

组合合理性验证不负责：

- 改写单条 story 文案
- 直接重做需求分析
- 输出实现方案
- 直接生成测试代码

## 4. 输入对象

建议定义独立输入对象：

```json
{
  "session_id": "comp_verify_001",
  "task_id": "task_001",
  "iteration": 1,
  "analysis_input": {
    "user_prompt": "为任务列表增加 CSV 导出能力，并确保权限和失败反馈合理。",
    "workspace_summary": {
      "languages": ["typescript", "python"],
      "frameworks": ["react", "fastapi", "pytest"],
      "key_modules": ["frontend/tasks", "app/tasks", "tests/tasks"]
    },
    "execution_constraints": {
      "disallow_new_dependencies": true,
      "preserve_public_api": true,
      "max_capability_groups": 6,
      "max_story_units": 24
    }
  },
  "analysis_result": {
    "requirement_spec": {},
    "capability_groups": [],
    "story_units": [],
    "verification": {}
  }
}
```

### 4.1 输入字段说明

- `session_id`
  - 当前组合验证会话的唯一标识
- `task_id`
  - 需求分析任务标识
- `iteration`
  - 当前验证轮次
- `analysis_input`
  - 原始需求和工作区摘要
- `analysis_result`
  - 当前需求分析产物
  - 必须至少包含：
    - `requirement_spec`
    - `capability_groups`
    - `story_units`
    - 当前 `verification`

## 5. 输出对象

建议输出独立 verdict，而不是沿用现有 `RequirementVerificationResult`。

```json
{
  "status": "pass|revise|blocked",
  "summary": "...",
  "coverage_assessment": {
    "covers_primary_user_goal": true,
    "covers_permission_constraints": false,
    "covers_failure_handling": false,
    "covers_end_to_end_flow": false
  },
  "composition_issues": [
    {
      "id": "issue_missing_permission_guard",
      "severity": "high",
      "issue_type": "missing_story",
      "message": "导出主流程存在，但缺少权限限制 story，无法保证只有仓库管理员可执行导出。",
      "related_story_ids": ["story_export_selected_records"],
      "related_capability_group_ids": ["capability_export_flow"],
      "suggested_action": "add_story"
    }
  ],
  "integration_test_scenarios": [
    {
      "id": "it_export_success",
      "title": "管理员按当前筛选条件导出成功",
      "covers_story_ids": ["story_export_selected_records"],
      "covers_capability_group_ids": ["capability_export_flow"],
      "expected_outcome": "下载结果与当前筛选条件一致"
    }
  ],
  "redundant_story_ids": [],
  "missing_story_topics": [
    "导出权限控制",
    "导出失败反馈"
  ],
  "revision_guidance": [
    "补充一条专门的导出权限控制 story",
    "补充一条导出失败反馈 story",
    "重新检查 capability group 是否覆盖异常路径"
  ]
}
```

## 6. 状态语义

### 6.1 `pass`

表示：

- 当前 story 集合已覆盖主业务目标
- capability group 与 story 分层基本一致
- 可以构造出完整的端到端验证场景
- 没有阻塞性缺口

### 6.2 `revise`

表示：

- 当前 story 集合存在可修复缺口
- 还不适合直接进入下一阶段
- 但可以通过补 story、拆 story、调依赖、补异常路径来修正

### 6.3 `blocked`

表示：

- 当前信息不足以完成组合验证
- 或原始需求存在关键缺失
- 或 story 集合和 requirement spec 严重冲突

## 7. 关键检查维度

建议该会话至少覆盖下面 6 个维度。

### 7.1 主路径覆盖

问题：

- 原始需求的核心业务目标是否被至少一条 capability group 和一组 story 覆盖

### 7.2 权限与约束覆盖

问题：

- requirement spec 中的角色、权限、约束是否被 story 明确承载

### 7.3 异常路径覆盖

问题：

- 是否缺少失败反馈、回退路径、边界输入处理类 story

### 7.4 跨 story 闭环完整性

问题：

- 多条 story 拼起来后，是否能形成完整流程
- 是否只覆盖了局部动作，没有形成结果闭环

### 7.5 capability 分组合理性

问题：

- capability group 是否只是“故事分桶”
- 还是已经形成能力域分层
- group 和 story 的边界是否一致

### 7.6 集成测试可构造性

问题：

- 当前 story 集合能否支撑端到端测试场景
- 是否存在必须跨 story 才能验证、但当前故事集合无法拼起来的空洞

## 8. `composition_issues` 建议枚举

建议 `issue_type` 至少支持：

- `missing_story`
- `redundant_story`
- `conflicting_story`
- `dependency_gap`
- `dependency_order_error`
- `missing_permission_path`
- `missing_failure_path`
- `missing_integration_path`
- `capability_group_misaligned`
- `scope_coverage_gap`

建议 `suggested_action` 至少支持：

- `add_story`
- `split_story`
- `merge_story`
- `adjust_dependency`
- `move_story_between_groups`
- `clarify_scope`

## 9. `integration_test_scenarios` 的意义

这个字段是组合合理性验证的核心产物之一。

它的作用不是直接生成测试代码，而是明确：

- 哪些 story 组合起来构成一个完整场景
- 该场景验证什么业务闭环
- 预期结果是什么

这会直接服务后续阶段：

- 测试生成
- Story 组合复核
- 用户反馈定位

## 10. 与第 4 步用户反馈入口的关系

组合合理性验证输出会直接影响后续用户交互设计。

例如：

- `missing_story_topics`
  - 可以提示用户补充全局需求说明
- `composition_issues.related_story_ids`
  - 可以允许用户对具体 story 提交反馈
- `integration_test_scenarios`
  - 可以让用户选择“我认为这个集成场景不合理”

因此，第 3 步的输出协议必须先定，才能更稳地推进第 4 步。

## 11. 当前建议

建议实现上采用独立结构：

- `RequirementVerificationAgent`
  - 继续负责单轮拆解质量验证

- `RequirementCompositionVerificationAgent`
  - 负责组合合理性验证

这样做的好处是：

- 职责边界更清楚
- prompt 更聚焦
- 输出对象更稳定
- 后续用户反馈能更精准映射到“全局问题”还是“单条 story 问题”

## 12. 下一步建议

如果认可这份协议草案，后续实现顺序建议是：

1. 定义 `RequirementCompositionVerificationInput/Result` 数据模型
2. 编写独立 prompt builder
3. 加一组最小 golden 样例
4. 再决定是否接入现有 orchestrator 的第二类验证阶段
