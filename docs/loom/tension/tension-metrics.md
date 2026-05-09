# 叙事张力指标 / Tension Metrics

---

## 1. 三个指标定义

### 1.1 plot_similarity_score（情节相似度）

**含义**：当前章节与前 N 章的情节语义相似度。越高说明情节越重复，越低说明情节越新颖。

**计算方法**：

```python
def compute_plot_similarity(
    branch_id: str,
    chapter_index: int,
    lookback_n: int = 3
) -> float:
    """
    用 pgvector cosine 相似度计算当前章节与前 N 章的平均相似度。
    直接使用现有 chunk_embeddings 表，不需要新的 embedding 调用。
    """
    # 获取当前章节的 embedding（取章节摘要 chunk 的 embedding）
    current_embedding = get_chapter_summary_embedding(branch_id, chapter_index)

    # 获取前 N 章的 embedding
    prev_embeddings = [
        get_chapter_summary_embedding(branch_id, chapter_index - i)
        for i in range(1, lookback_n + 1)
        if chapter_index - i >= 1
    ]

    if not prev_embeddings:
        return 0.0

    # 计算 cosine 相似度（pgvector 原生支持）
    similarities = [cosine_similarity(current_embedding, e) for e in prev_embeddings]
    return sum(similarities) / len(similarities)

# SQL 实现（更高效）
PLOT_SIMILARITY_SQL = """
SELECT AVG(1 - (ce1.vector_payload <=> ce2.vector_payload)) as similarity
FROM chunk_embeddings ce1
JOIN retrieval_chunks rc1 ON ce1.chunk_id = rc1.id
JOIN retrieval_documents rd1 ON rc1.document_id = rd1.id
JOIN chunk_embeddings ce2 ON TRUE
JOIN retrieval_chunks rc2 ON ce2.chunk_id = rc2.id
JOIN retrieval_documents rd2 ON rc2.document_id = rd2.id
WHERE rd1.branch_id = :branch_id
  AND rd1.chapter_index = :chapter_index
  AND rc1.chunk_order = 0  -- 取摘要 chunk
  AND rd2.branch_id = :branch_id
  AND rd2.chapter_index BETWEEN :chapter_index - :lookback_n AND :chapter_index - 1
  AND rc2.chunk_order = 0
"""
```

**阈值建议**：
- `> 0.85`：🔴 高度重复，强烈建议引入新元素
- `0.70 - 0.85`：🟡 中度相似，建议检查是否有足够变化
- `< 0.70`：✅ 情节新颖度良好

---

### 1.2 conflict_density（冲突密度）

**含义**：每千字的冲突事件密度。越低说明情节越平淡，缺乏张力。

**计算方法**：

```python
def compute_conflict_density(
    branch_id: str,
    chapter_index: int
) -> float:
    """
    统计本章的冲突类型 GraphEdge 数量，除以章节字数。
    直接使用现有 graph_edges 表，不需要新的分析。
    """
    # 统计本章的冲突边（edge_type 包含 conflict/confrontation/opposition 等）
    conflict_edge_count = count_conflict_edges(branch_id, chapter_index)

    # 获取章节字数
    chapter_length = get_chapter_word_count(branch_id, chapter_index)

    if chapter_length == 0:
        return 0.0

    return conflict_edge_count / (chapter_length / 1000)

# 冲突类型的 edge_type 列表（从现有 graph_edges 中统计）
CONFLICT_EDGE_TYPES = [
    "conflict", "confrontation", "opposition",
    "betrayal", "threat", "challenge",
    "power_struggle", "moral_dilemma"
]
```

**阈值建议**（基于中文网文经验值，需要根据实际数据校准）：
- `< 0.5`：🔴 冲突密度过低，情节平淡
- `0.5 - 1.5`：🟡 冲突密度适中
- `> 1.5`：✅ 冲突密度良好

---

### 1.3 surprise_index（新颖度指数）

**含义**：本章新引入的实体/关系占本章总实体/关系的比例。越低说明情节越重复，没有新元素。

**计算方法**：

```python
def compute_surprise_index(
    branch_id: str,
    chapter_index: int
) -> float:
    """
    统计本章新出现的 fact_records 中，
    有多少是在前文中从未出现过的新实体/关系。
    直接使用现有 fact_records 表。
    """
    # 本章的所有 facts
    current_facts = get_chapter_facts(branch_id, chapter_index)

    # 前文已知的所有 fact labels（用 canonical_group 去重）
    known_labels = get_known_fact_labels(branch_id, before_chapter=chapter_index)

    # 计算新颖度
    new_facts = [f for f in current_facts if f.label not in known_labels]
    if not current_facts:
        return 0.0

    return len(new_facts) / len(current_facts)
```

