# 需求分析智能体流程实例：注册登录网站

状态：示例文档  
最后更新：`2026-05-18`

## 1. 示例目标

本文用同一个原始需求贯穿当前需求分析智能体的完整流程，并说明每个流程节点对应的：

- 模型动作
- 输出产物
- 用户动作
- 关键状态

原始需求：

```text
制作一个网站，具备注册登录功能。
```

这不是在定义最终产品方案，而是在演示当前 `RequirementAnalysis` 智能体如何把一句自然语言需求逐步转成可审核、可验证、可继续迭代的 `RequirementSpec + capability_groups + story_units`。

## 2. 当前流程总览

当前实现中的主要阶段如下：

1. 用户输入原始需求。
2. 前端收集 IDE/仓库上下文并构造 `RequirementAnalysisInput`。
3. 后端进入 `content_review`，调用需求分析模型生成结构化需求。
4. 解析器与质量检查器校验结构和基础质量。
5. 单条 story 验证会话检查 story 粒度、可测试性、依赖和叙事质量。
6. 若单条验证通过，暂停为 `paused_content_verified`，等待用户审核。
7. 用户可选择继续单条优化，或进入组合验证。
8. 组合验证会话从集成测试视角检查整组 story 是否形成闭环。
9. 若组合验证未通过，用户可按组合问题继续优化，进入 `composition_revision`。
10. 若组合验证通过，暂停为 `paused_converged`，用户可接受结果，也可选择继续单条优化或继续组合优化。

## 3. 节点 1：用户输入原始需求

节点类型：用户动作。

用户在 IDE 面板输入：

```text
制作一个网站，具备注册登录功能。
```

前端记录的核心字段示例：

```json
{
  "task_id": "ra_login_001",
  "mode": "repo_chat",
  "user_prompt": "制作一个网站，具备注册登录功能。",
  "analysis_goal": "content_review",
  "iteration": 1
}
```

此时还不会生成 story，也不会直接生成测试或代码。

## 4. 节点 2：收集工作区上下文

节点类型：系统动作。

前端桥接层会收集当前 IDE 上下文，后端 orchestrator 会补充工作区摘要。

示例输出：

```json
{
  "workspace_summary": {
    "languages": ["typescript", "python"],
    "frameworks": ["react", "fastapi", "pytest"],
    "key_modules": ["frontend", "backend-bridge", "tdd_agent_framework"]
  },
  "active_file": null,
  "open_files": [],
  "diagnostics": [],
  "recent_test_failures": [],
  "execution_constraints": {
    "disallow_new_dependencies": true,
    "preserve_public_api": true,
    "max_capability_groups": 4,
    "max_story_units": 12
  }
}
```

这一步的作用是让模型知道当前项目大致技术环境，但它仍然不会替用户扩展过多产品范围。

## 5. 节点 3：首轮需求分析生成

节点类型：模型动作。

后端以 `analysis_goal = content_review` 调用需求分析模型。模型必须返回标准 JSON 对象，且顶层必须包含：

- `requirement_spec`
- `capability_groups`
- `story_units`

### 5.1 示例 RequirementSpec

```json
{
  "task_id": "ra_login_001",
  "version": 1,
  "problem_statement": "当前网站还没有注册和登录能力，访客无法创建账号，也无法以已注册身份进入需要登录的页面。",
  "product_goal": "为网站提供可验证的账号注册、登录认证和登录状态反馈能力，让用户能够从访客身份进入已登录身份。",
  "scope": [
    "账号注册入口",
    "账号登录入口",
    "登录状态反馈"
  ],
  "out_of_scope": [
    "第三方 OAuth 登录",
    "手机号短信验证码登录",
    "管理员后台账号管理"
  ],
  "constraints": [
    "注册和登录结果必须给出明确成功或失败反馈",
    "密码等敏感信息不得以明文形式在页面回显"
  ],
  "assumptions": [
    "第一版使用邮箱或用户名加密码作为注册登录凭据",
    "网站已有基础页面承载注册和登录入口"
  ],
  "interfaces_or_contracts": [
    "注册提交接口需要返回成功、字段校验失败或账号已存在结果",
    "登录提交接口需要返回成功、凭据错误或账号不可用结果"
  ],
  "acceptance_criteria": [
    "访客可以提交有效注册信息并创建账号",
    "已注册用户可以使用正确凭据登录网站",
    "注册或登录失败时用户可以看到明确原因并继续修正"
  ],
  "decomposition_strategy": "按访客注册、已注册用户登录、认证反馈三个可测试业务结果拆分。"
}
```

