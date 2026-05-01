# 风险审查主链：语义增强架构说明

## 1. 目的

这份文档回答两个问题：

1. 为什么当前 `risk_audit_service` 主链没有直接把 embedding / reranker / LLM skills 塞进每个 checker
2. 后续如果要把质量继续做上去，语义增强应该加在哪一层

---

## 2. 当前主链为什么偏结构化、可解释

当前风险审查主链优先目标不是“最聪明”，而是：

- 可解释
- 可回归
- 可审计
- 成本可控
- advisory-only

因此当前主链故意拆成三层：

### Layer A：语义抽取层
负责把原文/章节分析结果提纯成结构化中间产物，例如：

- `unsupported_inferences`
- `ambiguous_points`
- `state_transition_notes`
- `evidence_backed_resolutions`
- `unresolved_threads`
- `state_summary.*`
- graph / fact / retrieval 派生产物

这层已经大量使用：

- LLM
- skills / staged prompts
- 图谱与事实物化

### Layer B：风险判断层
即当前 `risk_audit_service`。

职责是：

- 消费结构化 signals
- 产出可解释风险项
- 保持结果稳定与可测试

### Layer C：聚合交付层
即：

- `ChapterRiskCard`
- `review_candidate_clusters`
- `audit_conclusion`
- review workflow

---

## 3. 为什么不在每个 checker 里直接调用 embedding / skills

如果把 embedding / reranker / LLM 直接塞进 checker 主判断，会立刻带来：

1. **结果漂移变大**
   - 同一章多次跑结论可能不稳定
2. **回归测试变难**
   - 很难维持稳定、可预测的断言
3. **成本和延迟上升**
   - 每章 * 多 checker * 二次模型调用，代价会快速放大
4. **审计性下降**
   - 很难清晰说明“为什么判这个风险”

所以当前不是“永远不用语义能力”，而是：

> 先把主链做成“结构化 signals -> 可解释风险判断”的稳定版本。

---

## 4. 当前实现的真实边界

当前 checker 不是直接对原文做最原始的关键词扫描，而是：

> 对上游已经语义提纯过的 artifact / state / thread / rule signals 做规则化收口。

因此当前粗糙点主要在于：

1. signal 颗粒度还不够细
2. 缺少跨章语义归并层
3. 缺少“候选对齐 / 候选去重 / 弱语义归一”的中间层

---

## 5. 后续正确的语义增强位置

不建议把主链直接改成“checker 内反复调用大模型”。

更合理的做法是新增一层：

## Semantic Signal Builder

放在 Layer A 与 Layer B 之间。

职责：

- 做跨章语义归一
- 做候选 linking / matching
- 做别名合并、规则归一、线程生命周期对齐
- 给 checker 提供更稳定的结构化 signal

### 可引入的能力

- embedding 相似检索
- reranker
- 小模型 canonicalization
- schema-guided LLM extraction

### 当前最小落地现状

当前仓库已经开始把这层从“文档概念”推进到“代码骨架”：

- `novel_analyzer/services/risk_semantic_signal_service.py`

当前该模块先承担：

- common artifact signals 抽取
- character signals 抽取
- rule signals 抽取
- relationship signals 抽取
- foreshadow/payoff signals 抽取
- setting scope signals 抽取
- thread closure signals 抽取
- plot signals 抽取
- timeline signals 抽取
- power signals 抽取

也就是说，checker 逻辑开始从“单文件内直接拼装所有 signals”过渡到：

> signal builder 抽取 -> checker 判定 -> aggregator 聚合

当前已经接入这层的主链 checker 包括：

- `character_ooc`
- `world_rule_consistency`
- `relationship_consistency`
- `foreshadow_payoff_consistency`
- `setting_scope_consistency`
- `thread_closure_consistency`
- `plot_logic_consistency`
- `timeline_consistency`
- `power_scaling_consistency`

这还不是最终的 embedding / reranker / canonicalization 版本，但已经把后续可演进位置稳定下来了。

---

## 6. 建议新增的 signal record

后续可逐步补：

