# 风格向量化与漂移检测 / Style Vector & Drift Detection

---

## 1. 问题定位

**现状**：风格轴（style_axes）是文字描述，无法量化"当前章节与目标风格的距离"。
100 章后风格可能已悄悄偏移，但系统无法检测。

**解法**：用现有 `ChunkEmbedding`（pgvector）计算风格向量，与参考章节对比，输出 `style_drift_score`。

---

## 2. 接口约定

```json
{
  "style_signal": {
    "style_drift_score": 0.12,
    "reference_chapter_index": 1,
    "drift_direction": "neutral | verbose | terse | melodramatic | flat",
    "alert_level": "none | warn | critical",
    "recalibration_suggestion": "当前章节语言密度偏高，建议参考第1-5章的节奏"
  }
}
```

**阈值建议**：
- `style_drift_score < 0.15`：✅ 风格稳定
- `0.15 - 0.30`：🟡 轻微漂移，建议关注
- `> 0.30`：🔴 明显漂移，建议重新校准

---

## 3. 计算方法

### 3.1 风格向量提取

```python
def compute_style_vector(branch_id: str, chapter_index: int) -> list[float]:
    """
    从现有 chunk_embeddings 提取章节风格向量。
    取该章节所有 chunk 的 embedding 均值，作为章节级风格向量。
    直接复用现有 ChunkEmbedding 表，不需要新的 embedding 调用。
    """
    # SQL 实现（高效）
    # SELECT AVG(vector_payload) FROM chunk_embeddings ce
    # JOIN retrieval_chunks rc ON ce.chunk_id = rc.id
    # JOIN retrieval_documents rd ON rc.document_id = rd.id
    # WHERE rd.branch_id = :branch_id AND rd.chapter_index = :chapter_index
```

### 3.2 漂移计算

```python
def compute_style_drift(
    branch_id: str,
    chapter_index: int,
    reference_window: int = 5,  # 参考前 N 章
) -> StyleDriftResult:
    """
    计算当前章节与参考窗口的风格距离。
    参考窗口：取前 reference_window 章的风格向量均值作为基准。
    """
    current_vector = compute_style_vector(branch_id, chapter_index)
    reference_vectors = [
        compute_style_vector(branch_id, chapter_index - i)
        for i in range(1, reference_window + 1)
        if chapter_index - i >= 1
    ]
    if not reference_vectors:
        return StyleDriftResult(style_drift_score=0.0, alert_level="none")

    reference_mean = mean_vector(reference_vectors)
    drift_score = cosine_distance(current_vector, reference_mean)
    return StyleDriftResult(
        style_drift_score=round(drift_score, 4),
        alert_level=_classify_drift(drift_score),
    )
```

### 3.3 风格锚点（Semantic Memory 集成）

```python
# 在 Loom memory 层的 semantic_snapshot 中存储风格锚点
semantic_snapshot = {
    "character_count": 12,
    "active_rules": [...],
    "key_relationships": [...],
    "style_anchor": {                    # 新增字段
        "reference_chapters": [1, 2, 3, 4, 5],
        "anchor_vector": [...],          # 参考章节的均值风格向量
        "anchor_computed_at": "2026-05-10T..."
    }
}
```

---

## 4. 漂移方向分类

```python
DRIFT_DIRECTIONS = {
    "verbose":      "语言密度上升，句子变长，修辞增多",
    "terse":        "语言密度下降，句子变短，描写减少",
    "melodramatic": "情感强度上升，感叹句增多",
    "flat":         "情感强度下降，叙述趋于平淡",
    "neutral":      "无明显方向性漂移",
}
```

漂移方向通过对比当前向量与参考向量在各维度的偏移方向推断，
不需要额外的分类模型，直接用向量差的主成分方向。

---

## 5. 与现有系统的集成

### preflight_imitation 接入

```python
# feature flag: loom_style_enabled（默认 False）
if settings.loom_style_enabled:
    style_result = style_calibration_service.compute_style_drift(
        branch_id=branch_id,
        chapter_index=chapter_index,
    )
    if style_result.alert_level == "critical":
        preflight_notes.append(PrefligtNote(
            level="warn",
            checker="loom_style_drift",
            message=f"风格漂移过大（score={style_result.style_drift_score}），建议重新校准",
        ))
```

### loom-status 输出

```
=== Loom Style Status ===
style_drift_score:   0.12
drift_direction:     neutral
alert_level:         none
reference_chapters:  1-5
```

---

## 6. 验收标准

- `style_drift_score` 与人工风格评分 Pearson r ≥ 0.5
- 计算时间 < 500ms（纯 SQL 查询，无 LLM 调用）
- feature flag 关闭时，现有链路完全不受影响

---

返回 [Style 层入口](./README.md) | [节奏分析设计](./rhythm-analysis-design.md)
