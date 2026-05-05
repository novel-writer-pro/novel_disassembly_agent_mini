# 统一风险审查体系（系统能力说明）

## 定位

`novel-analyzer` 当前不仅是章节拆书系统，也在逐步演进为一套 **面向作家 / 编辑 / 审稿者的统一风险审查体系**。

它的目标不是接管创作，也不是自动改文，而是：

1. 对新章做 **设定/连续性风险审查**
2. 输出 **章节风险卡（chapter risk card）**
3. 给出 **风险细节 + 证据 + 反证**
4. 帮助人工快速判断“这一章是否值得复核”

默认语义是：

- **advisory-only**
- **只提示，不阻断主提交**

---

## 系统当前已经拥有的审查输出

### 1. 章节风险卡

每章可聚合输出：

- `overall_risk_level`
- `top_risks`
- `risk_counts_by_domain`
- `risk_counts_by_severity`
- `checker_statuses`
- `coverage_gaps`

### 2. 风险细节

每条风险项统一采用 `GateRiskItem` 表示，包含：

- `checker_name`
- `risk_domain`
- `risk_type`
- `severity`
- `confidence`
- `summary`
- `supporting_evidence`
- `counter_evidence`
- `related_entities`
- `related_chapters`
- `needs_human_review`

### 3. 分支/作品级审查摘要

当前系统可在 branch 级导出：

- `risk_summary`
- `failed_summary`
- `review_candidates_summary`
- `review_candidate_clusters`
- `audit_conclusion`
- Markdown `branch_report`
- JSON `branch_bundle`
- package 级逐章导出产物

---

## 当前已正式落地的 checker

### A. `character_ooc`

用于检测人物层风险，例如：

- 动机偏移
- 性格/立场异常
- 角色行为与既有人设不一致
- 信息不足时的人工复核候选

当前已开始复用：

- `unsupported_inferences`
- `ambiguous_points`
- `state_transition_notes`
- `evidence_backed_resolutions`
- `unresolved_threads`

### B. `world_rule_consistency`

用于检测规则层风险，例如：

- 世界规则被打脸
- 既有约束突然失效
- 设定口径前后不一致
- 信息不足时的规则人工复核候选

当前已开始复用：

- `world_rule_signals`
- `unsupported_inferences`
- `ambiguous_points`
- `evidence_backed_resolutions`
- `unresolved_threads`

---

## 下一批 checker（Phase 1 已纳入系统 roster）

以下七类已经纳入系统 checker roster，其中关系、伏笔、设定作用域与线程收束 checker 已开始第一轮落地：

### C. `relationship_consistency`

领域：`relationship`

目标：

- 检测人物关系口径突然跳变
- 检测信任/敌意状态冲突
- 检测敌对关系缓和过快且桥接不足

当前阶段：

- 已落地 checker contract
- 支持 `relationship_issues`
- 已开始复用现有 artifact / state_summary 信号：
  - `state_summary.stable_relations`
  - `state_summary.evolved_relations`
  - `unsupported_inferences`
  - `state_transition_notes`
  - `evidence_backed_resolutions`
  - `unresolved_threads`
- 在信号不足时只会输出 `relationship_review_candidate` 或 `skipped`
- 当前第一轮已新增更细候选：
  - `relationship_shift_without_bridge`
  - `trust_state_conflict`
  - `hostility_resolution_too_fast`

### D. `foreshadow_payoff_consistency`

领域：`foreshadow`

目标：

- 检测当前兑现是否缺少前置铺垫
- 检测已解决线索是否无解释重开
- 检测关键伏笔/线程长期悬置

当前阶段：

- 已落地 checker contract
- 支持 `foreshadow_payoff_issues`
- 已开始复用现有 artifact / state_summary 信号：
  - `state_summary.new_foreshadowing`
  - `state_summary.paid_off_foreshadowing`
  - `unsupported_inferences`
  - `evidence_backed_resolutions`
  - `unresolved_threads`
- 在信号不足时只会输出 `foreshadow_review_candidate` 或 `skipped`
- 当前第一轮已新增更细候选：
  - `payoff_without_setup`
  - `resolved_thread_reopened_without_reason`
  - `important_thread_long_unmentioned`

### E. `setting_scope_consistency`

领域：`setting_scope`

目标：

- 检测设定作用域是否被异常放大/缩小
- 检测资源/次数/额度限制是否无解释失效
- 检测权限/组织/地理边界是否被可疑突破

当前阶段：

- 已落地 checker contract
- 支持 `setting_scope_issues`
- 已开始复用现有 artifact / state_summary 信号：
  - `state_summary.observed_world_rules`
  - `state_summary.constraining_world_rules`
  - `unsupported_inferences`
  - `state_transition_notes`
  - `unresolved_threads`
- 在信号不足时只会输出 `setting_scope_review_candidate` 或 `skipped`
- 当前第一轮已新增更细候选：
  - `constraint_scope_expansion`
  - `resource_limit_missing`
  - `authority_boundary_conflict`

### F. `thread_closure_consistency`

领域：`thread_closure`

目标：

