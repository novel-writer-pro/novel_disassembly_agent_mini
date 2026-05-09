# Tension 层入口 / 叙事张力自动调节

> Tension 层解决的核心问题：**情节平淡/重复无自动检测**。
> 当前完全依赖人工 steering，批量仿写时质量不稳定。

---

## 与 0509 控制层的关系

```
0509 operator_surface（展示张力信号，不变）
        ↑
        │ 接收 tension_signal（新信号）
        │
Loom tension 层（指标计算 + 信号输出，新增）
        │ 直接用现有 pgvector + GraphEdge 计算
        ↓
ChunkEmbedding（pgvector）+ GraphEdge（冲突密度）+ FactRecord（新实体）
```

Tension 层是 0509 operator_surface 的**信号提供者**，不直接写入 action_queue，
operator 看到张力警告后自行决定是否创建 tension_intervention ticket。

同时，张力指标是 0509 **Full Control Console**（🔴 未实现）的关键实时质量指标。

---

## 三个张力指标

| 指标 | 计算方法 | 数据来源 | 含义 |
|------|---------|---------|------|
| `plot_similarity_score` | pgvector cosine 相似度 | `chunk_embeddings` | 当前章节与前 N 章的情节相似度，越高越平淡 |
| `conflict_density` | GraphEdge 统计 | `graph_edges`（edge_type=conflict） | 每千字的冲突事件密度，越低越平淡 |
| `surprise_index` | 新实体比例 | `fact_records`（新 vs 已知） | 新引入实体/关系占比，越低越重复 |

**关键优势**：三个指标全部用现有数据计算，**不需要新的 LLM 调用**。

---

## 文档清单

| 文档 | 说明 |
|------|------|
| [tension-metrics.md](./tension-metrics.md) | 三个指标的完整计算方法 |
| [obstacle-injection.md](./obstacle-injection.md) | Obstacle 自动注入机制 |
| [trope-integration.md](./trope-integration.md) | 与现有 trope/worldview RAG 库集成 |

---

返回 [Loom 入口](../README.md)