**阈值建议**：
- `< 0.1`：🔴 几乎没有新元素，情节高度重复
- `0.1 - 0.3`：🟡 新元素较少，建议引入新角色/事件
- `> 0.3`：✅ 新颖度良好

---

## 2. 综合张力评分

```python
def compute_tension_score(
    branch_id: str,
    chapter_index: int
) -> TensionScore:
    """
    综合三个指标，输出张力评分和警告。
    """
    similarity = compute_plot_similarity(branch_id, chapter_index)
    density = compute_conflict_density(branch_id, chapter_index)
    surprise = compute_surprise_index(branch_id, chapter_index)

    # 综合评分（越高越好）
    # similarity 越低越好，所以取反
    tension_score = (
        (1 - similarity) * 0.4 +   # 情节新颖度权重 40%
        min(density / 1.5, 1.0) * 0.35 +  # 冲突密度权重 35%
        surprise * 0.25             # 新颖度权重 25%
    )

    alerts = []
    if similarity > 0.85:
        alerts.append(TensionAlert(
            type="high_similarity",
            severity="high",
            message=f"当前章节与前3章相似度 {similarity:.2f}，情节可能过于重复",
            suggestion="考虑引入新的冲突或转折"
        ))
    if density < 0.5:
        alerts.append(TensionAlert(
            type="low_conflict_density",
            severity="medium",
            message=f"冲突密度 {density:.2f}，情节可能过于平淡",
            suggestion="考虑增加角色间的冲突或内心矛盾"
        ))
    if surprise < 0.1:
        alerts.append(TensionAlert(
            type="low_surprise",
            severity="medium",
            message=f"新颖度指数 {surprise:.2f}，几乎没有新元素",
            suggestion="考虑引入新角色、新地点或新信息"
        ))

    return TensionScore(
        chapter_index=chapter_index,
        tension_score=tension_score,
        plot_similarity=similarity,
        conflict_density=density,
        surprise_index=surprise,
        alerts=alerts,
        loom_version="1.0"
    )
```

---

## 3. 接入 Preflight Checks

```python
# 在现有 preflight_imitation 中新增张力检查（feature flag 控制）

class PreflightChecker:
    def run(self, branch_id: str, chapter_index: int) -> PreflightResult:
        results = []

        # 现有 preflight checks（不变）
        results.append(self.check_source_skeleton_alignment(...))
        results.append(self.check_character_motivation(...))
        # ...

        # Loom 新增：张力检查
        if settings.LOOM_TENSION_ENABLED:
            tension = compute_tension_score(branch_id, chapter_index)
            if tension.alerts:
                results.append(PreflightItem(
                    check_name="tension_check",
                    status="warning" if tension.tension_score > 0.3 else "fail",
                    message=f"张力评分 {tension.tension_score:.2f}",
                    details=tension.alerts,
                    suggestion="考虑使用 obstacle injection 增加张力"
                ))

        return PreflightResult(items=results)
```

---

## 4. 输出给 0509 operator_surface

```json
{
  "tension_signal": {
    "chapter_index": 42,
    "tension_score": 0.45,
    "status": "warning",
    "alerts": [
      {
        "type": "high_similarity",
        "severity": "high",
        "message": "当前章节与前3章相似度 0.87，情节可能过于重复",
        "suggestion": "考虑引入新的冲突或转折"
      }
    ],
    "metrics": {
      "plot_similarity": 0.87,
      "conflict_density": 0.6,
      "surprise_index": 0.15
    },
    "loom_version": "1.0"
  }
}
```

---

## 5. 验收标准

- [ ] 三个指标的计算时间 < 1 秒（纯 SQL 查询，无 LLM 调用）
- [ ] `plot_similarity_score` 在已知"情节重复"的章节上 > 0.8
- [ ] `conflict_density` 在已知"情节平淡"的章节上 < 0.5
- [ ] 张力信号正确输出到 0509 operator_surface 的 `tension_signal` 字段
- [ ] feature flag 关闭时，现有 preflight 逻辑完全不受影响

---

返回 [Tension 层入口](./README.md) | [Obstacle 注入](./obstacle-injection.md)
