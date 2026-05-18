# 需求分析模块使用说明

状态：草案  
最后更新：`2026-05-18`

## 1. 适用范围

本文说明 `ai-ide-bridge` 当前需求分析模块的实际使用方式，包括：

- 如何启动带桥接层的 Void 原生客户端。
- 如何在 IDE 面板中配置需求分析模型。
- 如何运行需求分析。
- 各个按钮和状态分别表示什么。
- 常见错误应如何处理。

本文面向项目使用者和开发者，不替代设计文档。设计细节请参考：

- [需求分析流程图](./requirement-analysis-flow.png)
- [注册登录网站流程实例](./requirement-analysis-login-flow-example.md)
- [User Story 标准](./requirement-analysis-user-story-standard.md)
- [组合验证设计](./requirement-composition-verification-v1.md)
- [用户反馈协议](./requirement-feedback-v1.md)

## 2. 当前能力边界

当前需求分析模块属于 `ai-ide-bridge` 桥接层中的第一阶段能力。

当前已支持：

- 在 Void 原生客户端侧边栏中配置需求分析模型。
- 输入原始需求并运行需求分析。
- 生成结构化 `RequirementSpec`、`capability_groups`、`story_units`。
- 对单条 story 进行内容验证。
- 进入组合验证，从集成测试视角检查 story 集合是否闭环。
- 在组合验证未通过时，按组合问题继续修订。
- 在组合验证通过后，继续单条 story 优化或继续组合优化。
- 追加全局反馈或指定某条 story 反馈。
- 手动停止运行中的需求分析任务。

当前不表示：

- 需求分析结果已经自动进入代码实现。
- 需求分析结果已经自动生成测试代码。
- `backend-bridge` 已经完整接入 OpenHands 执行链路。

## 3. 启动方式

终端 1，启动 OpenHands 后端：

```bash
cd ~/ai-agent/OpenHands
source ~/ai-agent/.venv/bin/activate
export NO_PROXY=127.0.0.1,localhost
make start-backend BACKEND_HOST=127.0.0.1 BACKEND_PORT=3000
```

终端 2，启动我们自己的前端入口。

这条命令会自动拉起 `backend-bridge`，然后打开 Void 原生前端：

```bash
cd ~/ai-agent
source .venv/bin/activate
export NO_PROXY=127.0.0.1,localhost
export OPENHANDS_URL=http://127.0.0.1:3000
npm run start:native --prefix ai-ide-bridge/frontend/void
```

## 4. 打开需求分析入口

启动 Void 原生客户端后，在侧边栏中进入 `AI IDE Bridge` 面板。

该面板目前包含：

- 需求分析模型配置。
- 需求分析运行入口。
- 需求分析运行状态。
- 需求分析结果展示。
- 继续优化、组合验证、反馈和接受结果等按钮。

## 5. 配置需求分析模型

展开 `需求分析模型配置` 区域。

### 5.1 必填配置

通常需要填写：

- `启用需求分析智能体`：必须勾选。
- `Provider 名称`：例如 `openai`、`openrouter`、`my-gateway`。
- `模型名称`：例如 `gpt-5.4`。
- `Base URL`：模型服务地址，例如 `https://example.com/v1`。
- `API Key`：模型服务密钥。

配置会保存在本机 IDE 存储中。

### 5.2 模型参数

界面中还可以调整：

- `Temperature`：模型随机性。
- `Max Tokens`：单次响应最大 token 数。
- `Timeout(s)`：单次 HTTP 读超时。
- `Max Run(s)`：单次模型请求总运行上限。

### 5.3 Story / Group 上限策略

当前支持按轮次设置 story 和能力组上限：

- `首轮最多组数`
- `首轮最多 Story`
- `第二轮最多组数`
- `第二轮最多 Story`
- `第三轮起最多组数`
- `第三轮起最多 Story`

留空表示该轮次不设上限。

默认策略倾向于：

- 首轮控制规模，避免模型一次铺太大。
- 第二轮适度放宽。
- 第三轮及以后允许更大范围修订。

### 5.4 配置按钮

- `保存需求分析配置`：保存当前配置。
- `恢复默认`：恢复默认配置。
- `复制配置 JSON`：复制当前 snake_case 配置 JSON，便于调试后端入参。

## 6. 运行需求分析

在输入框中填写原始需求，例如：

```text
制作一个网站，具备注册登录功能。
```

点击：

```text
运行需求分析
```

前端会构造 `RequirementAnalysisInput`，核心字段包括：

