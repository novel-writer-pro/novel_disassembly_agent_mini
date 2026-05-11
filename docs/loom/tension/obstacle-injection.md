# Obstacle 自动注入机制 / Obstacle Injection

---

## 1. 定位

> Obstacle injection 是张力不足时的**建议生成器**，不是自动执行器。
> 它输出"建议注入什么类型的障碍"，operator 或 harness 决定是否采纳。

---

## 2. 触发条件

```python
# 触发 obstacle injection 的条件（任一满足）
TRIGGER_CONDITIONS = [
    tension_score.plot_similarity > 0.85,      # 情节高度重复
    tension_score.conflict_density < 0.5,       # 冲突密度过低
    tension_score.surprise_index < 0.1,         # 几乎没有新元素
    tension_score.tension_score < 0.3,          # 综合张力评分过低
]
```

---

## 3. Obstacle 类型库

基于叙事学理论（参考 KG+Literary Theory 2025），定义以下 obstacle 类型：

```python
OBSTACLE_TYPES = {
    # 外部障碍
    "external_threat": "引入外部威胁（新敌人、自然灾害、政治变局）",
    "resource_scarcity": "引入资源稀缺（时间压力、物资不足、能力限制）",
    "information_gap": "引入信息缺口（关键信息被隐藏、误导、延迟）",

    # 人际障碍
    "relationship_conflict": "引入人际冲突（信任危机、利益冲突、价值观分歧）",
    "betrayal_risk": "引入背叛风险（盟友动摇、内部矛盾）",
    "moral_dilemma": "引入道德困境（两难选择、价值观冲突）",

    # 内部障碍
    "character_flaw": "激活角色缺陷（弱点暴露、旧伤复发）",
    "identity_crisis": "引入身份危机（角色认知动摇、目标质疑）",
    "past_consequence": "引入过去的代价（旧事重提、因果报应）",

    # 情节障碍
    "unexpected_reversal": "引入意外逆转（计划失败、意外发现）",
    "foreshadow_activation": "激活已有伏笔（之前埋下的线索开始发酵）",
    "escalation": "升级现有冲突（已有矛盾激化）",
}
```

---

## 4. 障碍选择逻辑

```python
def suggest_obstacles(
    branch_id: str,
    chapter_index: int,
    tension_score: TensionScore,
    top_k: int = 3
) -> list[ObstacleSuggestion]:
    """
    根据张力评分和当前叙事状态，推荐最合适的 obstacle 类型。
    """
    suggestions = []

    # 根据触发原因选择 obstacle 类型
    if tension_score.plot_similarity > 0.85:
        # 情节重复 → 优先推荐能引入新元素的 obstacle
        candidates = ["unexpected_reversal", "foreshadow_activation", "external_threat"]
    elif tension_score.conflict_density < 0.5:
        # 冲突不足 → 优先推荐能增加冲突的 obstacle
        candidates = ["relationship_conflict", "moral_dilemma", "betrayal_risk"]
    elif tension_score.surprise_index < 0.1:
        # 新颖度不足 → 优先推荐能引入新角色/事件的 obstacle
        candidates = ["external_threat", "past_consequence", "identity_crisis"]
    else:
        candidates = list(OBSTACLE_TYPES.keys())

    # 结合当前叙事状态过滤（避免推荐不合适的 obstacle）
    active_threads = get_active_threads(branch_id, chapter_index)
    unresolved_foreshadows = get_unresolved_foreshadows(branch_id, chapter_index)

    # 如果有未解决的伏笔，优先推荐激活伏笔
    if unresolved_foreshadows and "foreshadow_activation" in candidates:
        candidates = ["foreshadow_activation"] + [c for c in candidates if c != "foreshadow_activation"]

    # 从 trope/worldview RAG 库检索匹配的具体 obstacle 样例
    for obstacle_type in candidates[:top_k]:
        rag_examples = retrieve_obstacle_examples(obstacle_type, branch_id)
        suggestions.append(ObstacleSuggestion(
            obstacle_type=obstacle_type,
            description=OBSTACLE_TYPES[obstacle_type],
            rag_examples=rag_examples[:2],  # 最多 2 个样例
            fit_score=compute_fit_score(obstacle_type, active_threads, unresolved_foreshadows)
        ))

    return sorted(suggestions, key=lambda x: x.fit_score, reverse=True)
```

---

## 5. 输出格式

```json
{
  "obstacle_suggestions": [
    {
      "obstacle_type": "foreshadow_activation",
      "description": "激活已有伏笔（之前埋下的线索开始发酵）",
      "fit_score": 0.92,
      "rag_examples": [
        {
          "source": "rag/tropes/foreshadow-activation-examples.md",
          "example": "第5章埋下的神秘符文，在第42章被敌人利用..."
        }
      ],
      "related_threads": ["神秘符文线索（第5章）", "古老预言（第12章）"]
    },
    {
      "obstacle_type": "relationship_conflict",
      "description": "引入人际冲突（信任危机、利益冲突、价值观分歧）",
      "fit_score": 0.75,
      "rag_examples": [...],
      "related_characters": ["张三", "李四"]
    }
  ],
  "trigger_reason": "plot_similarity=0.87，情节重复度过高",
  "action_required": false,
  "operator_note": "以上为建议，operator 可选择采纳或忽略"
}
```

---

## 6. 与 0509 action_queue 的关系

**重要约定**：Obstacle injection **不直接写入** 0509 的 `action_queue`。

```
Loom tension 层输出：obstacle_suggestions（建议列表）
                    ↓
0509 operator_surface 展示（operator 看到建议）
                    ↓
operator 决策：是否创建 tension_intervention ticket
                    ↓
0509 action_queue 写入（由 operator 手动触发）
```

这样保证了 operator 的最终决策权，Loom 只是信号提供者。

---

## 7. 验收标准

- [ ] `suggest_obstacles()` 在张力不足时返回 ≥ 1 个建议
- [ ] 建议的 `fit_score` 与人工判断的相关性 > 0.6
- [ ] 建议正确展示在 0509 operator_surface 的 `obstacle_suggestions` 字段
- [ ] 不直接写入 0509 action_queue（operator 决策权保留）

---

返回 [Tension 层入口](./README.md) | [张力指标](./tension-metrics.md) | [Trope 集成](./trope-integration.md)
