# 测试代码生成 Workflow Draft

状态：草案  
最后更新：`2026-09-05`

## 1. 目标

这一阶段负责把上一阶段产出的：

- `test_plan`
- `test_cases`
- workflow `plan`

转换成结构化的测试代码草案。

当前阶段：

- 只生成测试代码
- 不生成业务实现代码
- 不自动写入工作区

## 2. 接口

前端调用：

```text
POST /v1/test-code-generation/runs
```

输入核心字段：

- `input.story_units`
- `input.test_plan`
- `input.test_cases`
- `input.plan`

输出核心字段：

- `implementation_plan`
- `test_files`
- `changed_files`
- `rationale`
- `warnings`
- `quality_checks`

## 3. 质量要求

- 每个生成文件都必须是测试文件。
- 每个输入测试用例都必须被至少一个测试文件覆盖。
- `changed_files` 必须包含所有生成的测试文件路径。
- 生成内容必须是完整测试文件文本，而不是零散片段。

## 4. 前端职责

前端会基于：

- 需求分析结果
- 测试用例生成结果

自动生成一份 `Test Code Draft / Plan`，用户可以继续补充：

- 期望测试框架
- fixture 需求
- 参数化要求
- 文件拆分策略

## 5. 后续建议

测试代码草案进入第四阶段时，不应直接写入用户工作区。应按 [沙箱执行协议 v1](./sandbox-execution-protocol-v1.md) 交付：

- `test_files`
- 结构化 `command.argv`
- 执行策略
- 来源追踪信息

当前兼容接口可以接收旧的 `test_command` 字符串，但新实现应以 `sandbox-execution.v1` 为准。

如果下一步要进入正式隔离执行，可继续补：

- Docker 沙箱
- 网络与资源限制
- 运行事件流和取消接口
- 汇总失败并回到 repair 阶段