```json
{
  "mode": "repo_chat",
  "user_prompt": "制作一个网站，具备注册登录功能。",
  "analysis_goal": "content_review",
  "iteration": 1,
  "workspace_summary": {},
  "execution_constraints": {
    "disallow_new_dependencies": true,
    "preserve_public_api": true,
    "max_capability_groups": 4,
    "max_story_units": 12
  }
}
```

运行期间，面板会显示：

- 当前阶段。
- 最新事件。
- 最近事件列表。
- 模型输出预览。
- 自动重试次数。

如果任务仍在运行，可以点击：

```text
停止需求分析
```

停止只表示终止当前运行，不表示接受当前结果。

## 7. 结果产物

需求分析成功后，结果包通常包含：

- `requirement_spec`：整体需求说明、范围、约束、验收标准和拆解策略。
- `capability_groups`：能力分组。
- `story_units`：标准化 user story。
- `verification`：单条 story 验证结果。
- `composition_verification`：组合验证结果，只有进入组合验证后才会出现。
- `history`：迭代历史。
- `verification_gate_summary`：门禁摘要。
- `user_review_guidance`：给用户的简短审核建议。

`story_units` 不是简单功能名，应该类似：

```text
作为访客，当我第一次使用网站并提交有效的注册信息时，我希望创建一个可用于后续登录的网站账号，从而我可以从访客身份转为已注册用户。
```

不应写成：

```text
用户注册
```

## 8. 状态含义

### 8.1 `paused_content_verified`

含义：

- 单条 story 验证已通过。
- 当前 story 的结构、粒度、验收标准基本合格。
- 尚未完成组合验证。

常见下一步：

- 点击 `进入组合验证`。
- 或继续优化单条 story。

### 8.2 `paused_converged`

含义：

- 单条 story 验证通过。
- 组合验证通过。
- 当前需求分析结果已经形成较完整闭环。

常见下一步：

- 点击 `接受当前结果`。
- 或点击 `继续单条 story 优化`。
- 或点击 `继续组合优化`。

### 8.3 `paused_stalled`

含义：

- 当前结果还需要继续修订。
- 可能是单条验证达到自动修订上限。
- 也可能是组合验证认为 story 集合仍不完整。

常见下一步：

- 查看问题和澄清问题。
- 补充反馈后继续分析。
- 如果已有组合验证问题，点击 `按组合问题继续优化`。

### 8.4 `paused_blocked`

含义：

- 存在阻塞性问题。
- 需要用户补充关键前提或修正需求方向。

常见下一步：

- 回答面板给出的澄清问题。
- 追加全局反馈。
- 指定 story 给出反馈。

### 8.5 `paused_format_invalid`

含义：

- 模型输出没有通过 JSON 或协议结构校验。
- 例如模型返回了 Markdown、解释文本、空响应或错误形状对象。

常见下一步：

- 点击 `继续优化` 重试。
- 检查模型是否支持 JSON 输出。
- 降低输出复杂度或提高 `Max Tokens`。

## 9. 按钮含义

### 9.1 `运行需求分析`

从原始需求启动新一轮需求分析，默认目标为：

```text
analysis_goal = content_review
```

### 9.2 `停止需求分析`

请求停止当前运行中的需求分析任务。

### 9.3 `继续优化`

在尚未组合验证通过时使用。

如果当前没有失败的组合验证结果，通常继续走：

```text
analysis_goal = content_review
```

如果当前已有未通过的组合验证结果，前端会自动改为：

```text
analysis_goal = composition_revision
```

按钮文案会变成 `按组合问题继续优化`。

### 9.4 `进入组合验证`

在单条验证通过后使用。

它不会重新生成 story，而是使用当前 `previous_analysis_result` 快照，从集成测试视角验证整组 story 是否闭环。

对应目标：

```text
analysis_goal = composition_review
```

### 9.5 `按组合问题继续优化`

当组合验证未通过时出现。

它会把上一轮组合验证中的：

- `revision_guidance`
- `missing_story_topics`
- `composition_issues`

作为修订焦点，回到需求分析模型修订整组 story。

对应目标：

```text
analysis_goal = composition_revision
```

修订后系统会自动：

1. 跑单条 story 验证。
2. 单条验证通过后再次跑组合验证。

### 9.6 `返回单条 story 优化`

当组合验证未通过时，如果用户不想按组合问题修订，而是希望回到单条 story 层面调整，可以点击这个按钮。

对应目标：

```text
analysis_goal = content_review
```

### 9.7 `继续单条 story 优化`

当组合验证已经通过时出现。

适合场景：

- 某条 story 表达不够贴近业务。
- 验收标准需要调整。
- story 粒度需要拆分或合并。

