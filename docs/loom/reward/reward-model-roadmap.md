# Reward Model 演进路线 / Reward Model Roadmap

---

## 演进路线总览

```
阶段 1（当前可做）
LLM-as-judge pairwise
  ↓ 积累 500+ pairwise 对比数据
阶段 2（3-6个月后）
Fine-tuned reward model（Qwen-7B 或类似小模型）
  ↓ 积累多维度反馈数据
阶段 3（6-12个月后）
多维度 reward model（风格/张力/一致性分离）
```

---

## 阶段 1：LLM-as-judge（立即可做）

**方法**：用现有 LLM（gpt-5.4-mini）做 pairwise 评估，不需要训练。

**数据来源**：
- 现有 `manual_eval_record`（人工评审记录）
- 现有 `reader_feedback_comments`（读者反馈）
- Harness 迭代产生的多个草案版本

**输出**：
- `chapter_quality_score`（0-1 浮点数）
- `pairwise_preference`（A/B/tie）
- `quality_dimensions`（四个维度分项）

**局限**：
- 依赖 LLM 调用，有成本和延迟
- 结果可能有漂移（同一对比多次运行结果不完全一致）
- 无法离线运行

---

## 阶段 2：Fine-tuned Reward Model

**触发条件**：积累 500+ 高质量 pairwise 对比数据（人工标注 + LLM-as-judge 过滤）。

**模型选择**：
- 优先：Qwen-7B-Instruct（中文能力强，可本地部署）
- 备选：GLM-4-9B（中文 SOTA，但更大）
- 不推荐：GPT 系列（无法本地部署，成本高）

**训练方法**：
```
数据格式：(chapter_context, draft_a, draft_b, preference_label)
训练目标：Bradley-Terry 模型（pairwise preference learning）
评估指标：Kendall's τ（与人工判断的一致性）
目标：τ ≥ 0.5（参考 EvolvR 的 0.55）
```

**优势**：
- 本地运行，无 API 成本
- 结果稳定，可回归测试
- 可以针对中文网文风格专门优化

---

## 阶段 3：多维度 Reward Model

**触发条件**：阶段 2 模型稳定运行 3 个月，积累足够的多维度标注数据。

**方向**：
- 把四个维度（角色一致性/情节连贯性/风格忠实度/叙事张力）分别训练独立的 reward head
- 支持按需组合：仿写任务侧重风格忠实度，续写任务侧重情节连贯性

---

## 与现有 risk_checker 的关系

```
现有 risk_checker（保持不变）：
  判断"是否违规"（pass/revise/human_review）
  规则化，可解释，可回归

Loom reward model（新增，补充）：
  判断"哪个更好"（A/B/tie + 分项分数）
  学习型，可进化，可从反馈中改进

两者串联：
  risk_checker 先过滤违规 → reward model 再选最优
  不互相替代，各司其职
```

---

返回 [Reward 层入口](./README.md) | [评估数据收集](./eval-data-collection.md)
