# 评估数据收集规范 / Eval Data Collection

---

## 1. 现有数据来源盘点

| 数据来源 | DB 表 | 可提取内容 | 质量 |
|---------|------|----------|------|
| 人工评审记录 | `manual_eval_record`（文件） | 章节评分、问题描述、改进建议 | 高（人工标注） |
| 读者反馈 | `reader_feedback_comments` | 情感倾向、具体评论 | 中（半结构化） |
| Harness 迭代产物 | `chapter_artifacts`（多版本） | 同章节多个草案版本 | 高（天然 pairwise） |
| Risk checker 结果 | `gate_checker_results` | 各 checker 的 pass/fail | 中（规则化，非质量判断） |
| 人工 review 结论 | `cluster_review_records` | 问题簇的处理结论 | 高（人工决策） |

---

## 2. Pairwise 数据提取规范

### 2.1 从 Harness 迭代提取（最高质量）

Harness 在修复循环中会产生同一章节的多个草案版本，这是天然的 pairwise 数据：

```python
# 提取规则：
# - 同一 branch_id + chapter_index 的多个 chapter_artifacts
# - artifact_type = 'chapter_imitation_draft'
# - 取最终被采用的版本（final_verdict = 'pass'）作为"更好"的一方
# - 取被拒绝的版本（final_verdict = 'revise'）作为"更差"的一方

def extract_harness_pairs(branch_id: str, chapter_index: int) -> list[PairwisePair]:
    drafts = get_chapter_drafts(branch_id, chapter_index)
    pairs = []
    for i, draft_a in enumerate(drafts):
        for draft_b in drafts[i+1:]:
            if draft_a.final_verdict != draft_b.final_verdict:
                winner = draft_a if draft_a.final_verdict == 'pass' else draft_b
                loser = draft_b if winner == draft_a else draft_a
                pairs.append(PairwisePair(
                    preferred=winner,
                    rejected=loser,
                    annotator='harness_verdict',
                    confidence=0.7  # 中等置信度，因为 harness 判断不等于质量判断
                ))
    return pairs
```

### 2.2 从人工评审记录提取

```python
# manual_eval_record 格式（现有）：
# {
#   "chapter_index": 42,
#   "overall_score": 7,  # 1-10
#   "issues": ["角色动机不清晰", "节奏过快"],
#   "strengths": ["对话自然", "伏笔处理好"],
#   "recommendation": "revise | accept | reject"
# }

# 提取规则：
# - overall_score >= 7 的章节作为"好"样本
# - overall_score <= 4 的章节作为"差"样本
# - 同一章节有多个版本时，按 overall_score 排序构成 pairwise 对
```

### 2.3 从读者反馈提取

```python
# reader_feedback_comments 格式（现有）：
# {
#   "chapter_index": 42,
#   "comment_text": "这章写得很好，角色很真实",
#   "sentiment": "positive | negative | mixed"
# }

# 提取规则：
# - sentiment = 'positive' 的章节作为正向信号
# - sentiment = 'negative' 的章节作为负向信号
# - 置信度较低（0.5），需要与其他信号结合使用
```

---

## 3. 数据质量过滤

```python
# 过滤规则：
# 1. 两个草案的 risk_verdict 都是 'pass'（排除明显违规的草案）
# 2. 草案长度差异 < 30%（避免长度偏差影响判断）
# 3. 同一章节的两个草案来自同一 branch（确保上下文一致）
# 4. annotator = 'human' 的数据优先级最高
# 5. LLM-as-judge 的数据需要 confidence >= 0.7 才纳入训练集
```

---

## 4. 数据积累目标

| 阶段 | 目标数量 | 预计时间 | 用途 |
|------|---------|---------|------|
| 阶段 1 启动 | 50+ pairs | 立即（从现有数据提取） | LLM-as-judge few-shot |
| 阶段 2 准备 | 500+ pairs | 3-6 个月 | Fine-tuning reward model |
| 阶段 3 准备 | 2000+ pairs（多维度标注） | 6-12 个月 | 多维度 reward model |

---

## 5. 与 0509 Consumer Migration Telemetry 的对接

0509 的 **Consumer Migration Telemetry**（🔴 未实现）需要知道"哪些消费者已迁到 primary"。

Loom 的评估数据收集可以同时记录"哪个评估路径被使用"：

```json
{
  "pair_id": "...",
  "evaluation_path": "loom_pairwise | legacy_checker | human",
  "consumer": "harness | whole_book | manual_review",
  "migrated_to_primary": true
}
```

这个字段可以直接作为 0509 Consumer Migration Telemetry 的数据来源。

---

返回 [Reward 层入口](./README.md) | [Pairwise 评估设计](./pairwise-eval-design.md)
