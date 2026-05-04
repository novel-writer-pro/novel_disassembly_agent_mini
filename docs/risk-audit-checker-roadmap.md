# 统一风险审查体系：Checker 路线图

## 1. 当前 checker 全景

### 已正式落地

1. `character_ooc`
2. `world_rule_consistency`

### 已纳入并开始提质

3. `relationship_consistency`
4. `foreshadow_payoff_consistency`
5. `setting_scope_consistency`
6. `thread_closure_consistency`
7. `plot_logic_consistency`
8. `timeline_consistency`
9. `power_scaling_consistency`

---

## 2. 分阶段路线图

## Phase 1：框架成立（已完成）

目标：

- 建立统一 checker contract
- 建立统一 risk card
- 建立统一 export / report 输出

结果：

- `GateRiskItem`
- `CheckerResult`
- `ChapterRiskCard`
- review candidates / clusters / audit conclusion 已跑通
- Markdown / JSON 交付已跑通

## Phase 1.5：artifact-signal 提质（已推进）

### `world_rule_consistency`

已开始利用：

- `world_rule_signals`
- `unsupported_inferences`
- `ambiguous_points`
- `evidence_backed_resolutions`
- `unresolved_threads`

### `plot_logic_consistency`

已开始利用：

- `unsupported_inferences`
- `state_transition_notes`
- `evidence_backed_resolutions`
- `unresolved_threads`

### `timeline_consistency`

已开始利用：

- `timeline_signals`
- `unsupported_inferences`
- `ambiguous_points`
- `state_transition_notes`
- `unresolved_threads`

### `power_scaling_consistency`

已开始利用：

- `power_signals`
- `unsupported_inferences`
- `ambiguous_points`
- `state_transition_notes`
- `unresolved_threads`

### 当前 phase-2 第一轮已落地的细粒度候选

- `plot_logic_consistency`
  - `thread_state_conflict`
  - `motivation_to_action_gap`
- `timeline_consistency`
  - `sequence_conflict_candidate`
  - `recovery_window_insufficient`
- `power_scaling_consistency`
  - `upset_without_setup`
  - `cost_constraint_missing`

---

### `relationship_consistency`

已开始利用：

- `state_summary.stable_relations`
- `state_summary.evolved_relations`
- `unsupported_inferences`
- `state_transition_notes`
- `evidence_backed_resolutions`
- `unresolved_threads`

当前第一轮已落地的细粒度候选：

- `relationship_shift_without_bridge`
- `trust_state_conflict`
- `hostility_resolution_too_fast`

### `foreshadow_payoff_consistency`

已开始利用：

- `state_summary.new_foreshadowing`
- `state_summary.paid_off_foreshadowing`
- `unsupported_inferences`
- `evidence_backed_resolutions`
- `unresolved_threads`

当前第一轮已落地的细粒度候选：

- `payoff_without_setup`
- `resolved_thread_reopened_without_reason`
- `important_thread_long_unmentioned`

### `setting_scope_consistency`

已开始利用：

- `state_summary.observed_world_rules`
- `state_summary.constraining_world_rules`
- `unsupported_inferences`
- `state_transition_notes`
- `unresolved_threads`

当前第一轮已落地的细粒度候选：

- `constraint_scope_expansion`
- `resource_limit_missing`
- `authority_boundary_conflict`

### `thread_closure_consistency`

已开始利用：

- `state_summary.new_conflicts`
- `state_summary.escalated_conflicts`
- `unsupported_inferences`
- `evidence_backed_resolutions`
- `unresolved_threads`

当前第一轮已落地的细粒度候选：

- `thread_dropped_after_escalation`
- `closure_without_resolution_basis`
- `ending_stability_candidate`

## 3. 下一阶段优先级

## P1：增强现有 9 个 checker 的信号质量

### 目标

- 减少噪音
- 增加 cross-chapter 证据
- 提升候选可解释性

### 重点

1. `character_ooc`
   - 更稳定的角色画像基线
   - 更明确的动机/关系/能力漂移判据

2. `world_rule_consistency`
   - 更强的规则真源提取
   - 规则例外与规则破坏区分

3. `plot_logic_consistency`
   - 事件因果链建模
   - 已解决/未解决类表述与证据链闭合校验

4. `timeline_consistency`
   - 时间点、恢复时长、事件先后顺序建模

5. `power_scaling_consistency`
   - 战力基线
   - 能力跃迁阈值
   - 越阶/破格行为解释链

---

## P2：共享信号底座提质

建议建设：

- `CharacterSignalRecord`
- `RuleSignalRecord`
- `EventCausalitySignal`
- `TimelineSignalRecord`
- `PowerStateSignalRecord`

作用：

- 减少 checker 对最终摘要字段的依赖
- 让风险判定从“摘要提示”走向“结构化信号判断”

---

## P3：问题簇闭环

目标：

- 不只生成 cluster
- 还要支持 review lifecycle

建议后续字段：

- `cluster_status`
- `review_priority`
- `suggested_review_action`
- `review_owner`
- `review_notes`
- `resolved_by`
- `resolved_at`

### 当前已完成到哪

当前已经具备：

- `review_candidate_clusters`
- `cluster_title`
- `suggested_review_action`
- `review_priority`
- `cluster_status`

因此后续重点不再是“有没有问题簇”，而是：

1. 人工复核回写
2. resolved / reviewed 真正落库
3. review workflow 闭环

---

## 4. 长期扩展方向

在前 5 个 checker 稳定后，再考虑新增：

1. `relationship_consistency`
2. `motivation_consistency`
3. `belief_consistency`
4. `foreshadow_payoff_consistency`
5. `setting_scope_consistency`

但建议：

> 先把当前 5 个 checker 做扎实，再扩数量。

更细的下一批设计与实现边界，见：

- [`./risk-audit-next-batch-checkers.md`](./risk-audit-next-batch-checkers.md)

---

## 5. 当前最重要的开发顺序

建议顺序：

1. 强化 `character_ooc`
2. 强化 `world_rule_consistency`
3. 强化 `plot_logic_consistency`
4. 强化 `timeline_consistency`
5. 强化 `power_scaling_consistency`
6. 建 review workflow 闭环

---

## 6. 一句话总结

> 当前路线不是继续无限加 checker，而是先把已经进入 roster 的 5 个 checker 做成真正可解释、可聚合、可交付的系统审查能力。

当前 phase-2 第一轮已经证明：plot / timeline / power 三类 checker 可以继续沿“结构化信号 -> 更具体候选 -> 风险卡/cluster 消费”的路径稳定演进。

## Round 2 semantic signal closure

Semantic signal rows now carry stable `metadata_json.canonical_key` values and explicit
`metadata_json.evidence_reason` strings. Candidate links add
`evidence_json.candidate_reason` and endpoint canonical keys. This preserves checker
verdict contracts while giving later evidence-pack and cluster tooling deterministic
sample identifiers.