### 人物/关系
- `CharacterSignalRecord`
- `RelationshipSignalRecord`

### 伏笔/线程
- `ForeshadowLifecycleSignal`
- `ThreadLifecycleSignal`

### 规则/设定边界
- `RuleScopeSignalRecord`
- `AuthorityBoundarySignal`
- `ResourceConstraintSignal`

### 因果/时间/战力
- `EventCausalitySignal`
- `TimelineAnchorSignal`
- `PowerStateSignalRecord`

---

## 7. embedding 更适合做什么

embedding 最适合：

1. **跨章表达归并**
   - 同义表述、弱改写、隐晦说法
2. **候选 linking**
   - 前文伏笔与当前兑现是否其实指向同一条线
3. **规则/边界 canonicalization**
   - “不得擅入 / 无资格进入 / 需持令牌”是否属于同一约束
4. **关系语义归一**
   - “和解 / 停战 / 冰释前嫌”是否属于关系缓和簇

不建议让 embedding 直接输出“最终风险成立”。

---

## 8. skills / LLM 更适合做什么

skills / LLM 更适合：

1. 上游章节分析与结构化抽取
2. 疑难候选的二次复核
3. 人工 review 前的 evidence pack 增强
4. 低召回、高歧义 case 的补充解释

不建议：

- 每个 checker 全量、同步、直接依赖 LLM 二判

---

## 9. 推荐演进顺序

### Phase A：主链收口
先把 checker roster 做齐、做稳。

### Phase B：语义信号层增强
补充 semantic signal builder，不破坏当前 checker contract。

### Phase C：二次复核能力
仅对中间置信度 / 高价值候选启用 secondary review。

### Phase D：精细化排序与聚合
对 review candidate / cluster 做更强的 evidence ranking。

---

## 10. 最终推荐方案（生产向）

如果目标是 **稳定性 + 准确性 + 可持续演进**，不建议走纯关键词，也不建议走“所有 checker 全量直连 LLM”。

推荐最终采用：

## Hybrid Semantic Risk Architecture

### A. ONNX embedding + PostgreSQL / pgvector

用于：

- 跨章语义归并
- 规则/关系/伏笔/冲突表达对齐
- 候选 linking
- signal canonicalization

建议：

- 本地 ONNX embedding 模型做稳定向量化
- PostgreSQL / pgvector 保存：
  - signal text
  - canonical label
  - source chapter
  - signal type
  - vector

这层适合作为：

- `semantic signal store`
- `cross-chapter candidate retrieval`

### B. 规则化 checker 判定层

继续保留当前 checker 的职责：

- 可解释
- 可回归
- 可审计

embedding 层负责“找到更像同一件事的表达”，  
checker 层负责“判定这是否构成风险候选”。

### C. 目标式 LLM adjudication

LLM 不建议全量跑在每个 checker 上，建议只用于：

- 中间置信度候选
- 高价值章节
- 高冲突簇
- 人工 review 前 evidence pack 增强

也就是：

- embedding 负责召回/归并
- checker 负责稳定判断
- LLM 负责疑难复核

---

## 11. 为什么这是更好的方案

相对纯 LLM：

- 更稳定
- 成本更低
- 更可测试
- 更适合批量章节跑全书

相对纯 embedding：

- 不会把相似表达误当成最终风险
- 仍然保留规则与证据链约束

相对当前纯结构化启发式：

- 更强的跨章语义对齐能力
- 更适合处理隐晦改写、弱同义表达、设定别称

---

## 12. 一句话结论

> 最终生产方案，优先推荐 **ONNX embedding + PostgreSQL/pgvector 语义信号层 + 规则化 checker + 目标式 LLM 复核**。  
> 这比“纯关键词”、也比“checker 全量直连 LLM”更稳、更便宜、更适合长期维护。

---

## 13. 一句话总结

> 当前主链没有把 embedding / skills 直接塞进每个 checker，不是因为这些能力没价值，而是因为当前阶段优先保证稳定、可解释、可回归；后续真正的升级方向，应当是增加“语义信号层”，而不是把 checker 直接改成黑箱式 LLM 判定器。
