# Loom 架构 / 织机架构

> **Loom** — 织机。小说由线索（threads）、角色（characters）、世界规则（rules）织成。
> Loom 是在现有 novel-analyzer 基础上，把这些线索编织得更连贯、更可控、更能自我进化的下一代架构层。

---

## 一句话定位

> Loom 不是重写现有系统，而是在已有 GraphRAG 基础设施（`pg_trgm` + `pgvector` + `GraphNode/GraphEdge`）
> 与 0509 仿写控制层（`session_state → operator_surface → action_queue → execution_state`）之上，
> 填补三个关键缺口：**记忆代谢**、**评估自进化**、**叙事张力调节**。

---

## 与现有系统的关系

```
novel-analyzer（现有，保持不变）
├── 内容理解层        chapter_intake → fact_extractor → evidence_binder → ...
├── 风险与审查层      risk_semantic_signal → checker → review_workflow
├── 生成与仿写层      ← Loom memory 层增强 carry_over_state
│   └── 0509 控制层  session_state / operator_surface / action_queue  ← Loom 直接对接
├── 治理与评估层      ← Loom reward 层补充 pairwise 评估
└── 运营与接入层      保持不变

Loom（新增层，叠加在上方）
├── memory/          分层记忆 + 冲突代谢（对接 0509 session_state，填补 live writeback 缺口）
├── reward/          学习型评估（补充规则化 checker，填补 automated gate 缺口）
└── tension/         叙事张力自动调节（补充人工 steering，填补 full control console 缺口）
```

**原则**：
- 现有链路继续工作，Loom 通过 feature flag 渐进启用
- 复用现有 DB 表（`GraphNode`、`GraphEdge`、`FactRecord`、`RiskSemanticSignalRecord`），加字段而不是建新表
- 0509 控制层的 🔴 未实现项，是 Loom 各模块的优先填补目标
- 每个 Phase 都有可回滚路径，不影响生产稳定性

---

## 三大升级方向

### A. 分层记忆 + 冲突代谢（Memory）

**解决的问题**：
- 长书（100章+）仿写时，`carry_over_state` 线性追加，冲突累积无法消解，越写越乱
- 0509 控制层的 `session_state` 已有完整 preview 链，但缺 **Live Checkpoint Writeback**（🔴）

**核心思路**：
把现有 `GraphNode/GraphEdge/FactRecord/WindowArtifact` 映射为三层记忆结构，
加入冲突检测和代谢机制，并把 0509 的 `session_state` 作为 Working Memory 层的运行时入口。

**SOTA 参考**：EvoSpark（ACL 2026）Stratified Narrative Memory、Memory as Metabolism（2026）

→ [memory/README.md](./memory/README.md)

---

### B. 学习型评估 / Pairwise Reward（Reward）

**解决的问题**：
- 现有 `risk_checker` 规则固定，无法从人工评审数据中学习
- 0509 控制层缺 **Consumer Migration Telemetry** 和 **Automated Retirement Gate**（🔴）

**核心思路**：
从现有 `manual_eval_record` 和 `reader_feedback_comments` 提取 pairwise 对比数据，
构建 LLM-as-judge 评估层，逐步演进到 fine-tuned reward model，
同时为 0509 的 retirement gate 提供自动质量门控能力。

**SOTA 参考**：EvolvR（SOTA on StoryER/HANNA/OpenMEVA，2025-2026）

→ [reward/README.md](./reward/README.md)

---

### C. 叙事张力自动调节（Tension）

**解决的问题**：
- 情节平淡/重复无自动检测，完全依赖人工 steering
- 0509 控制层缺 **Full Control Console**（🔴），张力信号是控制台的关键输入

**核心思路**：
直接用现有 `ChunkEmbedding`（pgvector）计算 `plot_similarity_score`，
从现有 `GraphEdge` 计算 `conflict_density`，不需要新的 LLM 调用，
并把张力信号接入 0509 的 operator surface，作为控制台的实时质量指标。

**SOTA 参考**：Long Story Generation via KG + Literary Theory（2025）obstacle framework

