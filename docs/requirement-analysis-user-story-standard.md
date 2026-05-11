# RequirementAnalysis User Story 标准草案

状态：草案
最后更新：`2026-05-11`

## 1. 目标

这份文档定义需求分析阶段中 `User Story` 的标准写法与校验原则。

这里的“标准化”不只指 JSON 结构标准化，还包括：

- 字段结构标准化
- 内容表达标准化
- 粒度与业务语义标准化

如果只定义结构，不定义内容质量，模型很容易输出这种“结构对了但内容废了”的结果：

- `用户登录`
- `导出 CSV`
- `需求分析页面`
- `接入 Redis 缓存`

这些都不是合格的 `User Story`，最多只是：

- 功能主题
- 模块名
- 页面名
- 技术任务

## 2. 合格 User Story 的定义

一条合格的 `User Story` 应该是：

- 一个可独立讨论的业务能力切片
- 面向明确角色，而不是面向模块名
- 描述“谁在什么场景下需要什么能力，以及这样做带来什么业务结果”
- 自带可测试的验收标准
- 能与其他 story 组合成完整业务闭环

推荐统一使用四段式叙事模板：

```text
As a [role], when [context], I want [capability], so that [business outcome].
```

相比传统的三段式模板，这里显式加入 `when [context]`，目的是防止 story 漂成无边界的泛功能描述。

## 3. 直接拒绝的伪 Story 类型

以下内容不应被接受为合格 story：

### 3.1 只有功能名

- `用户登录`
- `导出 CSV`
- `任务筛选`

### 3.2 只有模块名或页面名

- `需求分析结果页`
- `审批面板`
- `导出模块`

### 3.3 纯技术任务

- `接入 Redis 缓存`
- `增加后端接口字段`
- `重构前端状态管理`

### 3.4 多个目标揉进一条

- `管理员可以筛选、导出、删除并重新同步记录`

这类描述的问题是：

- 无法独立验证
- 粒度过粗
- 无法精确给出用户反馈
- 难以和其他 story 组合做集成验证

## 4. 标准结果结构

建议需求分析结果中的 `story_units` 使用如下结构：

```json
{
  "id": "story_export_selected_records",
  "story_kind": "user_outcome",
  "title": "仓库管理员可以按当前筛选条件导出任务记录 CSV",
  "as_a": "仓库管理员",
  "when_context": "我已经在任务记录列表中设置筛选条件",
  "i_want": "导出当前筛选结果为 CSV 文件",
  "so_that": "我可以将审计数据用于汇报和离线分析",
  "narrative": "As a 仓库管理员, when 我已经在任务记录列表中设置筛选条件, I want 导出当前筛选结果为 CSV 文件, so that 我可以将审计数据用于汇报和离线分析。",
  "actor": "仓库管理员",
  "goal": "导出当前筛选结果为 CSV 文件",
  "business_value": "我可以将审计数据用于汇报和离线分析",
  "business_outcome": "用户得到与当前筛选结果一致的 CSV 文件",
  "scope": [
    "导出按钮触发",
    "筛选条件透传",
    "CSV 文件下载"
  ],
  "out_of_scope": [
    "异步任务导出",
    "Excel 格式导出"
  ],
  "acceptance_criteria": [
    "Given 用户已设置筛选条件, When 用户点击导出, Then 下载的 CSV 仅包含满足当前筛选条件的记录"
  ],
  "test_scenarios": [
    "正常导出当前筛选结果"
  ],
  "dependencies": [],
  "priority": "high",
  "risk": "medium",
  "open_questions": [],
  "implementation_hints": []
}
```

## 5. 字段级规范

### 5.1 `id`

- 必填
- 稳定唯一
- 仅用于引用，不承载主要业务语义
- 推荐格式：`story_<domain>_<action>`

### 5.2 `story_kind`

- 必填
- 用于标记 story 在业务闭环中的角色
- 建议枚举：
  - `user_outcome`
  - `admin_outcome`
  - `operator_outcome`
  - `compliance_guard`
  - `system_feedback`

### 5.3 `title`

- 必填
- 必须是“具体业务能力陈述”，不能只是短功能名
- 应尽量包含：
  - 角色或使用对象
  - 动作或能力
  - 业务对象
  - 必要边界

合格示例：

- `仓库管理员可以按当前筛选条件导出任务记录 CSV`
- `普通成员在无审批权限时只能查看需求分析结果而不能接受结果`
- `测试负责人可以针对单条 user story 提交修订意见`

不合格示例：

- `导出 CSV`
- `权限控制`
- `需求分析页面`
- `增加审批按钮`

### 5.4 `as_a`

- 必填
- 必须是具体角色
- 不应使用过于泛化的主语

合格示例：

- `仓库管理员`
- `普通成员`
- `测试负责人`

不合格示例：

- `用户`
- `系统`
- `前端`

### 5.5 `when_context`

- 必填
- 明确触发场景、前置条件或业务上下文
- 没有该字段，story 很容易漂成无边界能力

合格示例：

- `我已经在任务记录列表中设置筛选条件`
- `当前需求分析结果处于待接受状态`
- `我发现某条 user story 的验收标准不可测试`

不合格示例：

- `需要的时候`
- `在系统中`

### 5.6 `i_want`

- 必填
- 表达角色希望获得的业务能力
- 不得退化为实现动作

合格示例：