### 5.2 示例 capability_groups

```json
[
  {
    "id": "capability_account_access",
    "title": "账号访问能力",
    "goal": "让访客可以创建账号，并让已注册用户可以进入已登录状态。",
    "scope": ["账号注册入口", "账号登录入口", "登录状态反馈"],
    "story_ids": [
      "story_visitor_registers_account",
      "story_registered_user_logs_in",
      "story_user_gets_auth_feedback"
    ],
    "priority": "high"
  }
]
```

### 5.3 示例 story_units

```json
[
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
    "goal": "创建一个可用于后续登录的网站账号",
    "business_value": "我可以从访客身份转为已注册用户",
    "business_outcome": "访客可以完成账号创建并获得清晰的注册结果",
    "scope": ["账号注册入口", "注册成功反馈", "注册字段校验"],
    "out_of_scope": ["第三方 OAuth 登录", "短信验证码注册"],
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
  },
  {
    "id": "story_registered_user_logs_in",
    "story_kind": "user_outcome",
    "title": "已注册用户可以使用正确凭据登录网站",
    "as_a": "已注册用户",
    "when_context": "我已经拥有网站账号并提交正确登录凭据",
    "i_want": "进入网站的已登录状态",
    "so_that": "我可以访问需要登录身份的页面或能力",
    "narrative": "作为已注册用户，当我已经拥有网站账号并提交正确登录凭据时，我希望进入网站的已登录状态，从而我可以访问需要登录身份的页面或能力。",
    "actor": "已注册用户",
    "goal": "进入网站的已登录状态",
    "business_value": "我可以访问需要登录身份的页面或能力",
    "business_outcome": "已注册用户可以通过正确凭据建立登录会话",
    "scope": ["账号登录入口", "登录成功反馈", "登录会话建立"],
    "out_of_scope": ["第三方 OAuth 登录", "多因素认证"],
    "acceptance_criteria": [
      "提交正确凭据后系统会建立登录状态并展示登录成功结果",
      "提交错误密码时系统不会建立登录状态并展示凭据错误提示",
      "提交不存在账号时系统会提示无法完成登录"
    ],
    "dependencies": ["story_visitor_registers_account"],
    "priority": "high",
    "risk": "medium",
    "test_focus": ["登录成功路径", "错误密码", "不存在账号"],
    "implementation_hints": []
  },
  {
    "id": "story_user_gets_auth_feedback",
    "story_kind": "system_feedback",
    "title": "用户可以根据注册登录反馈判断下一步操作",
    "as_a": "正在注册或登录的用户",
    "when_context": "我提交注册或登录表单后系统完成处理",
    "i_want": "看到明确的成功、失败或修正提示",
    "so_that": "我可以知道是否已进入账号流程的下一步",
    "narrative": "作为正在注册或登录的用户，当我提交注册或登录表单后系统完成处理时，我希望看到明确的成功、失败或修正提示，从而我可以知道是否已进入账号流程的下一步。",
    "actor": "正在注册或登录的用户",
    "goal": "看到明确的成功、失败或修正提示",
    "business_value": "我可以知道是否已进入账号流程的下一步",
    "business_outcome": "用户不会因注册登录结果不明确而停留在不可判断状态",
    "scope": ["注册反馈", "登录反馈", "表单错误提示"],
    "out_of_scope": ["全站通知系统重构"],
    "acceptance_criteria": [
      "注册成功时用户可以看到成功结果或被引导到登录/已登录页面",
      "登录成功时用户可以看到已登录状态或进入登录后页面",
      "注册或登录失败时用户可以看到可操作的错误提示"
    ],
    "dependencies": ["story_visitor_registers_account", "story_registered_user_logs_in"],
    "priority": "medium",
    "risk": "low",
    "test_focus": ["成功反馈", "失败反馈", "用户下一步引导"],
    "implementation_hints": []
  }
]
```

## 6. 节点 4：结构解析与基础质量检查

节点类型：系统动作。

解析器会检查模型输出是否是可解析 JSON，并将字段标准化。质量检查器会检查：

