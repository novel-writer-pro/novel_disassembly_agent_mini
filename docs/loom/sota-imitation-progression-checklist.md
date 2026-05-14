# SOTA 仿写能力推进 Checklist

> 这份清单不是单纯的 Loom checklist。
>
> 它回答的是：**我们离 SOTA 级仿写能力还有多远，当前每一项建设是否真的推进了主链路。**

---

## 1. 主目标

主链路目标始终是：

> **把 novel-analyzer 的仿写能力推进到更接近 SOTA 的长期稳定水准。**

因此所有 Loom / control-plane / evaluation 建设，都必须回答同一个问题：

- 是否让仿写更像原作？
- 是否让多章节连续仿写更稳？
- 是否降低 `character_ooc` / world rule 漂移 / 情节退化？
- 是否减少人工盯跑负担？

---

## 2. 这份清单怎么用

### 使用原则

1. **先看主链路效果，再看局部信号是否漂亮**
2. **先让 LLM 自动处理，再决定是否转人工**
3. **人工只是复杂 case 的兜底，不是默认主流程**
4. **每一项推进都要能回到卫图样例上复现**

### Changelist 记录原则

每一轮推进都应该在 `CHANGELOG.md` 和 handoff 中带一个可追踪 marker，例如：

- `CL-loom-whole-book-bridge-01`
- `CL-loom-weitut-validate-01`

---

## 3. 仿写主链推进清单

## A. 基础链路可跑

- [ ] PostgreSQL / LLM provider / migration 全部可用
- [ ] 卫图样例小说可稳定导入
- [ ] writer-imitate 主链路能稳定产出 JSON / Markdown / operator surface
- [ ] whole-book imitation dry-run / sandbox execute 可稳定导出
- [ ] Loom feature flags 可切换：`disabled / shadow / ab / enabled`

**验收标准**：
- 至少一条卫图样例 branch 从 ingest → analysis → writer-imitate → whole-book export 全链路成功

---

## B. 像原作（Style Fidelity）

- [ ] 基础仿写能保留原章结构骨架
- [ ] 风格偏移可量化（`style_drift_score`）
- [ ] style 信号进入 chapter / session / whole-book 报告
- [ ] 与人工风格评分能建立相关性基线

**关键指标**：
- `style_drift_score`
- 人工风格评分
- style signal vs manual score 相关性

---

## C. 角色一致性（Character Consistency）

- [ ] `character_ooc` 在卫图样例上可稳定检测
- [ ] 角色一致性信号进入 chapter / session / whole-book 报告
- [ ] 多章节 carry-over 后角色设定不明显漂移
- [ ] 角色认知基（Persona）在复杂 case 上开始接管规则化 OOC 检查

**关键指标**：
- `character_ooc` 触发率
- `character_consistency_signal`
- 人工角色评分

---

## D. 长程连续性（Long-Horizon Continuity）

- [ ] carry_over_state 不再线性退化
- [ ] unresolved threads / rule state / relationship state 可跨章稳定传递
- [ ] whole-book sandbox/export 报告能显式暴露 Loom 摘要
- [ ] LLM 生成后的人类介入仍能 resume 回原链条

**关键指标**：
- `carry_over_gap_count`
- `long_book_consistency_diagnostics`
- `session_loom_gate_summary`

---

## E. 情节张力与节奏（Tension / Rhythm）

- [ ] `plot_similarity_score` 可识别重复章节走势
- [ ] `conflict_density` 可识别平淡区段
- [ ] `surprise_index` 可识别新信息匮乏
- [ ] `hook_density` / 节奏信号进入 whole-book 聚合
- [ ] operator 能看到 tension gate，不必回到底层手工拼装

**关键指标**：
- `average_tension_score`
- `tension_alert_chapters`
- `average_hook_density`

---

## F. 对话质量（Dialogue Quality）

- [ ] 对话质量信号已产出
- [ ] 对话冲突密度/效率进入 Loom 报告
- [ ] 与人工对话评分建立第一轮校准

---

## G. 评估闭环（Evaluation Loop）

