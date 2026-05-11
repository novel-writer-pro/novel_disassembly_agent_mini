# Memory 层入口 / 分层记忆 + 冲突代谢

> Memory 层解决的核心问题：**长书仿写时记忆线性退化**。
> 当前 `carry_over_state` 是 JSON 追加，章节越多冲突越多，模型越难处理。

---

## 与 0509 控制层的关系

```
0509 session_state（运营容器，不变）
        ↑
        │ 消费 carry_over_state（格式不变，内容更好）
        │
Loom memory 层（组装器，新增）
        │ 从三层记忆动态组装
        ↓
Working Memory ← Episodic Memory ← Semantic Memory
（当前上下文）    （事件序列）        （知识图谱，PostgreSQL）
```

Memory 层是 0509 的**上游供应商**，不替换 0509，只改善 carry_over_state 的内容质量。

---

## 三层记忆结构

| 层次 | 内容 | 现有 DB 映射 | 更新频率 |
|------|------|------------|---------|
| **Working Memory** | 当前章节上下文（~2000 tokens） | `window_artifacts`（最近窗口） | 每章 |
| **Episodic Memory** | 事件序列，按重要性排序 | `fact_records` + `importance_score`（新增字段） | 每章，有衰减 |
| **Semantic Memory** | 知识图谱：角色/关系/规则/世界观 | `graph_nodes` + `graph_edges` + `conflict_status`（新增字段） | 每章，有版本 |

---

## 文档清单

| 文档 | 说明 |
|------|------|
| [layered-memory-design.md](./layered-memory-design.md) | 三层记忆完整设计 + DB 扩展方案 |
| [conflict-metabolism.md](./conflict-metabolism.md) | 冲突代谢机制（contradiction/evolution/ambiguity） |
| [carry-over-migration.md](./carry-over-migration.md) | 从现有 carry_over_state 迁移方案 |

---

返回 [Loom 入口](../README.md)