- 是否包含 `requirement_spec`、`capability_groups`、`story_units`
- `capability_groups.story_ids` 是否引用已有 story
- `dependencies` 是否引用已有 story
- story 标题是否只是“用户登录”这种功能名
- `scope`、`acceptance_criteria`、`test_focus` 是否为空
- story 总数是否超过当前轮次上限

### 6.1 格式失败分支示例

如果模型只返回：

```text
这里是需求分析结果：用户需要注册和登录。
```

系统会进入：

```text
status = paused_format_invalid
```

示例包摘要：

```json
{
  "status": "paused_format_invalid",
  "verification": {
    "status": "blocked",
    "summary": "模型输出未通过格式校验。",
    "revision_guidance": ["重试需求分析，要求模型只返回标准 JSON 对象。"]
  }
}
```

用户动作：

- 点击“继续优化”重新发起需求分析。
- 或补充说明，例如“只考虑邮箱加密码注册登录，不需要第三方登录”。

## 7. 节点 5：单条 story 验证

节点类型：模型动作。

`RequirementVerification` 会检查单条 story 和单轮拆解质量。它不等同于组合验证，重点是每条 story 自己是否可测试、粒度是否合理、叙事是否清楚。

### 7.1 单条验证通过示例

```json
{
  "status": "pass",
  "summary": "注册、登录和反馈 story 的单条叙事清晰，验收标准可测试，依赖关系可解释。",
  "issues": [],
  "revision_guidance": [],
  "quality_score": {
    "scope_clarity": 90,
    "testability": 92,
    "dependency_sanity": 88,
    "story_granularity": 86
  }
}
```

系统状态：

```text
paused_content_verified
```

此时系统暂停，等待用户审核。用户可选择：

- `继续优化`：继续走 `content_review`，优化单条 story。
- `进入组合验证`：进入 `composition_review`。
- 提交全局反馈或 story 级反馈后继续分析。

### 7.2 单条验证未通过示例

如果模型生成的 story 是：

```text
用户登录
```

验证器可能输出：

```json
{
  "status": "revise",
  "summary": "部分 story 仍是功能名，缺少具体场景、业务结果和可测试验收标准。",
  "issues": [
    {
      "id": "issue_story_too_shallow",
      "severity": "medium",
      "issue_type": "under_scoped",
      "message": "story_login 只描述了功能主题，没有说明用户处于什么场景、希望达成什么业务结果。",
      "affected_story_ids": ["story_login"]
    }
  ],
  "revision_guidance": [
    "将“用户登录”改写为包含角色、场景、目标和业务结果的完整 user story。"
  ]
}
```

系统会自动进入下一轮修订，最多自动修订到当前上限。达到上限仍未通过时进入：

```text
paused_stalled
```

此时系统会给用户展示澄清问题，例如：

```text
第一版注册登录是否只支持邮箱和密码，还是也需要用户名登录？
登录成功后应进入哪个页面或展示什么状态？
账号重复、密码错误、账号不存在时分别应如何提示？
```

## 8. 节点 6：用户审核单条验证结果

节点类型：用户动作。

当状态为 `paused_content_verified` 时，面板会展示简短概要和建议。

示例概要：

```json
{
  "verification_gate_summary": {
    "blocking_issue_count": 0,
    "nonblocking_suggestion_count": 0,
    "explicit_capability_coverage": {
      "required": ["注册", "登录"],
      "covered": ["注册", "登录"],
      "missing": [],
      "covered_count": 2,
      "required_count": 2
    },
    "decision_reason": "阻塞问题已清零，显式能力覆盖达到门槛，当前结果适合进入用户审核。"
  },
  "user_review_guidance": {
    "summary_points": [
      "目标：为网站提供可验证的账号注册、登录认证和登录状态反馈能力。",
      "范围：账号注册入口、账号登录入口、登录状态反馈",
      "当前拆分为 1 个能力组、3 条 user story。"
    ],
    "suggestions": [
      "快速确认第一版是否需要支持第三方登录。",
      "确认登录成功后是否必须进入特定页面。",
      "确认注册后是否自动登录。"
    ],
    "clarification_questions": []
  }
}
```

用户动作示例：

```text
点击“进入组合验证”。
```

前端会发起：

```json
{
  "analysis_goal": "composition_review",
  "previous_analysis_result": {
    "requirement_spec": {},
    "capability_groups": [],
    "story_units": [],
    "verification": {}
  }
}
```

