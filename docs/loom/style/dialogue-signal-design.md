# 对话质量信号设计 / Dialogue Signal Design

---

## 1. 问题定位

**现状**：系统只能从 `fact_records` 抽取 dialogue candidates，没有：
- 角色说话风格一致性检测（同一角色在不同章节说话方式是否一致）
- 对话信息效率检查（对话是否推进情节，还是只是填充）
- 冲突对话密度（对话中有多少是有张力的交锋）

**商业影响**：对话质量是读者评价"角色有没有灵魂"的核心感知点。

---

## 2. 接口约定

```json
{
  "dialogue_signal": {
    "character_voice_consistency": {
      "张三": 0.82,
      "李四": 0.71,
      "overall": 0.76
    },
    "dialogue_efficiency": 0.65,
    "conflict_dialogue_density": 0.38,
    "dialogue_ratio": 0.42,
    "alert_level": "none | warn | critical",
    "suggestion": "李四的说话风格与前5章差异较大，建议检查角色一致性"
  }
}
```

---

## 3. 三个核心指标

### 3.1 character_voice_consistency（角色说话风格一致性）

```python
def compute_character_voice_consistency(
    branch_id: str,
    chapter_index: int,
    character_name: str,
    lookback_n: int = 5,
) -> float:
    """
    计算当前章节中某角色的说话风格与前 N 章的一致性。
    方法：提取该角色的对话文本，计算 embedding，与历史对话 embedding 对比。
    直接复用现有 ChunkEmbedding，不需要新的 embedding 调用。
    """
    current_dialogues = get_character_dialogues(branch_id, chapter_index, character_name)
    if not current_dialogues:
        return 1.0  # 无对话，视为一致

    historical_dialogues = [
        get_character_dialogues(branch_id, chapter_index - i, character_name)
        for i in range(1, lookback_n + 1)
        if chapter_index - i >= 1
    ]
    historical_flat = [d for ds in historical_dialogues for d in ds]
    if not historical_flat:
        return 1.0  # 无历史对话，无法对比

    current_vector = mean_embedding(current_dialogues)
    historical_vector = mean_embedding(historical_flat)
    return round(1.0 - cosine_distance(current_vector, historical_vector), 4)
```

**阈值建议**：
- `> 0.75`：✅ 角色声音一致
- `0.60 - 0.75`：🟡 轻微漂移，建议关注
- `< 0.60`：🔴 明显漂移，建议检查

### 3.2 dialogue_efficiency（对话信息效率）

```python
def compute_dialogue_efficiency(
    branch_id: str,
    chapter_index: int,
) -> float:
    """
    对话推进情节的效率。
    方法：统计对话中包含 fact_record 事件的比例。
    对话行中有新事件/信息披露/决策 → 高效对话
    对话行中只有情感表达/寒暄 → 低效对话
    """
    dialogue_facts = count_dialogue_facts(branch_id, chapter_index)
    total_dialogue_lines = count_dialogue_lines(branch_id, chapter_index)
    if total_dialogue_lines == 0:
        return 1.0
    return round(dialogue_facts / total_dialogue_lines, 4)
```

**阈值建议**：
- `> 0.5`：✅ 对话推进情节
- `0.3 - 0.5`：🟡 对话效率一般
- `< 0.3`：🔴 对话填充过多，建议精简

### 3.3 conflict_dialogue_density（冲突对话密度）

```python
def compute_conflict_dialogue_density(
    branch_id: str,
    chapter_index: int,
) -> float:
    """
    对话中冲突/交锋的比例。
    从 graph_edges 中统计本章对话相关的 conflict 类型边。
    """
    conflict_dialogue_edges = count_conflict_dialogue_edges(branch_id, chapter_index)
    total_dialogue_lines = count_dialogue_lines(branch_id, chapter_index)
    if total_dialogue_lines == 0:
        return 0.0
    return round(conflict_dialogue_edges / total_dialogue_lines, 4)
```

---

## 4. 与 Reward 层的集成

```python
# dialogue_signal 进入 pairwise 评估第五个维度
class PairwiseResult:
    dimensions: dict[str, DimensionResult] = {
        "character_consistency": ...,
        "plot_coherence": ...,
        "style_fidelity": ...,
        "narrative_tension": ...,
        "dialogue_quality": ...,   # 新增第五维度
    }

# dialogue_quality 的 heuristic 计算
def _heuristic_dialogue_quality(
    draft_a: str,
    draft_b: str,
    signal_a: dict,
    signal_b: dict,
) -> DimensionResult:
    score_a = (
        signal_a.get("dialogue_efficiency", 0.5) * 0.4
        + signal_a.get("conflict_dialogue_density", 0.3) * 0.3
        + signal_a.get("character_voice_consistency", {}).get("overall", 0.7) * 0.3
    )
    score_b = (
        signal_b.get("dialogue_efficiency", 0.5) * 0.4
        + signal_b.get("conflict_dialogue_density", 0.3) * 0.3
        + signal_b.get("character_voice_consistency", {}).get("overall", 0.7) * 0.3
    )
    diff = score_a - score_b
    if abs(diff) < 0.05:
        return DimensionResult(winner="tie", score_diff=0.0)
    return DimensionResult(
        winner="A" if diff > 0 else "B",
        score_diff=round(abs(diff), 4),
    )
```

---

## 5. 接入点

```python
# ChapterImitationHarnessReport 新增字段（feature flag: loom_pairwise_enabled）
@dataclass
class ChapterImitationHarnessReport:
    ...
    chapter_quality_signal: dict[str, object] = field(default_factory=dict)
    dialogue_signal: dict[str, object] = field(default_factory=dict)  # 新增
```

---

## 6. 数据来源

| 指标 | 数据来源 | 是否需要新 LLM 调用 |
|------|---------|-----------------|
| `character_voice_consistency` | `chunk_embeddings`（对话 chunk） | ❌ 不需要 |
| `dialogue_efficiency` | `fact_records`（对话相关事件） | ❌ 不需要 |
| `conflict_dialogue_density` | `graph_edges`（conflict 类型） | ❌ 不需要 |

---

## 7. 验收标准

- `dialogue_signal` 与人工对话评分 Kendall's τ ≥ 0.4
- 计算时间 < 300ms（纯 DB 查询）
- feature flag 关闭时，现有链路完全不受影响

---

返回 [Style 层入口](./README.md) | [节奏分析设计](./rhythm-analysis-design.md)
