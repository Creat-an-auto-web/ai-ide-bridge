# AI IDE Bridge TDD 后端框架设计草案

状态：草案  
最后更新：`2026-04-18`

## 1. 背景

当前项目已经基本完成前端桥接链路：

- 复用 Void 原生前端
- 通过 `frontend/frontend-bridge` 组织 IDE 上下文、任务请求和事件归约
- 通过 `backend-bridge` 向后端发起任务并接收事件

现阶段的核心问题已经不再是“前端能不能发请求”，而是“后端到底采用什么执行框架”。

如果继续把 OpenHands 原生 agent loop 当作最终产品框架，会遇到几个问题：

- 状态流不受我们控制，前端只能被动适配 OpenHands 的内部事件
- TDD 过程缺少稳定的中间产物，难以做可审计回放
- 需求分析、测试设计、代码实现、失败修复容易混在一个黑箱循环里
- 测试与实现没有被强制拆开，难以保证“先定义行为，再实现代码”
- 后续如果要替换执行引擎，成本会很高

因此，后端应该逐步演进为“我们自己的 TDD 编排框架”，而不是继续直接依赖 OpenHands 原生工作流。

## 2. 总体判断

你给出的方向是对的，但要把它落成一个真正可实现的后端框架，关键不是简单串起四个智能体，而是建立一个严格的、可回放的、可终止的 TDD 状态机。

推荐的总体原则是：

- 产品协议以 `bridge protocol` 为主，不向前端暴露 OpenHands 内部对象
- 后端核心价值放在 orchestration 层，而不是放在某个单独模型 prompt 上
- OpenHands 更适合作为执行能力层
  - 沙箱
  - 命令执行
  - 文件读写
  - 工具调用
- TDD 过程必须有结构化中间产物，而不是只靠自然语言上下文串联

## 3. 目标与非目标

### 3.1 目标

- 让后端按 TDD 流程稳定执行任务
- 让每个阶段都有明确输入、输出、失败条件
- 让前端可以看到阶段进度、产物摘要、测试结果和修复轮次
- 让执行引擎可替换，避免产品能力与 OpenHands 强耦合
- 为后续加入更强的策略控制、审批、评估器打基础

### 3.2 非目标

- 现在就做一个完全分布式多智能体系统
- 现在就做复杂的 DAG 调度平台
- 现在就要求每个阶段必须是独立进程或独立模型
- 现在就替换掉现有的 `backend-bridge` 对外协议

第一版更适合做成“单编排器 + 多阶段角色 + 结构化产物 + 可循环修复”的严格状态机。

## 4. 推荐架构

建议把后端拆成四层：

### 4.1 IDE 协议层

职责：

- 接收前端任务请求
- 向前端回传任务状态和事件
- 维持任务生命周期

这一层继续由现有 bridge 协议承担，尽量稳定。

### 4.2 TDD 编排层

职责：

- 驱动整个 TDD 状态机
- 维护每轮迭代上下文
- 决定何时进入下一阶段
- 决定何时结束、何时修复、何时失败

这一层是未来后端框架的核心。

### 4.3 能力代理层

职责：

- 调用需求分析角色
- 调用测试设计角色
- 调用代码实现角色
- 调用失败修复角色
- 调用结果评估器

这一层可以先共用同一个模型提供者，用不同 prompt role 实现；后续再替换为真正多智能体。

### 4.4 执行与沙箱层

职责：

- 准备工作区
- 写入测试文件和实现文件
- 运行测试
- 收集 stdout、stderr、退出码、生成文件、patch

这一层可以继续复用 OpenHands 的 sandbox 或工具执行能力。

## 5. 核心状态机

建议第一版采用如下状态机：

```text
TaskCreated
  -> RequirementAnalysis
  -> TestDesign
  -> CodeImplementation
  -> SandboxExecution
  -> ResultEvaluation
    -> FinishSuccess
    -> RepairImplementation
      -> SandboxExecution
      -> ResultEvaluation
    -> FinishFailed
```

其中：