- [x] `loom-collect-pairs` 可从 writer-imitate 产物提取 pairwise
- [x] `loom-collect-pairs-from-manual` 可从人工工作区提取 pairwise
- [x] `loom-pairs-stats` 可追踪数据积累进度
- [x] `loom-ab-compare` 可比较 baseline vs loom
- [x] `evaluation_method=llm_judge` 样本开始出现并积累
- [ ] 500+ pairs 积累目标进入持续跟踪

---

## G2. Reference-based 评估（主评估方式）

- [x] `ReferenceEvalService` 以原文为参照评估仿写还原度
- [x] `loom-reference-eval` CLI 可一键评估单章 fidelity
- [x] `_loom_reference_fidelity` 自动集成到 `writer-imitate --use-llm` 产物
- [x] 6 维度评估：structure/character/style/continuity/tension/information_density
- [x] 卫图 ch2 验证：enhanced fidelity=0.78 vs baseline=0.18（4.3x）
- [x] 卫图 ch10 验证：enhanced fidelity=0.35 vs baseline=0.15（2.3x）
- [ ] 多章节统计验证（5-10 次运行取平均）
- [ ] reference fidelity 进入 whole-book 聚合（average_reference_fidelity）
- [ ] reference fidelity 进入 gate summary 作为 ship/hold 判据

**关键指标**：
- `overall_fidelity`（0-1，越高越像原文）
- `structure_fidelity`（场景节拍还原）
- `character_fidelity`（角色行为还原）
- `continuity_fidelity`（连续性还原）

**验收标准**：
- enhanced `overall_fidelity` 在 ch≥10 时稳定高于 baseline（≥1.5x）
- 6 维度中至少 4 个 enhanced 胜出

**注意**：
当前很多自动链路仍可能走 heuristic fallback，不能把“能力已实现”误当成“效果已被真实证明”。

---

## H. LLM-first / Human-fallback / Resume-able

- [ ] 默认优先使用 LLM judge / 自动修复 / 自动分类
- [ ] 复杂 case 才转人工 mailbox / manual_eval
- [ ] 人工介入后能回到 `resume / recovery / checkpoint / transition` 链
- [ ] 人工兜底结果可再回收为 pairwise / manual eval 数据

**验收标准**：
- 至少一次卫图样例验证流程从自动阶段进入人工，再成功恢复回原链条

---

## 4. 卫图样例的真实验证清单

## P0：必须完成

- [ ] 选定卫图样例 branch / run / novel source
- [ ] 产出 baseline 仿写结果
- [ ] 产出 Loom 增强仿写结果
- [ ] 跑 `loom-ab-compare`
- [ ] 记录 `character_ooc` 变化
- [ ] 记录 LLM-first 自动评估结果
- [ ] 对复杂 case 建立人工介入 mailbox
- [ ] 完成 resume / recovery 演示

## P1：建议完成

- [ ] 抽取 pairwise 数据进入 JSONL
- [ ] 汇总 `loom-pairs-stats`
- [ ] 人工复核少量章节（角色 / 风格 / 对话 / 连续性）
- [ ] 记录哪些问题 LLM 能独立处理，哪些必须人工兜底

## P2：后续进入稳定化

- [ ] 累积 500+ pairs
- [ ] 开始 reward model 训练准备
- [ ] 引入真实 executor / live writeback 验证

---

## 5. 判断“建设是否真的有效”的门槛

只有同时满足下面几项，才能说某轮 Loom 建设“有效”：

- [ ] 在卫图样例上完成 baseline vs loom 对比
- [ ] `character_ooc` 下降趋势可见
- [ ] 质量/张力/风格/对话信号与人工判断不明显冲突
- [ ] 人工介入次数没有随着 Loom 打开而失控增加
- [ ] mailbox 介入后可以 resume，不打断主链路
- [ ] 文档/手册/交接记录齐全，可复现

如果只满足“能跑”而不满足上面这些，结论只能是：

> **能力已建成，效果待证实。**

---

## 6. 本清单关联文档

- [卫图样例真实效果验证工作流](./weitu-real-effect-validation.md)
- [Loom 开发交接文档](./handoff.md)
- [Loom 路线图](./roadmap.md)
- [CLI 操作手册](../cli-operations-manual.md)
- [人工评估工作区模板](../../runs/manual_eval/_template/README.md)
