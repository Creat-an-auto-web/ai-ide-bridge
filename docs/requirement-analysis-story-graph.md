# 需求分析故事依赖图交付物

状态：草案  
最后更新：`2026-05-26`

需求分析阶段除了交付用户故事列表，还应交付故事之间的依赖关系，供测试用例生成阶段规划测试顺序和端到端组合场景。

## 1. 严格依赖图

`story_dependency_graph` 只表示严格前置或顺序依赖，必须是有向无环图。

边方向统一为：

```text
from 前置故事 -> to 后续故事
```

示例：

```json
{
  "story_dependency_graph": {
    "nodes": [
      {
        "story_id": "S1",
        "title": "访客可以注册论坛账号",
        "capability_group_id": "CG1"
      },
      {
        "story_id": "S2",
        "title": "已注册用户可以登录论坛",
        "capability_group_id": "CG1"
      }
    ],
    "edges": [
      {
        "from": "S1",
        "to": "S2",
        "type": "business_precondition",
        "reason": "登录依赖已有账号"
      }
    ],
    "entry_story_ids": ["S1"],
    "terminal_story_ids": ["S2"],
    "is_dag": true,
    "warnings": []
  }
}
```

允许的依赖边类型：

- `business_precondition`
- `state_precondition`
- `data_precondition`
- `permission_precondition`
- `workflow_sequence`

## 2. 非严格关系

`story_relationships` 表示不适合放入 DAG 的关系，例如组合、替代、扩展和保护关系。

示例：

```json
{
  "story_relationships": [
    {
      "source": "S3",
      "target": "S5",
      "type": "integration_composition",
      "reason": "发帖与点赞需要组合成帖子互动场景验证"
    }
  ]
}
```

允许的关系类型：

- `integration_composition`
- `alternative_path`
- `extends_behavior`
- `guards_behavior`

## 3. 当前实现策略

当前需求分析模型可以直接返回 `story_dependency_graph` 和 `story_relationships`。

如果模型没有返回 `story_dependency_graph`，系统会根据每条 `story_units[].dependencies` 自动派生依赖图，保证测试生成阶段始终可以收到基础 DAG。