- `RequirementAnalysis` 负责把用户需求整理为可实现目标
- `TestDesign` 负责先产出测试，再定义通过标准
- `CodeImplementation` 只根据需求产物和测试产物实现代码
- `SandboxExecution` 负责真实运行测试
- `ResultEvaluation` 负责判断是否通过、是否进入修复、是否终止
- `RepairImplementation` 只允许根据失败信息修复，不重写需求和测试基线

## 6. 各阶段职责

### 6.1 RequirementAnalysis

输入：

- 用户 prompt
- 仓库上下文
- 当前文件、选区、报错、测试日志
- 执行模式和约束

输出不应只有 User Story，还应至少包含：

- `problem_statement`
- `scope`
- `out_of_scope`
- `acceptance_criteria`
- `constraints`
- `interfaces_or_contracts`
- `assumptions`

这一阶段的目标不是开始写代码，而是收敛任务边界。

### 6.2 TestDesign

输入：

- 需求分析产物

输出建议包含：

- `test_plan`
- `test_cases`
- `expected_behaviors`
- `test_files`
- `fixtures`
- `pass_criteria`

关键要求：

- 测试先于实现产出
- 测试内容尽量覆盖 acceptance criteria
- 需要区分单元测试、集成测试、边界测试
- 必须标记哪些测试是本轮新增，哪些是已有回归测试

### 6.3 CodeImplementation

输入：

- 需求分析产物
- 测试设计产物

输出建议包含：

- `implementation_plan`
- `changed_files`
- `patch`
- `rationale`

这一阶段应避免重新解释需求，更不应反向修改测试目标。

### 6.4 SandboxExecution

输入：

- 当前工作区
- 新增测试
- 实现代码
- 运行策略

输出必须结构化，而不是只给一段日志：

- `exit_code`
- `passed`
- `failed_tests`
- `passed_tests`
- `stdout`
- `stderr`
- `duration_ms`
- `artifacts`
- `workspace_diff`

### 6.5 ResultEvaluation

输入：

- 测试设计产物
- 执行结果
- 当前修复轮次

输出：

- `decision`
  - `success`
  - `repair`
  - `failed`
- `failure_summary`
- `repair_targets`
- `stop_reason`

### 6.6 RepairImplementation

输入：

- 原始需求产物
- 测试设计产物
- 执行失败结果
- 历史修复记录

输出：

- `repair_plan`
- `changed_files`
- `patch`
- `reasoning_summary`

这一阶段只允许修实现，原则上不回写测试基线。  
只有在明确识别出测试设计错误时，才允许走受控的“测试修订”分支，但这不应是 v1 默认能力。

## 7. 结构化中间产物

这套框架能否稳定，取决于中间产物是否结构化。

建议后端内部至少维护以下对象：

### 7.1 RequirementSpec

```json
{
  "task_id": "task_xxx",
  "problem_statement": "修复用户登录后 token 刷新失效的问题",
  "scope": ["auth refresh flow", "token persistence"],
  "out_of_scope": ["UI redesign"],
  "acceptance_criteria": [
    "token 过期后可以自动刷新",
    "刷新失败时用户被安全登出"
  ],
  "constraints": [
    "保持现有接口不变",
    "不引入新的外部依赖"
  ]
}
```

### 7.2 TestSpec

```json
{
  "requirement_version": 1,
  "test_cases": [
    {
      "id": "tc_refresh_success",
      "kind": "unit",
      "purpose": "验证 token 过期后自动刷新",
      "expected_result": "返回新 token 并更新缓存"
    }
  ],
  "pass_criteria": [
    "新增测试全部通过",
    "关键回归测试不失败"
  ]
}
```

### 7.3 ImplementationSpec

```json
{
  "iteration": 1,
  "implementation_plan": [
    "补充 token 刷新逻辑",
    "在刷新失败时清理会话状态"
  ],
  "changed_files": ["app/auth/service.py", "tests/test_auth_refresh.py"]
}
```

### 7.4 ExecutionReport

```json
{
  "iteration": 1,
  "passed": false,
  "exit_code": 1,
  "failed_tests": [
    {
      "name": "test_refresh_success",
      "message": "expected refreshed token but got None"
    }
  ],
  "duration_ms": 4280
}
```

### 7.5 RepairRecord

