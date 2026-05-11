# Requirement Feedback v1 草案

状态：草案
最后更新：`2026-05-11`

## 1. 目标

这份文档定义需求分析阶段中的用户反馈协议。

它对应当前推进计划中的第 4 步：

- 给用户提供交互入口
- 允许用户追加需求描述
- 允许用户针对单条 `User Story` 给出反馈意见

这里先定义协议与数据模型，不直接规定前端 UI 形态。

## 2. 为什么先定义协议

用户反馈如果没有协议约束，很容易退化成“重新说一遍需求”。

为了让后续系统能稳定消费反馈，反馈对象必须明确：

- 这是全局反馈，还是单条 story 反馈
- 它针对什么对象
- 它希望系统做什么动作
- 它应该如何映射回下一轮 `revision_focus`

## 3. 反馈分类

建议只定义两类正式反馈对象：

- `global_feedback`
- `story_feedback`

这样职责最清楚：

- 全局反馈用于修正整体边界、约束、优先级和业务背景
- Story 级反馈用于修正具体故事的粒度、验收标准、依赖和描述

## 4. `global_feedback`

### 4.1 适用场景

适用于：

- 补充业务背景
- 增加全局约束
- 修正范围边界
- 调整整体优先级
- 指出组合验证中的全局缺口

不适用于：

- 只修正单条 story 的 wording
- 只修正某个 story 的 AC

### 4.2 协议结构

```json
{
  "feedback_id": "gfb_001",
  "package_id": "reqpkg_001",
  "task_id": "task_001",
  "kind": "global_feedback",
  "author_role": "user",
  "feedback_type": "scope_adjustment",
  "feedback_text": "导出能力第一期只允许仓库管理员使用，普通成员暂不开放。",
  "applies_to": {
    "capability_group_ids": [],
    "story_ids": []
  },
  "expected_action": "refine_existing_stories",
  "created_at": "2026-05-11T12:00:00Z"
}
```

### 4.3 字段说明

- `feedback_id`
  - 反馈对象唯一标识
- `package_id`
  - 当前需求分析结果包标识
- `task_id`
  - 任务标识
- `kind`
  - 固定为 `global_feedback`
- `author_role`
  - 反馈发起方角色
- `feedback_type`
  - 反馈类型
- `feedback_text`
  - 用户自然语言反馈
- `applies_to`
  - 可选，用于关联某些 capability group 或 story，但不强制
- `expected_action`
  - 用户期待系统采取的动作
- `created_at`
  - 创建时间

## 5. `story_feedback`

### 5.1 适用场景

适用于：

- 某条 story 太粗或太细
- 某条 story 的验收标准不可测试
- 某条 story 的依赖不对
- 某条 story 的角色、场景或业务结果描述不准确

### 5.2 协议结构

```json
{
  "feedback_id": "sfb_001",
  "package_id": "reqpkg_001",
  "task_id": "task_001",
  "kind": "story_feedback",
  "author_role": "user",
  "story_id": "story_export_selected_records",
  "feedback_type": "granularity_issue",
  "feedback_text": "这条 story 太大了，应该把权限限制和导出成功路径拆开。",
  "expected_action": "split_story",
  "created_at": "2026-05-11T12:02:00Z"
}
```

### 5.3 字段说明

- `story_id`
  - 必填
  - 明确指出反馈针对哪条 story
- `feedback_type`
  - 用于标记问题类别
- `expected_action`
  - 指示系统更倾向拆分、改写、调整依赖还是补 AC

## 6. `feedback_type` 建议枚举

两类反馈共享一组主枚举即可：

- `scope_adjustment`
- `missing_case`
- `granularity_issue`
- `priority_change`
- `dependency_issue`
- `acceptance_issue`
- `wording_issue`
- `business_rule_update`

说明：

- `scope_adjustment`
  - 更适合全局反馈
- `granularity_issue`
  - 更适合 story 反馈
- `dependency_issue`
  - 两类反馈都可能出现

## 7. `expected_action` 建议枚举

建议支持：

- `refine_existing_stories`
- `add_story`
- `split_story`
- `merge_story`
- `adjust_dependency`
- `rewrite_acceptance_criteria`
- `clarify_scope`
- `reprioritize`

## 8. 如何映射回 `revision_focus`

这是第 4 步和前 3 步真正打通的关键。

### 8.1 全局反馈映射

`global_feedback` 应优先映射为：

- 下一轮 `revision_focus` 的高优先级全局指导语句
- 必要时补入 requirement spec 的 `constraints` / `scope` / `out_of_scope`

例如：

- 反馈：
  - `导出能力第一期只允许仓库管理员使用，普通成员暂不开放。`
- 映射后的 `revision_focus`：
  - `补充权限限制相关 story，并确保导出能力只对仓库管理员开放。`

### 8.2 Story 反馈映射

`story_feedback` 应优先映射为：

- 与 `story_id` 绑定的修订焦点
- 反馈中提到的粒度、AC、依赖问题

例如：

- 反馈：
  - `这条 story 太大了，应该把权限限制和导出成功路径拆开。`
- 映射后的 `revision_focus`：
  - `针对 story_export_selected_records 进行拆分，将导出成功路径与权限限制拆为独立 stories。`

## 9. 与组合验证输出的关系

第 4 步的反馈协议应能直接消费第 3 步的组合验证结果。

### 9.1 从 `missing_story_topics` 生成全局反馈入口

例如：

- 组合验证发现：
  - `导出权限控制`
  - `导出失败反馈`

此时前端可提示用户：

- 是否补充这两个全局缺口

### 9.2 从 `composition_issues.related_story_ids` 生成 story 反馈入口

例如：

- 某个组合问题指向：
  - `story_export_selected_records`

前端可直接为该 story 提供“补充意见”入口。

## 10. 当前建议

建议实现顺序如下：

1. 先将 `global_feedback` 与 `story_feedback` 定义成正式模型
2. 再决定是否把它们作为下一轮需求分析输入的一部分
3. 再实现前端 UI 入口

这样做可以避免：

- 前端先做了输入框，但后端没有稳定消费方式
- 反馈被简单拼接到 prompt 里，缺少结构语义

## 11. 下一步建议

如果认可这份协议，后续建议继续做：

1. 在 `tdd_agent_framework` 中补反馈数据模型
2. 在前端类型中补反馈对象定义
3. 定义一个最小的 `feedback -> revision_focus` 转换函数
4. 然后再考虑 UI 入口的具体交互形态