其中 `previous_analysis_result` 会包含上一轮完整需求分析快照。如果快照缺少 `capability_groups`，当前后端会根据 `story_units` 自动合成兜底分组，避免组合验证入口直接报错。

## 9. 节点 7：组合验证

节点类型：模型动作。

`RequirementCompositionVerification` 从集成测试视角检查整组 story 是否形成完整闭环。

### 9.1 组合验证未通过示例

假设首轮 story 只覆盖注册和登录成功路径，没有明确“登录状态保持/退出”边界。组合验证可能输出：

```json
{
  "status": "revise",
  "summary": "注册和登录主路径已覆盖，但登录状态生命周期仍不完整，后续集成测试无法确认用户何时处于已登录或已退出状态。",
  "coverage_assessment": {
    "covers_primary_user_goal": true,
    "covers_permission_constraints": true,
    "covers_failure_handling": true,
    "covers_end_to_end_flow": false
  },
  "composition_issues": [
    {
      "id": "composition_issue_session_lifecycle",
      "severity": "medium",
      "issue_type": "missing_story",
      "message": "当前 story 可以验证注册和登录，但没有明确用户如何识别当前登录状态以及如何退出登录。",
      "related_story_ids": ["story_registered_user_logs_in"],
      "related_capability_group_ids": ["capability_account_access"],
      "suggested_action": "补充登录状态生命周期 story，覆盖已登录展示和退出登录。"
    }
  ],
  "integration_test_scenarios": [
    {
      "id": "it_register_then_login",
      "title": "访客注册后使用新账号登录",
      "covers_story_ids": ["story_visitor_registers_account", "story_registered_user_logs_in"],
      "covers_capability_group_ids": ["capability_account_access"],
      "expected_outcome": "用户可以从注册成功进入可登录状态，并使用正确凭据建立登录会话。"
    }
  ],
  "redundant_story_ids": [],
  "missing_story_topics": ["登录状态生命周期", "退出登录"],
  "revision_guidance": [
    "补充一条覆盖已登录状态展示和退出登录的 story。",
    "重新检查注册、登录、登录状态之间是否能形成端到端集成测试闭环。"
  ]
}
```

系统状态：

```text
paused_stalled
```

用户动作：

```text
点击“按组合问题继续优化”。
```

前端会发起：

```json
{
  "analysis_goal": "composition_revision",
  "previous_verification_summary": "注册和登录主路径已覆盖，但登录状态生命周期仍不完整。",
  "revision_focus": [
    "补充一条覆盖已登录状态展示和退出登录的 story。",
    "补充缺失的组合能力：登录状态生命周期",
    "补充缺失的组合能力：退出登录"
  ],
  "previous_analysis_result": {
    "requirement_spec": {},
    "capability_groups": [],
    "story_units": [],
    "verification": {},
    "composition_verification": {}
  }
}
```

## 10. 节点 8：组合问题驱动的修订

节点类型：模型动作。

`composition_revision` 不是重新做一次普通单条优化，而是要求需求分析模型：

- 以上一版 `previous_analysis_result` 为基线。
- 围绕组合验证问题做增删改。
- 不要无视上一版结果从零重写。
- 修订后仍必须输出完整 `requirement_spec + capability_groups + story_units`。

示例新增 story：

```json
{
  "id": "story_logged_in_user_manages_session_state",
  "story_kind": "user_outcome",
  "title": "已登录用户可以识别当前登录状态并主动退出",
  "as_a": "已登录用户",
  "when_context": "我已经通过正确凭据进入网站的已登录状态",
  "i_want": "看到当前账号的登录状态并可以主动退出登录",
  "so_that": "我可以确认账号访问状态并在需要时结束当前会话",
  "narrative": "作为已登录用户，当我已经通过正确凭据进入网站的已登录状态时，我希望看到当前账号的登录状态并可以主动退出登录，从而我可以确认账号访问状态并在需要时结束当前会话。",
  "actor": "已登录用户",
  "goal": "看到当前账号的登录状态并可以主动退出登录",
  "business_value": "我可以确认账号访问状态并在需要时结束当前会话",
  "business_outcome": "用户可以明确判断自己是否处于登录状态，并能主动结束登录会话",
  "scope": ["登录状态展示", "退出登录", "会话结束反馈"],
  "out_of_scope": ["多设备会话管理", "强制下线其他设备"],
  "acceptance_criteria": [
    "登录成功后用户可以看到当前已登录状态或账号标识",
    "用户点击退出登录后系统会结束当前登录状态",
    "退出登录后用户访问需要登录的页面时会被要求重新登录"
  ],
  "dependencies": ["story_registered_user_logs_in"],
  "priority": "medium",
  "risk": "medium",
  "test_focus": ["已登录状态展示", "退出登录", "退出后访问限制"],
  "implementation_hints": []
}
```