```json
{
  "iteration": 2,
  "based_on_iteration": 1,
  "failure_summary": "刷新函数未写回新 token",
  "repair_targets": ["app/auth/service.py"]
}
```

## 8. 编排器职责

编排器不是简单的“调用下一个 agent”，而是任务真相源。

它至少要负责：

- 为每个任务分配全局 `task_id`
- 维护阶段状态与轮次计数
- 持久化中间产物
- 控制最大修复轮次
- 将结构化产物转换为前端事件
- 处理取消、超时、审批和失败终止

建议在 v1 就加入以下控制：

- `max_repair_iterations`
- `max_total_runtime_ms`
- `max_test_runtime_ms`
- `allow_test_revision`
- `workspace_write_policy`

## 9. 与 OpenHands 的关系

这是最关键的边界定义。

推荐定位：

- OpenHands 是执行能力提供者
- 不是 IDE 产品协议
- 也不是最终的 TDD 编排框架

更具体地说，OpenHands 可以承担：

- 沙箱准备
- 命令执行
- 文件操作
- 补丁生成
- 工具调用

但以下内容应由我们自己掌握：

- TDD 状态机
- 中间产物格式
- 任务阶段划分
- 失败回流策略
- 前端可见事件模型

换句话说，未来应逐步把架构演进为：

`Void 前端 -> bridge 协议 -> 自研 TDD orchestrator -> OpenHands sandbox/tooling`

而不是：

`Void 前端 -> 直接适配 OpenHands 原生事件流`

## 10. 前端需要配合的变化

前端现在不需要重做，但为了支持这套框架，后续最好逐步补充几类稳定事件：

- `task.stage_changed`
- `task.artifact`
- `task.test_plan`
- `task.execution_report`
- `task.repair_started`
- `task.repair_result`

前端展示应重点围绕这些语义层事件，而不是原样打印后端内部日志。

前端最值得提前准备的区域：

- 阶段时间线
- 需求摘要卡片
- 测试计划卡片
- 执行报告卡片
- 修复轮次卡片
- 最终交付卡片

这能让前端从“日志窗口”升级为“任务过程面板”。

## 11. 第一版实现建议

建议分三步推进。

### 11.1 MVP 1：单轮 TDD

只实现：

- RequirementAnalysis
- TestDesign
- CodeImplementation
- SandboxExecution
- FinishSuccess 或 FinishFailed

不做自动修复循环。

目标：

- 先证明结构化阶段能跑通
- 先定义中间产物格式
- 先定义前端事件模型

### 11.2 MVP 2：失败修复循环

加入：

- ResultEvaluation
- RepairImplementation
- 最大修复轮次控制

目标：

- 让任务可以根据失败测试自动修复
- 同时防止无限循环

### 11.3 MVP 3：策略与审批

加入：

- 测试修订策略
- 命令审批策略
- 文件写入策略
- 风险操作拦截

目标：

- 从“能跑”提升到“可控”

## 12. 第一版不要过早做的事

以下内容建议延后：

- 真正的多模型并发协作
- 复杂 DAG 编排
- 自动重写测试用例
- 大规模长期记忆
- 直接复用 OpenHands 全量事件到前端

这些方向不是没价值，而是会过早放大系统复杂度。

## 13. 成功标准

如果第一版框架完成，应该至少满足：

- 前端可以看到明确的阶段流转
- 每阶段都有结构化产物可回放
- 测试先于实现产出
- 执行结果不是一段原始日志，而是结构化报告
- 失败时能明确知道是需求问题、测试问题还是实现问题
- 更换执行引擎时，前端协议基本不变

## 14. 推荐结论

这条路线值得做，而且应该尽快把“OpenHands 作为执行能力层”与“自研 TDD 编排层”切开。

最务实的落地方式不是一步到位做复杂多智能体平台，而是：

1. 先定义状态机
2. 先定义中间产物
3. 先定义前端事件模型
4. 再把 OpenHands 缩到执行层
5. 最后再演进为真正多智能体

如果按照这个顺序推进，你们做出来的不是“套壳 OpenHands 的 IDE”，而是“有自己后端方法论的 IDE”。
