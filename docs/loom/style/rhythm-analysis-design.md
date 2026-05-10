# 节奏分析器设计 / Rhythm Analysis Design

---

## 1. 问题定位

**现状**：有 `hook_score`（章末钩子）和 `scene_beats`（场景节拍），但缺乏：
- 爽点密度模型（每千字有多少个情绪高点）
- 节奏类型识别（慢热型 / 动作密集型 / 均衡型）
- 高潮点检测（全书哪些章节是情节高峰）

**商业影响**：爽点密度直接决定读者留存率，是网文商业化的核心指标。

---

## 2. 接口约定

```json
{
  "rhythm_signal": {
    "hook_density": 2.3,
    "pacing_type": "balanced",
    "climax_score": 0.72,
    "satisfaction_density": 1.8,
    "alert_level": "none | warn | critical",
    "suggestion": "当前章节爽点密度偏低，建议在第3场景后增加一个小高潮"
  }
}
```

**阈值建议**：
- `hook_density < 1.0`（每千字不足1个钩子）：🔴 节奏过慢，建议加密
- `hook_density 1.0 - 2.5`：✅ 节奏正常
- `hook_density > 4.0`：🟡 节奏过密，可能缺乏铺垫

---

## 3. 三个核心指标

### 3.1 hook_density（钩子密度）

```python
def compute_hook_density(chapter_text: str) -> float:
    """
    每千字的钩子数量。
    钩子定义：情绪高点、悬念设置、冲突爆发、意外反转。
    从现有 fact_records 中统计 event_type 为 hook/climax/reversal 的事件数。
    """
    word_count = len(chapter_text) / 2  # 中文字符数
    hook_events = count_hook_events(branch_id, chapter_index)
    return round(hook_events / (word_count / 1000), 2)
```

### 3.2 pacing_type（节奏类型）

```python
PACING_TYPES = {
    "slow_burn":      "慢热型：铺垫多，高潮少，适合长篇情感线",
    "action_heavy":   "动作密集型：冲突多，节奏快，适合爽文",
    "balanced":       "均衡型：张弛有度，适合大多数题材",
    "episodic":       "章回型：每章独立小故事，适合轻小说",
}

def classify_pacing_type(
    branch_id: str,
    chapter_index: int,
    lookback_n: int = 5,
) -> str:
    """
    根据前 N 章的 tension_score + hook_density 分布判断节奏类型。
    直接复用 tension_service 的计算结果，不需要新的分析。
    """
    tension_scores = [get_tension_score(branch_id, i) for i in range(
        max(1, chapter_index - lookback_n), chapter_index + 1
    )]
    hook_densities = [compute_hook_density_from_db(branch_id, i) for i in range(
        max(1, chapter_index - lookback_n), chapter_index + 1
    )]
    avg_tension = mean(tension_scores)
    avg_hook = mean(hook_densities)
    tension_variance = variance(tension_scores)

    if avg_tension < 0.4 and avg_hook < 1.0:
        return "slow_burn"
    elif avg_tension > 0.7 and avg_hook > 2.5:
        return "action_heavy"
    elif tension_variance > 0.1:
        return "balanced"
    else:
        return "episodic"
```

### 3.3 climax_score（高潮评分）

```python
def compute_climax_score(branch_id: str, chapter_index: int) -> float:
    """
    当前章节是否是情节高峰。
    综合 tension_score + conflict_density + surprise_index 计算。
    直接复用 tension_service 的三个指标，加权求和。
    """
    tension = get_tension_score(branch_id, chapter_index)
    # tension_score 已包含 plot_similarity(反向) + conflict_density + surprise_index
    # climax_score = 1 - plot_similarity + conflict_density + surprise_index 的加权
    return round(
        (1 - tension.plot_similarity_score) * 0.3
        + tension.conflict_density * 0.4
        + tension.surprise_index * 0.3,
        4
    )
```

---

## 4. 与 Tension 层的联动

```
rhythm_signal.hook_density 低
    + tension_signal.conflict_density 低
    → 双重平淡警告（double_flat_alert）
    → 触发更强的 obstacle injection 建议

rhythm_signal.pacing_type == "slow_burn"
    + 连续 5 章 tension_score < 0.3
    → 建议激活 overdue_threads（多线调度，Phase 5）
```

---

## 5. 数据来源

| 指标 | 数据来源 | 是否需要新 LLM 调用 |
|------|---------|-----------------|
| `hook_density` | `fact_records`（event_type 统计） | ❌ 不需要 |
| `pacing_type` | `tension_service` 结果复用 | ❌ 不需要 |
| `climax_score` | `tension_service` 结果复用 | ❌ 不需要 |
| `satisfaction_density` | `fact_records`（satisfaction 类事件） | ❌ 不需要 |

---

## 6. 接入点

```python
# preflight_imitation 接入（feature flag: loom_style_enabled）
if settings.loom_style_enabled:
    rhythm = rhythm_analysis_service.compute_rhythm_signal(
        branch_id=branch_id,
        chapter_index=chapter_index,
    )
    if rhythm.hook_density < 1.0:
        preflight_notes.append(PrefligtNote(
            level="warn",
            checker="loom_rhythm",
            message=f"爽点密度偏低（{rhythm.hook_density}/千字），建议增加情绪高点",
        ))
```

---

## 7. 验收标准

- `hook_density` 与读者留存率正相关（需真实数据验证）
- `pacing_type` 分类与人工判断一致率 ≥ 70%
- 计算时间 < 200ms（纯 DB 统计，无 LLM 调用）

---

返回 [Style 层入口](./README.md) | [风格向量设计](./style-vector-design.md) | [对话信号设计](./dialogue-signal-design.md)
