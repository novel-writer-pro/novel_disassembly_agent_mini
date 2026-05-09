# Pairwise 评估框架设计 / Pairwise Eval Design

---

## 1. 为什么用 Pairwise

### 现有 checker 的局限

```
现有 risk_checker：
  输入：chapter_artifact
  输出：pass / revise / human_review（二元或三元）
  问题：只能判断"是否违规"，不能判断"哪个更好"
```

### Pairwise 的优势

```
Pairwise 评估：
  输入：草案 A vs 草案 B（同一章节的两个版本）
  输出：A 更好 / B 更好 / 相当（+ 理由）
  优势：
  - 可以捕捉"好但不违规"的质量差异
  - 与人工判断的一致性更高（参考 EvolvR Kendall's τ = 0.55）
  - 可以从人工评审数据中学习
```

---

## 2. 数据格式

### 2.1 Pairwise 对比对

```json
{
  "pair_id": "uuid",
  "branch_id": "...",
  "chapter_index": 42,
  "draft_a": {
    "source": "harness_iteration_1",
    "text": "...",
    "risk_verdict": "pass",
    "checker_scores": {...}
  },
  "draft_b": {
    "source": "harness_iteration_2",
    "text": "...",
    "risk_verdict": "pass",
    "checker_scores": {...}
  },
  "preference": "A",
  "preference_reason": "A 的角色动机更清晰，情节推进更自然",
  "annotator": "human | llm_judge",
  "annotation_confidence": 0.85,
  "quality_dimensions": {
    "character_consistency": {"winner": "A", "score_diff": 0.3},
    "plot_coherence": {"winner": "A", "score_diff": 0.2},
    "style_fidelity": {"winner": "tie", "score_diff": 0.0},
    "narrative_tension": {"winner": "B", "score_diff": 0.1}
  }
}
```

### 2.2 Chapter Quality Score（输出给 0509）

```json
{
  "chapter_index": 42,
  "branch_id": "...",
  "quality_score": 0.78,
  "confidence": 0.82,
  "dimensions": {
    "character_consistency": 0.85,
    "plot_coherence": 0.80,
    "style_fidelity": 0.72,
    "narrative_tension": 0.65
  },
  "loom_version": "1.0",
  "evaluation_method": "llm_judge_pairwise"
}
```

---

## 3. LLM-as-judge Prompt 设计

### 3.1 评估维度

```
维度 1：角色一致性（character_consistency）
  - 角色行为是否符合其已建立的性格和动机？
  - 角色状态是否与前文一致？

维度 2：情节连贯性（plot_coherence）
  - 情节推进是否自然？
  - 是否有逻辑跳跃或无法解释的转折？

维度 3：风格忠实度（style_fidelity）
  - 是否保持了原著的叙事风格？
  - 节奏、句式、信息密度是否一致？

维度 4：叙事张力（narrative_tension）
  - 是否有足够的冲突和悬念？
  - 情节是否过于平淡或重复？
```

### 3.2 Prompt 模板

```python
PAIRWISE_JUDGE_PROMPT = """
你是一位专业的小说编辑，正在评估同一章节的两个仿写草案。

【原章节信息】
章节目标：{chapter_goal}
关键约束：{key_constraints}

【草案 A】
{draft_a_text}

【草案 B】
{draft_b_text}

请从以下四个维度评估，哪个草案更好：
1. 角色一致性：角色行为是否符合其性格和动机
2. 情节连贯性：情节推进是否自然，有无逻辑跳跃
3. 风格忠实度：是否保持原著风格
4. 叙事张力：是否有足够的冲突和悬念

输出格式（JSON）：
{{
  "overall_preference": "A" | "B" | "tie",
  "overall_reason": "...",
  "dimensions": {{
    "character_consistency": {{"winner": "A"|"B"|"tie", "reason": "..."}},
    "plot_coherence": {{"winner": "A"|"B"|"tie", "reason": "..."}},
    "style_fidelity": {{"winner": "A"|"B"|"tie", "reason": "..."}},
    "narrative_tension": {{"winner": "A"|"B"|"tie", "reason": "..."}}
  }}
}}
"""
```

---

## 4. 接入 Harness 决策

### 当前 Harness 决策逻辑

```python
# 现有（伪代码）
if risk_verdict == "pass":
    return draft
elif risk_verdict == "revise":
    return revise(draft, failure_type)
```

### 接入 Pairwise 后的 Harness 决策逻辑

```python
# Loom 增强后（伪代码）
if risk_verdict == "pass":
    if loom_enabled and has_multiple_drafts:
        # 用 pairwise 评估选出更好的草案
        quality_scores = [pairwise_eval(draft_a, draft_b) for ...]
        best_draft = select_best(quality_scores)
        record_quality_score(best_draft.chapter_quality_score)  # 输出给 0509
        return best_draft
    else:
        return draft
elif risk_verdict == "revise":
    return revise(draft, failure_type)
```

---

## 5. 接入 0509 Retirement Gate

### 当前 0509 retirement gate 的问题

0509 的 `session_legacy_retirement_readiness` 判断条件是：
- primary 消费者迁移完成
- 无回归

但没有"生成质量达标"这个条件。

### Loom 补充的质量门控

```python
# 在 0509 retirement gate 前增加 Loom quality check

def can_retire_legacy_field(session_id: str, field_name: str) -> bool:
    # 0509 原有条件
    if not migration_complete(session_id, field_name):
        return False
    if has_regression(session_id):
        return False

    # Loom 新增条件（如果 Loom reward 层已启用）
    if loom_reward_enabled:
        recent_quality = get_recent_chapter_quality_scores(session_id, last_n=10)
        if avg(recent_quality) < QUALITY_THRESHOLD:  # 默认 0.7
            return False

    return True
```

---

## 6. 验收标准

- [ ] LLM-as-judge 与人工判断的一致性 Kendall's τ ≥ 0.4（目标 ≥ 0.5）
- [ ] `chapter_quality_score` 正确输出到 0509 `session_primary_verdicts` 的输入信号
- [ ] Pairwise 评估不增加超过 2 秒的延迟（异步运行）
- [ ] feature flag 关闭时，现有 harness 决策逻辑完全不受影响

---

返回 [Reward 层入口](./README.md) | [Reward Model 路线图](./reward-model-roadmap.md)
