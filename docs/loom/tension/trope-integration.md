# Trope/Worldview RAG 库集成 / Trope Integration

---

## 1. 现有 RAG 库盘点

```
rag/                          ← 现有目录
├── tropes/                   ← 套路/情节模式库
├── worldviews/               ← 世界观设定库
└── audience/                 ← 读者偏好库
```

现有 `steering_library_service.py` 已经支持从 `rag/` 目录加载文档并做检索。

---

## 2. Tension 层如何使用 RAG 库

### 2.1 Obstacle 样例检索

```python
def retrieve_obstacle_examples(
    obstacle_type: str,
    branch_id: str,
    top_k: int = 3
) -> list[RagExample]:
    """
    从 rag/tropes/ 目录检索与 obstacle_type 匹配的样例。
    使用现有 steering_library_service 的检索能力。
    """
    query = f"{obstacle_type} 情节障碍 叙事张力"
    results = steering_library_service.retrieve(
        query=query,
        library_type="tropes",
        top_k=top_k
    )
    return [RagExample(source=r.source, example=r.text) for r in results]
```

### 2.2 世界观约束过滤

```python
def filter_obstacles_by_worldview(
    suggestions: list[ObstacleSuggestion],
    branch_id: str
) -> list[ObstacleSuggestion]:
    """
    根据当前小说的世界观设定，过滤掉不合适的 obstacle 类型。
    例如：现代都市小说不应推荐"魔法系统崩溃"类型的 obstacle。
    """
    worldview = get_branch_worldview(branch_id)  # 从 graph_nodes 获取世界观节点
    worldview_constraints = steering_library_service.get_worldview_constraints(worldview)

    return [
        s for s in suggestions
        if not conflicts_with_worldview(s.obstacle_type, worldview_constraints)
    ]
```

---

## 3. RAG 库扩展建议

为了让 Tension 层的 obstacle injection 更准确，建议在现有 `rag/` 目录下补充：

```
rag/
├── tropes/
│   ├── external-obstacles/    ← 外部障碍样例（已有部分）
│   ├── interpersonal-conflicts/  ← 人际冲突样例（建议补充）
│   ├── internal-struggles/    ← 内心挣扎样例（建议补充）
│   └── plot-reversals/        ← 情节逆转样例（建议补充）
└── tension-patterns/          ← 新增：张力模式库
    ├── low-tension-fixes.md   ← 低张力修复方案
    └── escalation-patterns.md ← 冲突升级模式
```

---

## 4. 与现有 steering_pack 的关系

现有 `steering_pack`（人工指定创新导向）和 Loom tension 层的关系：

```
人工 steering_pack（现有，不变）：
  由 operator 手动指定创新方向（worldview/trope/audience）
  优先级最高，覆盖 Loom 的自动建议

Loom obstacle injection（新增，补充）：
  自动检测张力不足并给出建议
  优先级低于人工 steering_pack
  当 steering_pack 已指定时，obstacle injection 仍运行但标记为"参考建议"
```

---

返回 [Tension 层入口](./README.md) | [Obstacle 注入](./obstacle-injection.md)