修订后的 capability group 也会同步更新：

```json
{
  "id": "capability_account_access",
  "title": "账号访问能力",
  "goal": "让用户完成注册、登录、识别登录状态并主动结束会话。",
  "scope": ["账号注册入口", "账号登录入口", "登录状态反馈", "退出登录"],
  "story_ids": [
    "story_visitor_registers_account",
    "story_registered_user_logs_in",
    "story_user_gets_auth_feedback",
    "story_logged_in_user_manages_session_state"
  ],
  "priority": "high"
}
```

## 11. 节点 9：组合修订后的单条验证

节点类型：模型动作。

组合修订后，系统不会直接相信新增 story，而是先跑单条验证。

示例输出：

```json
{
  "status": "pass",
  "summary": "新增登录状态生命周期 story 与既有注册、登录 story 依赖关系清晰，验收标准可以被端到端测试验证。",
  "issues": [],
  "revision_guidance": [],
  "quality_score": {
    "scope_clarity": 91,
    "testability": 93,
    "dependency_sanity": 90,
    "story_granularity": 88
  }
}
```

如果这里不通过，系统会暂停为：

```text
paused_stalled 或 paused_blocked
```

并提示用户继续补充信息或返回单条 story 优化。

## 12. 节点 10：再次组合验证

节点类型：模型动作。

单条验证通过后，系统自动再次进入组合验证。

示例输出：

```json
{
  "status": "pass",
  "summary": "注册、登录、反馈和登录状态生命周期 story 已能形成完整账号访问闭环，可以构造端到端集成测试。",
  "coverage_assessment": {
    "covers_primary_user_goal": true,
    "covers_permission_constraints": true,
    "covers_failure_handling": true,
    "covers_end_to_end_flow": true
  },
  "composition_issues": [],
  "integration_test_scenarios": [
    {
      "id": "it_register_login_logout",
      "title": "访客注册后登录并退出",
      "covers_story_ids": [
        "story_visitor_registers_account",
        "story_registered_user_logs_in",
        "story_user_gets_auth_feedback",
        "story_logged_in_user_manages_session_state"
      ],
      "covers_capability_group_ids": ["capability_account_access"],
      "expected_outcome": "用户可以完成注册、登录、看到登录状态、退出登录，并在退出后不再保持登录身份。"
    },
    {
      "id": "it_login_failure_feedback",
      "title": "错误凭据登录失败并展示可操作反馈",
      "covers_story_ids": [
        "story_registered_user_logs_in",
        "story_user_gets_auth_feedback"
      ],
      "covers_capability_group_ids": ["capability_account_access"],
      "expected_outcome": "用户不会进入已登录状态，并能看到可修正的失败提示。"
    }
  ],
  "redundant_story_ids": [],
  "missing_story_topics": [],
  "revision_guidance": []
}
```

系统状态：

```text
paused_converged
```

## 13. 节点 11：组合通过后的用户选择

节点类型：用户动作。

当状态为 `paused_converged` 时，当前 UI 提供三类选择。

### 13.1 接受当前结果

用户动作：

```text
点击“接受当前结果”。
```

含义：

- 当前需求分析结果可作为后续测试生成或实现规划输入。
- 不再继续本轮需求分析。

### 13.2 继续单条 story 优化

用户动作：

```text
点击“继续单条 story 优化”。
```

前端动作：

```json
{
  "analysis_goal": "content_review",
  "previous_analysis_result": null
}
```

适用场景：

- 用户觉得某条 story 表达不够贴近业务。
- 用户想调整验收标准的措辞。
- 用户想拆分或合并某条具体 story。

示例用户反馈：

```text
story_registered_user_logs_in 里应明确支持用户名或邮箱二选一登录。
```

### 13.3 继续组合优化

用户动作：

```text
点击“继续组合优化”。
```

前端动作：