→ [tension/README.md](./tension/README.md)

---

## 快速导航

| 文档 | 说明 |
|------|------|
| [overview.md](./overview.md) | 完整架构图、SOTA 对比表、设计原则、风险分析 |
| [memory/README.md](./memory/README.md) | 记忆层入口 |
| [memory/layered-memory-design.md](./memory/layered-memory-design.md) | 三层记忆设计 + DB 扩展方案 |
| [memory/conflict-metabolism.md](./memory/conflict-metabolism.md) | 冲突代谢机制 |
| [memory/carry-over-migration.md](./memory/carry-over-migration.md) | 从现有 carry_over_state 迁移方案 |
| [reward/README.md](./reward/README.md) | 评估层入口 |
| [reward/pairwise-eval-design.md](./reward/pairwise-eval-design.md) | Pairwise 评估框架设计 |
| [reward/reward-model-roadmap.md](./reward/reward-model-roadmap.md) | LLM-as-judge → reward model 演进路线 |
| [reward/eval-data-collection.md](./reward/eval-data-collection.md) | 评估数据收集规范 |
| [tension/README.md](./tension/README.md) | 张力层入口 |
| [tension/tension-metrics.md](./tension/tension-metrics.md) | 三个张力指标计算方法 |
| [tension/obstacle-injection.md](./tension/obstacle-injection.md) | Obstacle 自动注入机制 |
| [tension/trope-integration.md](./tension/trope-integration.md) | 与现有 trope/worldview RAG 库集成 |
| [roadmap.md](./roadmap.md) | Phase 1/2/3 开发路线图 + 验收标准 |

---

## 如何判断 Loom 比现有架构更好

每个 Phase 都有**可量化的对比实验**，且每个实验都有明确的回滚路径：

| Phase | 对比方法 | 验收指标 | 回滚方式 |
|-------|---------|---------|---------|
| Phase 1（记忆） | 同一本书连续 20 章，旧链路 vs Loom 链路 | `character_ooc` 触发率下降 ≥ 20%，人工一致性评分提升 | feature flag 关闭，回到原 carry_over_state |
| Phase 2（张力） | 批量仿写 10 章，有/无张力调节对比 | `plot_similarity_score` 方差扩大，人工"情节吸引力"评分提升 | 关闭 preflight 张力检查 |
| Phase 3（评估） | pairwise 评估 vs 现有 checker，与人工判断对比 | Kendall's τ ≥ 0.5（参考 EvolvR 的 0.55） | 回到纯规则 checker |

---

## 0509 控制层与 Loom 的对接关系

| 0509 状态 | 对应 Loom 模块 | Loom 填补内容 |
|-----------|--------------|-------------|
| ✅ Session State / Operator Surface | memory/layered-memory-design | 作为 Working Memory 层的运行时入口 |
| ✅ Action Queue / Execution State | memory/carry-over-migration | 对接 carry_over_state 迁移路径 |
| ✅ Primary/Legacy 双层治理 | reward/eval-data-collection | 评估数据按 primary/legacy 分层收集 |
| 🔴 Live Checkpoint Writeback | memory/conflict-metabolism | 冲突消解后的状态回写机制 |
| 🟡 Consumer Migration Telemetry | reward/eval-data-collection | writer control surfaces、execution resume、live/runtime readiness 以及 external runtime simulation bridge 已输出最小迁移遥测；更细粒度真实 runtime 观测仍待后续扩展 |
| 🟡 Automated Retirement Gate | reward/pairwise-eval-design | writer retirement readiness/preview 已接入最小质量门控；完整 reward 驱动 gate 仍待后续扩展 |
| 🟡 Loom Signal Surface | tension/tension-metrics + reward/pairwise-eval-design | `writer-imitate-operator-surface` 已暴露 `session_loom_signals`，`session_primary_verdicts` 也已吸收 quality 聚合；retirement gate 仍待后续接入 |

---

返回 [文档中心](../README.md) | [架构专题](../architecture/README.md)