- 检测升级冲突是否失去后续承接
- 检测收束/已解决表述是否缺少解决依据
- 检测阶段性结尾是否存在收束不稳候选

当前阶段：

- 已落地 checker contract
- 支持 `thread_closure_issues`
- 已开始复用现有 artifact / state_summary 信号：
  - `state_summary.new_conflicts`
  - `state_summary.escalated_conflicts`
  - `unsupported_inferences`
  - `evidence_backed_resolutions`
  - `unresolved_threads`
- 在信号不足时只会输出 `thread_closure_review_candidate` 或 `skipped`
- 当前第一轮已新增更细候选：
  - `thread_dropped_after_escalation`
  - `closure_without_resolution_basis`
  - `ending_stability_candidate`

### G. `plot_logic_consistency`

领域：`plot`

目标：

- 检测剧情因果链断裂
- 检测关键行动缺少必要前置
- 检测推断链跳步过大

当前阶段：

- 已落地 checker contract
- 支持 `plot_logic_issues`
- 已开始复用现有 artifact 信号：
  - `unsupported_inferences`
  - `state_transition_notes`
  - `evidence_backed_resolutions`
  - `unresolved_threads`
- 在信号不足时只会输出 `logic_review_candidate` 或 `skipped`
- phase-2 第一轮已新增更细候选：
  - `thread_state_conflict`
  - `motivation_to_action_gap`

### H. `timeline_consistency`

领域：`timeline`

目标：

- 检测时间线冲突
- 检测事件顺序不一致
- 检测状态恢复/推进时间异常

当前阶段：

- 已落地 checker contract
- 支持 `timeline_issues`
- 已开始复用现有 artifact 信号：
  - `timeline_signals`
  - `unsupported_inferences`
  - `ambiguous_points`
  - `state_transition_notes`
  - `unresolved_threads`
- 在信号不足时只会输出 `timeline_review_candidate` 或 `skipped`
- phase-2 第一轮已新增更细候选：
  - `sequence_conflict_candidate`
  - `recovery_window_insufficient`

### I. `power_scaling_consistency`

领域：`power`

目标：

- 检测战力漂移
- 检测能力突然跳变
- 检测越阶/压制缺乏前置解释

当前阶段：

- 已落地 checker contract
- 支持 `power_scaling_issues`
- 已开始复用现有 artifact 信号：
  - `power_signals`
  - `unsupported_inferences`
  - `ambiguous_points`
  - `state_transition_notes`
  - `unresolved_threads`
- 在信号不足时只会输出 `power_review_candidate` 或 `skipped`
- phase-2 第一轮已新增更细候选：
  - `upset_without_setup`
  - `cost_constraint_missing`

---

## 当前系统能力边界

需要明确：

1. 当前不是所有 checker 都已经达到高质量召回。
2. 当前最成熟的是：
   - 人物 OOC
   - 规则一致性
3. 关系 / 伏笔兑现 / 设定作用域 / 线程收束 / 剧情因果 / 时间线 / 战力 checker 目前处于：
   - **系统 contract 已落地**
   - **advisory 语义已稳定**
   - **phase-2 第一轮结构化候选已落地**
   - **高质量 cross-chapter 信号底座仍需继续建设**

因此当前对外表述建议是：

> 系统已经具备统一风险审查体系的第一阶段能力，当前正式覆盖人物 OOC 与规则一致性，并已将人物关系、伏笔兑现、设定作用域、线程收束、剧情因果、时间线、战力漂移纳入统一 checker 体系，后续将在相同框架下持续提质。

---

## 对外建议表述

推荐使用以下说法：

- 统一风险审查体系
- 章节一致性审查
- 小说设定/连续性门控
- 风险卡 + 人工复核候选

不建议使用以下说法：

- “Codex 帮你看”
- “大模型临时检查”
- “AI 自动给你改文”

---

## 当前系统已经具备的交付层

当前系统不仅能产出 `ChapterRiskCard`，还已经能产出：

1. `review_candidates_summary`
2. `review_candidate_clusters`
3. `audit_conclusion`
4. Markdown / JSON 双交付

其中：

- `review_candidate_clusters` 当前已具备：
  - `cluster_title`
  - `suggested_review_action`
  - `review_priority`
  - `cluster_status`

- `audit_conclusion` 当前已具备：
  - `content_judgement`
  - `risk_judgement`
  - `blocking_judgement`
  - `recommended_action`

这说明当前系统已经具备：

> 风险卡 → 候选问题 → 问题簇 → 结构化结论

的第一阶段完整交付链路。

---

## 下一阶段开发重点

1. **共享信号底座提质**
   - Character signals
   - Rule signals
   - Event causality signals
   - Timeline signals
   - Power-state signals

2. **Checker 提质顺序建议**
   1. `plot_logic_consistency`
   2. `timeline_consistency`
   3. `power_scaling_consistency`
   4. 下一批新增 checker 设计收口见：
      - [`./risk-audit-next-batch-checkers.md`](./risk-audit-next-batch-checkers.md)

3. **交付层优化**
   - 报告里直接写“当前最终审查结论”
   - 给 human review candidate 增加 evidence 摘要
   - 给 branch report 增加更适合作家/编辑使用的审阅视角
