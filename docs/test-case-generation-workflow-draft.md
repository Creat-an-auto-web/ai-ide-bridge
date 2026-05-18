# 测试用例生成 Workflow Draft

状态：草案  
最后更新：`2026-05-18`

## 1. 目标

本文说明当前仓库里“需求分析 -> 测试用例生成”这一段前后联合 workflow 的目标、边界和建议用法，重点回答下面几个问题：

- 需求描述如何先生成概念性的测试用例，而不是直接写实现。
- 概念性测试用例和最终可执行测试代码之间有哪些 gap。
- 参数类型、参数组合、边界值和异常路径为什么容易漏。
- 以“注册功能”为例，正常业务流程应该长什么样。
- 前端现在应该如何把 `plan` 传给后端，后端又会返回什么。

## 2. 当前链路

当前仓库已经具备下面这条链路：

1. 前端完成需求分析，拿到 `RequirementAnalysisResult`。
2. 用户接受当前需求分析结果，或至少拿到已通过组合验证的结果。
3. 前端基于 `story_units + composition_verification` 自动生成一个 `workflow draft / plan`。
4. 前端把 `settings + input.plan + input.story_units` 发给 `POST /v1/test-case-generation/runs`。
5. 后端先产出测试计划和概念性测试用例，再用第二个 AI 对照 `plan` 生成 `completion_check`。

当前链路还不表示：

- 已经自动生成最终测试代码文件。
- 已经自动进入实现代码阶段。
- 已经自动运行 sandbox 执行和修复闭环。

## 3. 为什么先产出概念性测试用例

需求分析的产物是 `user story`，不是代码接口定义。这个阶段直接写测试代码，经常会遇到三个问题：

- 需求还没有收敛，测试代码会把错误假设提前固化。
- 接口细节、字段命名、返回结构可能还在变化，导致测试代码反复推倒重写。
- 模型很容易直接跳到“实现怎么写”，反而忽略“到底该测什么”。

所以当前阶段先输出“与实现挂钩的概念性测试用例”更稳妥。它至少要包含：

- 测试标题
- 覆盖的 story
- 目的
- 输入
- 步骤
- 预期结果
- 关联的验收标准

这样既不会过早绑定具体测试框架，又能为后续生成测试代码提供稳定基线。

## 4. 概念性测试与可执行测试的 gap

下面这些 gap 是当前最容易漏掉的点：

### 4.1 参数类型 gap

如果业务字段在需求里只写“用户名”“密码”“邮箱”，但没有进一步强调类型和约束，测试生成很容易只产出一条“正常提交成功”的用例。

对于 `string` 类型，至少要补齐这些维度：

- `empty`
- `whitespace`
- `invalid_format`
- `min_length - 1`
- `max_length + 1`
- `duplicate`
- `escaped/special characters`

### 4.2 参数组合 gap

真实业务很少只由单字段决定。注册功能通常要同时考虑：

- 用户名
- 邮箱
- 密码
- 确认密码
- 是否同意协议

只测“每个字段单独非法”是不够的，还需要覆盖组合情况，例如：

- 邮箱合法，但密码太短
- 用户名合法，但邮箱重复
- 所有字段合法，但未勾选协议
- 邮箱和用户名都冲突

### 4.3 skill 覆盖 gap

需求分析里的 `story` 往往表达业务目标，但不一定穷尽“系统需要展现哪些 skill/能力”。例如注册流程经常隐含：

- 表单字段校验
- 账号唯一性检查
- 创建账号
- 成功反馈
- 失败反馈
- 下一步引导

如果 workflow draft 不明确这些点，测试用例就容易只覆盖“注册成功”这一条主路径。

## 5. 注册功能正常长什么样

以“制作一个网站，具备注册登录功能”为例，注册功能最基础的正常流程通常应满足：

1. 访客打开注册页。
2. 输入合法用户名/邮箱/密码。
3. 提交后系统完成字段校验。
4. 若账号未重复，则创建新账号。
5. 页面返回明确成功反馈。
6. 用户被引导到登录页或进入已注册后的下一步。

对应的最小可测试业务结果是：

- 有效输入可以成功注册。
- 无效输入会收到明确修正提示。
- 已存在账号不能重复注册。
- 成功和失败结果都能让用户知道下一步该做什么。

## 6. 前后联合例子

下面是一个推荐的前后联合例子：

### 6.1 前端输入

前端在需求分析通过后，把 `story_units` 和 workflow draft 一起发给后端：