```json
{
  "analysis_goal": "composition_revision",
  "revision_focus": [
    "在不破坏当前已通过组合闭环的前提下，继续增强端到端流程覆盖、边界场景、跨 story 依赖一致性和集成测试可验证性。"
  ],
  "previous_analysis_result": {
    "requirement_spec": {},
    "capability_groups": [],
    "story_units": [],
    "verification": {},
    "composition_verification": {
      "status": "pass"
    }
  }
}
```

适用场景：

- 用户接受当前闭环，但想补强边界场景。
- 用户希望让集成测试覆盖更完整。
- 用户希望检查跨 story 依赖是否还能更清楚。

此时 prompt 会明确要求模型：

```text
不要推翻已通过闭环，应在保持通过结果稳定的前提下，补强边界场景、跨 story 一致性、验收标准和集成测试可验证性。
```

## 14. 节点 12：用户反馈入口

节点类型：用户动作。

当前 UI 允许用户追加全局反馈，或选择某条 story 给出定向反馈。

### 14.1 全局反馈示例

用户输入：

```text
第一版不需要注册后自动登录，注册成功后引导用户去登录页即可。
```

前端构造：

```json
{
  "global_feedback": {
    "kind": "global_feedback",
    "feedback_type": "scope_adjustment",
    "feedback_text": "第一版不需要注册后自动登录，注册成功后引导用户去登录页即可。",
    "expected_action": "refine_existing_stories",
    "applies_to": {
      "capability_group_ids": [],
      "story_ids": []
    }
  }
}
```

模型应同步修正：

- `RequirementSpec.assumptions`
- 注册 story 的 `business_outcome`
- 注册成功验收标准
- 注册与登录 story 的依赖关系

### 14.2 Story 级反馈示例

用户选择：

```text
story_registered_user_logs_in
```

用户输入：

```text
这条 story 应该明确错误密码和账号不存在都不能泄露敏感信息。
```

前端构造：

```json
{
  "story_feedback": {
    "kind": "story_feedback",
    "story_id": "story_registered_user_logs_in",
    "feedback_type": "wording_issue",
    "feedback_text": "这条 story 应该明确错误密码和账号不存在都不能泄露敏感信息。",
    "expected_action": "refine_existing_stories"
  }
}
```

模型应优先修订：

- `story_registered_user_logs_in.acceptance_criteria`
- `story_registered_user_logs_in.test_focus`
- 必要时补充 `constraints`

## 15. 节点 13：手动停止

节点类型：用户动作。

当需求分析运行时间较长，或用户判断当前方向不对时，可以手动停止。

用户动作：

```text
点击“停止需求分析”。
```

系统动作：

- 前端设置停止标记。
- 当前流式连接结束后不再继续自动流程。
- UI 展示“已手动停止需求分析任务”。

这不等同于接受结果，也不等同于失败收敛，只是终止当前运行。

## 16. 本示例中的最终需求包节选

最终 `RequirementAnalysisPackage` 不只是状态和能力组，也必须包含 `story_units`。下面是节选后的结构，省略了部分重复字段，但保留了最终 story 集合：

