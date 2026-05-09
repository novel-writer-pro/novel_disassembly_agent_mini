# Reward 层入口 / 学习型评估

> Reward 层解决的核心问题：**评估维度固化，无法从人工反馈中学习**。
> 现有 `risk_checker` 只能判断"是否违规"，不能判断"是否优秀"，也不能自我进化。

---

## 与 0509 控制层的关系

```
0509 session_primary_verdicts（session 级，不变）
        ↑
        │ 聚合 chapter_quality_score（新信号）
        │
Loom reward 层（chapter 级评估，新增）
        │ 从 pairwise 对比中学习
        ↓
manual_eval_record + reader_feedback_comments（现有数据来源）
```

Reward 层是 0509 verdict 的**输入信号来源**，不替换 0509 的 session 级判断。

同时，Reward 层为 0509 的 **Automated Retirement Gate**（🔴 未实现）提供自动质量门控能力。

---

## 三个演进阶段

| 阶段 | 方法 | 数据来源 | 输出 |
|------|------|---------|------|
| **阶段 1** | LLM-as-judge pairwise | 现有 `manual_eval_record` | `chapter_quality_score` |
| **阶段 2** | 专用 reward model（小模型） | 积累的 pairwise 对比数据 | 更稳定的 `quality_score` |
| **阶段 3** | 多维度 reward（风格/张力/一致性） | 阶段 2 数据 + 读者反馈 | 细粒度质量信号 |

---

## 文档清单

| 文档 | 说明 |
|------|------|
| [pairwise-eval-design.md](./pairwise-eval-design.md) | Pairwise 评估框架完整设计 |
| [reward-model-roadmap.md](./reward-model-roadmap.md) | LLM-as-judge → reward model 演进路线 |
| [eval-data-collection.md](./eval-data-collection.md) | 评估数据收集规范 |

---

返回 [Loom 入口](../README.md)