- `导出当前筛选结果为 CSV 文件`
- `对单条 user story 提交修订意见`

不合格示例：

- `后端返回导出接口`
- `新增一个按钮`

### 5.7 `so_that`

- 必填，除非确实不存在业务结果且有明确说明
- 必须表达业务价值或业务结果，不要写技术收益

合格示例：

- `我可以将审计数据用于汇报和离线分析`
- `我可以只修正问题 story 而不用整体重跑`

不合格示例：

- `代码更优雅`
- `方便后续开发`

### 5.8 `narrative`

- 必填
- 必须遵循统一四段式模板
- 必须与 `as_a` / `when_context` / `i_want` / `so_that` 语义一致

### 5.9 `actor`

- 必填
- 兼容字段
- 必须与 `as_a` 完全一致

### 5.10 `goal`

- 必填
- 兼容字段
- 必须与 `i_want` 完全一致

### 5.11 `business_value`

- 必填
- 兼容字段
- 必须与 `so_that` 完全一致

### 5.12 `business_outcome`

- 必填
- 强语义字段
- 用于描述这条 story 成立后外部可观察到的结果
- 比 `so_that` 更适合后续组合验证与集成测试

合格示例：

- `用户得到与当前筛选结果一致的 CSV 文件`
- `无审批权限的成员无法误触发接受操作`

### 5.13 `scope`

- 必填
- 描述本 story 覆盖哪些业务边界
- 不应写成详细实现步骤

### 5.14 `out_of_scope`

- 必填
- 明确本 story 不负责什么
- 用于防止 story 无限膨胀

### 5.15 `acceptance_criteria`

- 必填
- 必须可测试
- 推荐 `Given / When / Then`
- 建议 3 到 7 条

不合格示例：

- `体验良好`
- `导出应尽量快`
- `界面更清晰`

### 5.16 `test_scenarios`

- 必填
- 用于概括后续测试设计的关键场景
- 应服务于验证闭环，而不是重复业务口号

### 5.17 `dependencies`

- 必填
- 只能引用已有 story id
- 应表达业务流程依赖或闭环依赖

### 5.18 `priority`

- 必填
- 建议枚举：
  - `low`
  - `medium`
  - `high`

### 5.19 `risk`

- 必填
- 建议枚举：
  - `low`
  - `medium`
  - `high`

### 5.20 `open_questions`

- 选填
- 用于显式承载未决业务问题
- 不应把未定项偷偷混进 story 主体

### 5.21 `implementation_hints`

- 选填
- 可为后续阶段提供提示
- 不应反向主导 story 的业务定义

## 6. 最小判定标准

一条 story 只有同时满足下面条件，才算合格：

- 不是功能名、页面名、模块名或技术任务名
- `title` 是完整业务能力陈述
- `narrative` 同时包含角色、场景、能力、业务结果
- 只承载一个主要用户目标
- `acceptance_criteria` 可测试
- `scope` 与 `out_of_scope` 边界明确
- 可以与其他 story 组合成业务闭环

## 7. 建议加入质量检查器的拒绝规则

建议 `quality_checker` 在内容层面加入下面规则。

### 7.1 直接拒绝

- `title` 只是短功能名，如 `用户登录`、`导出 CSV`
- `title` 不包含动作语义
- `narrative` 缺少 `when_context`
- story 明显是技术任务
- 一条 story 同时包含多个并列主要目标
- `acceptance_criteria` 不是可测试行为陈述

### 7.2 给出 warning

- `as_a` 过于泛化，例如直接写 `用户`
- `so_that` 过弱，例如只写 `方便使用`
- `scope` 过大或 `out_of_scope` 为空
- capability group 只包含一条 story

## 8. 合格 / 不合格改写样例

### 8.1 示例一：用户登录

原始粗糙描述：

- `用户登录`

改写后：

- `title`
  - `注册用户可以使用邮箱和密码登录工作台`
- `narrative`
  - `As a 注册用户, when 我已经完成账号注册且尚未登录, I want 使用邮箱和密码登录工作台, so that 我可以访问自己的项目和任务数据。`

### 8.2 示例二：导出 CSV

原始粗糙描述：

- `导出 CSV`

改写后：

- `title`
  - `仓库管理员可以按当前筛选条件导出任务记录 CSV`
- `narrative`
  - `As a 仓库管理员, when 我已经在任务记录列表中设置筛选条件, I want 导出当前筛选结果为 CSV 文件, so that 我可以将审计数据用于汇报和离线分析。`

### 8.3 示例三：需求分析支持反馈

原始粗糙描述：

- `需求分析支持反馈`

建议拆成两条 story：

- `产品负责人可以追加全局需求约束以继续优化当前需求分析结果`
- `测试负责人可以针对单条 user story 提交修订意见`

## 9. 与后续协议的关系

这份规范会直接影响后续 4 类对象的设计与校验：

- `RequirementAnalysisResult.story_units`
- 用户追加的 `global_feedback`
- 用户针对单条 story 的 `story_feedback`
- 组合合理性验证产物 `composition_verification_result`

后续如果协议层正式落地：

- 建议把 `when_context`、`business_outcome`、`story_kind` 设为正式字段
- 建议在 `quality_checker` 中实现“伪 story 拒绝规则”
- 建议在验证闭环中增加从集成测试视角检查 story 组合合理性的独立会话