对应目标：

```text
analysis_goal = content_review
```

### 9.8 `继续组合优化`

当组合验证已经通过时出现。

适合场景：

- 当前闭环已通过，但还想补强边界场景。
- 希望集成测试覆盖更完整。
- 希望跨 story 依赖更清晰。

对应目标：

```text
analysis_goal = composition_revision
```

此时模型会被要求：

```text
不要推翻已通过闭环，应在保持通过结果稳定的前提下，补强边界场景、跨 story 一致性、验收标准和集成测试可验证性。
```

### 9.9 `接受当前结果`

当组合验证通过后可用。

含义：

- 用户接受当前需求分析结果。
- 本轮需求分析结束。
- 当前结果可以作为后续测试设计或实现阶段输入。

## 10. 反馈用法

结果面板中可以追加反馈。

### 10.1 全局反馈

不选择具体 story，直接填写反馈。

示例：

```text
第一版只支持邮箱加密码登录，不需要第三方登录。
```

这会构造 `global_feedback`，适合修改整体范围、约束或优先级。

### 10.2 Story 级反馈

先选择某条 story，再填写反馈。

示例：

```text
这条登录 story 应明确错误密码和账号不存在都不能泄露敏感信息。
```

这会构造 `story_feedback`，适合修改某一条 story 的描述、验收标准或测试重点。

### 10.3 带反馈继续分析

点击：

```text
带反馈继续分析
```

系统会把反馈纳入下一轮输入。

如果当前处于组合验证未通过状态，反馈会跟随 `composition_revision` 路径；否则通常走 `content_review`。

## 11. 常见问题

### 11.1 `EADDRINUSE: address already in use 127.0.0.1:27183`

含义：

- 已有 Void 原生运行时或桥接服务占用了端口。

处理：

- 关闭旧 Void 窗口。
- 停止旧后端进程。
- 再重新执行 `npm run start:native --prefix ai-ide-bridge/frontend/void`。

### 11.2 `provider request failed with status 400` 且提示 JSON

可能原因：

- 模型服务要求 JSON 模式时，输入消息中必须明确包含 `json`。
- 当前 prompt 已包含相关约束，但如果使用的代理服务额外改写请求，仍可能触发。

处理：

- 确认模型服务兼容 OpenAI 风格 JSON 输出。
- 检查 provider 网关是否改写 `response_format`。
- 重试或更换模型配置。

### 11.3 `HTTP 524` 或 `ReadTimeout`

含义：

- 上游模型网关或 Cloudflare 超时。
- 通常不是需求分析协议本身错误。

处理：

- 调大 `Timeout(s)` 或 `Max Run(s)`。
- 降低首轮 story 上限。
- 更换更稳定的模型网关。

### 11.4 `provider response does not contain choices`

含义：

- 上游返回的不是 OpenAI compatible chat completions 结构。

处理：

- 检查 `Base URL` 是否指向 chat completions 兼容接口。
- 检查 provider 网关错误页是否被当成模型响应返回。

### 11.5 `requirement_spec must be an object`

含义：

- 模型返回了错误 JSON 结构。
- 例如只返回了 `status`、`summary` 或验证器风格对象。

处理：

- 点击继续优化重试。
- 降低需求复杂度。
- 检查模型是否遵守结构化输出。

### 11.6 `story_unit.scope must be a non-empty list of strings`

含义：

- 某条 story 缺少范围字段，或字段类型错误。

处理：

- 点击继续优化。
- 在反馈中明确要求每条 story 必须包含具体业务范围。

## 12. 推荐使用流程

推荐按下面顺序使用：

1. 启动 Void 原生客户端。
2. 配置并保存需求分析模型。
3. 输入原始需求并点击 `运行需求分析`。
4. 等待进入 `paused_content_verified`。
5. 快速查看 story 摘要和建议。
6. 如果单条 story 方向不对，追加反馈后继续优化。
7. 如果单条 story 可接受，点击 `进入组合验证`。
8. 如果组合验证未通过，点击 `按组合问题继续优化`。
9. 如果组合验证通过，按需要选择 `接受当前结果`、`继续单条 story 优化` 或 `继续组合优化`。

## 13. 相关文档

- [需求分析流程图](./requirement-analysis-flow.png)
- [注册登录网站流程实例](./requirement-analysis-login-flow-example.md)
- [User Story 标准](./requirement-analysis-user-story-standard.md)
- [组合验证设计](./requirement-composition-verification-v1.md)
- [用户反馈协议](./requirement-feedback-v1.md)
- [整体 README](../README.md)