```json
{
  "settings": {
    "enabled": true,
    "provider_kind": "openai_compatible",
    "provider_name": "zhipu",
    "model": "GLM-4.7-Flash",
    "api_base": "https://api.z.ai/api/paas/v4",
    "api_key": "<local>",
    "temperature": 0.2,
    "max_tokens": 4000,
    "timeout_seconds": 60
  },
  "input": {
    "task_id": "ra_login_001",
    "user_prompt": "制作一个网站，具备注册登录功能。",
    "plan": "必须覆盖注册成功、字段校验失败、账号重复注册、登录成功、登录失败、登录状态反馈和端到端注册后登录路径。",
    "story_units": [
      {
        "id": "story_visitor_registers_account",
        "story_kind": "user_outcome",
        "title": "访客可以使用有效账号信息完成网站注册",
        "as_a": "访客",
        "when_context": "我第一次使用网站并提交有效的注册信息",
        "i_want": "创建一个可用于后续登录的网站账号",
        "so_that": "我可以从访客身份转为已注册用户",
        "narrative": "作为访客，当我第一次使用网站并提交有效的注册信息时，我希望创建一个可用于后续登录的网站账号，从而我可以从访客身份转为已注册用户。",
        "actor": "访客",
        "context": "我第一次使用网站并提交有效的注册信息",
        "goal": "创建一个可用于后续登录的网站账号",
        "business_value": "我可以从访客身份转为已注册用户",
        "business_outcome": "访客可以完成账号创建并获得清晰的注册结果",
        "scope": ["账号注册入口", "注册成功反馈", "注册字段校验"],
        "out_of_scope": [],
        "acceptance_criteria": [
          "提交有效注册信息后系统会创建账号并展示注册成功结果",
          "提交缺失或格式错误的信息时系统会指出需要修正的字段",
          "提交已存在账号信息时系统会提示该账号不可重复注册"
        ],
        "dependencies": [],
        "priority": "high",
        "risk": "medium",
        "test_focus": ["注册成功路径", "字段校验失败", "账号重复注册"],
        "implementation_hints": []
      }
    ],
    "execution_constraints": {
      "max_test_cases_per_story": 6,
      "require_boundary_cases": true,
      "require_negative_cases": true
    }
  }
}
```

### 6.2 后端输出

后端返回的结果应至少包含：

- `test_plan`
- `test_cases`
- `coverage_summary`
- `quality_checks`
- `completion_check`

其中 `completion_check` 专门回答：

- 当前测试计划是否已经完成了前端给出的 `plan`
- 哪些缺失项还没覆盖
- 下一轮应该补什么

## 7. 当前 workflow draft 应该强调什么

推荐在 draft 里固定强调下面这些要求：

- 测试用例先输出概念性描述，但标题、输入、步骤、预期结果必须能落到测试代码。
- 每个 story 至少覆盖正向、边界、负向三类场景。
- 所有 `string` 类型字段都要覆盖空值、空白、非法格式、边界长度和重复值。
- 如果存在组合验证阶段产出的端到端场景，必须保留为集成测试候选。
- 测试计划必须区分单 story 覆盖和跨 story 联合覆盖。

## 8. 与当前实现的对应关系

- 前端 workflow draft 生成与请求映射：`frontend/frontend-bridge/src/test-case-generation.ts`
- Void 面板联调入口：`frontend/void/.../useAiIdeBridge.tsx`
- 面板展示和触发按钮：`frontend/void/.../AiIdeBridgePanel.tsx`
- 后端接口：`backend-bridge/app/api/test_case_generation.py`
- 后端 orchestrator：`tdd_agent_framework/orchestrators/test_case_generation.py`
- AI 完成度检查：`tdd_agent_framework/agents/test_case_generation_verification`

## 9. 下一步建议

如果要继续从“概念性测试用例”进入“测试代码”，建议下一阶段补一个 `CodeImplementation` 或 `TestCodeSynthesis` 步骤，并明确输入输出契约：

- 输入：需求分析结果、测试计划、测试用例、workflow draft
- 输出：测试文件路径、测试代码、测试框架、fixture、运行命令

当前 v1 先把“需求分析 -> 测试用例生成 -> 完成度校验”做稳定，再进入自动写测试代码，会更容易控制风险。

补充：当前仓库已新增下一阶段入口，见 [测试代码生成 Workflow Draft](./test-code-generation-workflow-draft.md)。