```json
{
  "status": "paused_converged",
  "requirement_spec": {
    "product_goal": "为网站提供可验证的账号注册、登录认证和登录状态反馈能力。",
    "scope": ["账号注册入口", "账号登录入口", "登录状态反馈", "退出登录"],
    "out_of_scope": ["第三方 OAuth 登录", "手机号短信验证码登录", "管理员后台账号管理"]
  },
  "capability_groups": [
    {
      "id": "capability_account_access",
      "title": "账号访问能力",
      "goal": "让用户完成注册、登录、识别登录状态并主动结束会话。",
      "scope": ["账号注册入口", "账号登录入口", "登录状态反馈", "退出登录"],
      "story_ids": [
        "story_visitor_registers_account",
        "story_registered_user_logs_in",
        "story_user_gets_auth_feedback",
        "story_logged_in_user_manages_session_state"
      ]
    }
  ],
  "story_units": [
    {
      "id": "story_visitor_registers_account",
      "title": "访客可以使用有效账号信息完成网站注册",
      "narrative": "作为访客，当我第一次使用网站并提交有效的注册信息时，我希望创建一个可用于后续登录的网站账号，从而我可以从访客身份转为已注册用户。",
      "scope": ["账号注册入口", "注册成功反馈", "注册字段校验"],
      "acceptance_criteria": [
        "提交有效注册信息后系统会创建账号并展示注册成功结果",
        "提交缺失或格式错误的信息时系统会指出需要修正的字段",
        "提交已存在账号信息时系统会提示该账号不可重复注册"
      ],
      "dependencies": [],
      "priority": "high"
    },
    {
      "id": "story_registered_user_logs_in",
      "title": "已注册用户可以使用正确凭据登录网站",
      "narrative": "作为已注册用户，当我已经拥有网站账号并提交正确登录凭据时，我希望进入网站的已登录状态，从而我可以访问需要登录身份的页面或能力。",
      "scope": ["账号登录入口", "登录成功反馈", "登录会话建立"],
      "acceptance_criteria": [
        "提交正确凭据后系统会建立登录状态并展示登录成功结果",
        "提交错误密码时系统不会建立登录状态并展示凭据错误提示",
        "提交不存在账号时系统会提示无法完成登录"
      ],
      "dependencies": ["story_visitor_registers_account"],
      "priority": "high"
    },
    {
      "id": "story_user_gets_auth_feedback",
      "title": "用户可以根据注册登录反馈判断下一步操作",
      "narrative": "作为正在注册或登录的用户，当我提交注册或登录表单后系统完成处理时，我希望看到明确的成功、失败或修正提示，从而我可以知道是否已进入账号流程的下一步。",
      "scope": ["注册反馈", "登录反馈", "表单错误提示"],
      "acceptance_criteria": [
        "注册成功时用户可以看到成功结果或被引导到登录/已登录页面",
        "登录成功时用户可以看到已登录状态或进入登录后页面",
        "注册或登录失败时用户可以看到可操作的错误提示"
      ],
      "dependencies": ["story_visitor_registers_account", "story_registered_user_logs_in"],
      "priority": "medium"
    },
    {
      "id": "story_logged_in_user_manages_session_state",
      "title": "已登录用户可以识别当前登录状态并主动退出",
      "narrative": "作为已登录用户，当我已经通过正确凭据进入网站的已登录状态时，我希望看到当前账号的登录状态并可以主动退出登录，从而我可以确认账号访问状态并在需要时结束当前会话。",
      "scope": ["登录状态展示", "退出登录", "会话结束反馈"],
      "acceptance_criteria": [
        "登录成功后用户可以看到当前已登录状态或账号标识",
        "用户点击退出登录后系统会结束当前登录状态",
        "退出登录后用户访问需要登录的页面时会被要求重新登录"
      ],
      "dependencies": ["story_registered_user_logs_in"],
      "priority": "medium"
    }
  ],
  "verification": {
    "status": "pass"
  },
  "composition_verification": {
    "status": "pass",
    "summary": "注册、登录、反馈和登录状态生命周期 story 已能形成完整账号访问闭环。"
  }
}
```

## 17. 与当前实现的对应关系

| 流程节点 | 当前实现中的关键对象或状态 |
| --- | --- |
| 原始需求输入 | `user_prompt` |
| 工作区上下文整理 | `workspace_summary`、`open_files`、`diagnostics` |
| 首轮需求分析 | `analysis_goal = content_review` |
| 结构解析与质量检查 | `RequirementAnalysisParser`、`RequirementAnalysisQualityChecker` |
| 单条 story 验证 | `RequirementVerification` |
| 单条验证通过暂停 | `paused_content_verified` |
| 进入组合验证 | `analysis_goal = composition_review` |
| 组合验证未通过 | `paused_stalled` 或 `paused_blocked` |
| 按组合问题继续优化 | `analysis_goal = composition_revision` |
| 组合验证通过 | `paused_converged` |
| 继续单条 story 优化 | 显式 `analysis_goal = content_review` |
| 继续组合优化 | 显式 `analysis_goal = composition_revision`，且上一轮 `composition_verification.status = pass` |
| 接受当前结果 | 前端 `acceptRequirementAnalysisResult()` |

## 18. 这个示例刻意体现的原则

- `User Story` 不是“用户登录”这种功能名，而是包含角色、场景、目标和业务结果的需求描述。
- 单条验证通过不代表组合验证通过。
- 组合验证不直接改 story，只输出组合层审查结果。
- 组合修订会回到需求分析模型，但必须以上一版结果为基线。
- 组合修订后仍要先过单条验证，再过组合验证。
- 组合通过后仍允许继续优化，但必须区分“单条 story 优化”和“组合增强优化”。
