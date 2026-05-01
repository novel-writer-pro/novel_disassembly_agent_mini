# 风险审查第二批 Checker：技术路线与落地文档

## 1. 文档目的

这份文档专门回答第二批 checker 的三个问题：

1. **接下来补强什么**
2. **每个 checker 具体怎么补**
3. **补到什么程度算可交付**

这里的“第二批 checker”特指当前已经进入统一 checker roster、但仍需继续提质的三类能力：

- `plot_logic_consistency`
- `timeline_consistency`
- `power_scaling_consistency`

它们不是新发明的 checker，而是：

> **已经进入系统主路径、已经有 contract、已经能产出 advisory 风险，但还需要继续从“可跑”走向“可信”。**

---

## 2. 范围定义

## 2.1 in scope

本阶段聚焦三件事：

1. **补强三类 checker 的输入信号模型**
2. **补强风险项生成逻辑与降噪规则**
3. **补强交付层的解释性字段与验证基线**

## 2.2 out of scope

本阶段不做：

1. 新增大量 checker 门类
2. 自动修文 / 自动改 canon
3. 作品级总评分
4. UI 先行改造
5. 主观文风 / 好不好看判断

---

## 3. 当前状态判断

### 3.1 已有基础

当前三类 checker 都已经具备：

- 统一 `GateChecker` contract
- 统一 `CheckerResult` 输出
- 统一 `GateRiskItem` 风险项
- 统一 chapter risk card 聚合链路
- branch bundle / branch report / review summary 消费能力

### 3.2 当前短板

它们当前的主要问题不是“没有接上系统”，而是：

1. **过度依赖摘要字段**
2. **跨章节证据链还不够强**
3. **例外情况与真正异常的区分还不够稳**
4. **提示能跑，但解释性和排序质量还不够好**

因此本阶段目标不是“再接一遍”，而是：

> **让三类 checker 从 contract-first advisory，升级到 evidence-first advisory。**

---

## 4. 统一实施原则

### 4.1 只做风险提示，不抢最终判断

所有 checker 继续保持：

- `advisory-only`
- 默认只做风险提示
- 高风险也不自动改文、不自动定罪

### 4.2 先强证据，再强结论

升级顺序必须是：

1. 先补结构化 signal
2. 再补 checker 规则
3. 再补聚合排序
4. 最后才考虑调高 severity / confidence

### 4.3 优先抑制误报

对作家 / 编辑辅助工具来说：

- **低噪音** 比 **虚高召回** 更重要
- 无法闭合证据链时，宁可：
  - `needs_human_review=true`
  - `severity=low`
  - `status=partial/skipped`

### 4.4 所有异常都要给反证位

第二批 checker 的风险项必须继续保留并优先补强：

- `supporting_evidence`
- `counter_evidence`
- `needs_human_review`
- `related_chapters`
- `related_entities`

---

## 5. Checker A：`plot_logic_consistency`

## 5.1 目标

检测以下问题：

1. 关键行动缺少前置动机或条件
2. 结果出现，但中间因果桥缺失
3. 冲突推进方向与前文既有状态不兼容
4. 已解决 / 未解决 / 兑现 / 反转的叙事状态被错误声明

## 5.2 当前已用输入

当前已开始复用：

- `unsupported_inferences`
- `state_transition_notes`
- `evidence_backed_resolutions`
- `unresolved_threads`

## 5.3 第二阶段应新增/强化的信号

建议形成 `EventCausalitySignal` / `PlotTransitionSignal` 两类共享信号：

### A. `EventCausalitySignal`

建议字段：

- `event_key`
- `chapter_index`
- `trigger_event`
- `outcome_event`
- `causal_bridge_present`
- `bridge_evidence`
- `bridge_gap_reason`
- `dependency_entities`
- `dependency_rules`

### B. `PlotTransitionSignal`

建议字段：

- `thread_key`
- `chapter_index`
- `thread_state` (`open|advancing|resolved|reversed|ambiguous`)
- `state_change_reason`
- `evidence_snippets`
- `contradicting_snippets`

## 5.4 风险类型建议

重点稳定以下 `risk_type`：

- `logic_gap_candidate`
- `causal_bridge_missing`
- `resolution_without_support`
- `thread_state_conflict`
- `motivation_to_action_gap`

### 当前已落地的 phase-2 候选

- `thread_state_conflict`
- `motivation_to_action_gap`

说明：
- 前者用于识别“已解决”与“未解线程”并置的线程状态冲突
- 后者用于识别动机/决定与行动/结果之间的因果桥不足

## 5.5 降噪规则

以下情况优先降级为人工复核候选，而不是直接高风险：

1. 本章明确采用省略叙事 / 跳场
2. 因果桥存在于上一章结尾或窗口摘要中
3. 角色故意隐瞒信息，导致读者视角暂时缺桥
4. “未解释”只是暂未兑现，不是已冲突

## 5.6 可交付门槛

达到以下标准才算进入“稳定 advisory”：

1. 至少能区分：
   - 真因果断裂
   - 暂未解释
   - 刻意留白
2. 输出风险项时，至少附带：
   - 1 条支持证据
   - 1 条反证或替代解释
3. cluster 聚合时能把同一 thread 的多章问题串起来

---

## 6. Checker B：`timeline_consistency`

## 6.1 目标

检测以下问题：

1. 时间先后顺序冲突
2. 恢复、闭关、赶路、成长周期不合理
3. “当夜/次日/三日后/半年后”等锚点互相打架
4. 状态变化发生得过快，但没有明确时间补偿

## 6.2 当前已用输入

当前已开始复用：

- `timeline_signals`
- `unsupported_inferences`
- `ambiguous_points`
- `state_transition_notes`
- `unresolved_threads`

## 6.3 第二阶段应新增/强化的信号

建议形成 `TimelineSignalRecord`：

- `chapter_index`
- `anchor_text`
- `anchor_type` (`absolute|relative|duration|sequence`)
- `normalized_time_span`
- `subject_entity`
- `related_event`
- `previous_anchor_ref`
- `consistency_status`
- `conflict_reason`

建议再补 `RecoveryDurationSignal`：

- `subject_entity`
- `state_type` (`injury|cultivation|travel|cooldown|resource_recovery`)
- `declared_duration`
- `expected_duration_band`
- `supporting_context`
- `possible_exception_reason`

## 6.4 风险类型建议

优先稳定：

- `timeline_conflict`
- `sequence_conflict`
- `duration_implausible`
- `recovery_window_insufficient`
- `time_anchor_ambiguity_candidate`

### 当前已落地的 phase-2 候选

- `sequence_conflict_candidate`
- `recovery_window_insufficient`

说明：
- 前者用于识别 `当夜/次日` 等短窗口时间锚点并置
- 后者用于识别恢复/赶路/再战之间可能存在的时长不足

## 6.5 降噪规则

以下情况优先降级：

1. 文本明确用了“约莫”“不久后”“许久之后”等模糊时间
2. 章节切换造成时间压缩，但分支摘要可解释
3. 世界规则允许时间流速差异 / 秘境时间偏移
4. 人物口述时间不可靠，而叙事主视角未确认

## 6.6 可交付门槛

1. 至少能识别并区分：
   - 明确顺序冲突
   - 时长不足
   - 时间锚点不足
2. 不能因为“模糊时间表达”大量误报
3. 能把跨章节恢复周期问题聚成一个 cluster

---

## 7. Checker C：`power_scaling_consistency`

## 7.1 目标

检测以下问题：

1. 战力提升过快且没有代价解释
2. 能力表现突然突破既有上限
3. 越阶取胜缺少前置铺垫或规则例外
4. 资源、伤势、冷却限制突然消失

## 7.2 当前已用输入

当前已开始复用：

- `power_signals`
- `unsupported_inferences`
- `ambiguous_points`
- `state_transition_notes`
- `unresolved_threads`

## 7.3 第二阶段应新增/强化的信号

建议形成 `PowerStateSignalRecord`：

- `subject_entity`
- `chapter_index`
- `power_dimension` (`realm|skill|artifact|combat_output|resource_capacity`)
- `current_state`
- `previous_state`
- `state_delta`
- `delta_reason`
- `cost_or_constraint`
- `exception_clause`

建议再补 `CombatOutcomeSignal`：

- `chapter_index`
- `actor`
- `opponent`
- `declared_advantage`
- `actual_outcome`
- `upset_level`
- `explaining_factors`
- `missing_explanation_reason`

## 7.4 风险类型建议

优先稳定：

- `power_jump_candidate`
- `capability_ceiling_break`
- `upset_without_setup`
- `cost_constraint_missing`
- `resource_limit_inconsistency`

### 当前已落地的 phase-2 候选

- `upset_without_setup`
- `cost_constraint_missing`

说明：
- 前者用于识别越阶/压制结果出现，但前置铺垫不足
- 后者用于识别强力表现后的代价/限制/冷却说明不足

## 7.5 降噪规则

以下情况优先降级：

1. 有明确奇遇、外挂、秘法、环境加成
2. 对手轻敌、受伤、被克制、属性相斥
3. 本章只是能力展示角度不同，不是能力新增
4. 战斗胜负并不等于战力绝对压制

## 7.6 可交付门槛

1. 能区分：
   - 正常成长
   - 破格但可解释
   - 真正异常跳变
2. 能给出“代价/限制是否仍存在”的证据判断
3. 同一角色跨章节能力漂移可被串成连续问题簇

---

## 8. 共享信号底座建议

第二批 checker 不应各自重复造轮子，建议优先沉淀以下共享结构：

1. `EventCausalitySignal`
2. `PlotTransitionSignal`
3. `TimelineSignalRecord`
4. `RecoveryDurationSignal`
5. `PowerStateSignalRecord`
6. `CombatOutcomeSignal`

### 8.1 为什么先做共享信号

因为第二批 checker 的核心难点不是“写 if/else”，而是：

- 需要跨章节对比
- 需要区分“异常”与“例外”
- 需要把 LLM 摘要转成稳定证据

### 8.2 共享信号的工程收益

1. 降低 checker 间重复逻辑
2. 让 export / report 能展示更稳定的证据源
3. 方便后续扩展：
   - `foreshadow_payoff_consistency`
   - `relationship_consistency`
   - `motivation_consistency`

---

## 9. 风险项输出约束

第二批 checker 输出的 `GateRiskItem` 建议统一遵守以下约束：

### 9.1 何时允许 high

只有满足以下条件才允许 `severity=high`：

1. 至少 2 个独立证据点支持
2. 至少 1 个反证位已尝试排除
3. 异常不是单章孤例，而是与历史基线冲突

### 9.2 何时必须 low + human review

以下情况一律优先：

- `severity=low`
- `needs_human_review=true`

适用条件：

1. 证据链不闭合
2. 可能存在题材特例
3. 可能被后续章节解释
4. 只依赖单章模糊表述

### 9.3 summary 写法要求

风险 summary 必须：

1. 说清“哪一类异常”
2. 说清“发生在谁/哪条线/哪个事件”
3. 不直接替作者下最终结论

推荐风格：

- “存在 XX 风险候选，当前证据显示……”
- “本章出现 XX 漂移迹象，但仍需结合前后文复核……”

避免风格：

- “此章已经写崩”
- “作者这里明显出错”

---

## 10. 实施顺序建议

建议按下面顺序推进，而不是三类平均发力：

### Step 1：`timeline_consistency`

原因：

- 信号相对更客观
- 更容易做结构化锚点
- 更适合作为 cross-chapter 信号底座试验田

### Step 2：`power_scaling_consistency`

原因：

- 与时间/恢复/资源限制强相关
- 在已有 timeline signal 后更容易降噪

### Step 3：`plot_logic_consistency`

原因：

- 因果链最强依赖语义解释
- 误报成本最高
- 最适合放在前两类稳定后再深做

---

## 11. 测试与验收基线

## 11.1 单元测试

每个 checker 至少补：

1. 真异常样例
2. 看似异常但可解释样例
3. 信号不足降级样例
4. 跨章节聚合样例

## 11.2 集成测试

至少验证：

1. risk card 能反映三类 checker 新字段
2. branch bundle / branch report 可导出解释性证据
3. review candidate / cluster 可稳定承接第二批 checker 风险

## 11.3 验收门槛

至少满足：

1. 不因三类 checker 提质破坏现有 review workflow
2. 不显著抬高误报噪音
3. 报告可直接给编辑/作家看懂
4. `72 passed` 这类主干回归不被破坏

---

## 12. 与后续扩展的关系

第二批 checker 做扎实之后，才建议继续扩：

- `relationship_consistency`
- `motivation_consistency`
- `belief_consistency`
- `foreshadow_payoff_consistency`
- `setting_scope_consistency`

原因很简单：

> 第二批 checker 解决的是“剧情/时间/战力”这组最容易出现真实连续性问题、又最容易误报的核心中层能力。

只有这层稳定后，统一风险审查体系才算真正站稳。

---

## 13. 一句话总结

> 第二批 checker 的重点不是继续“加门类”，而是把 `plot_logic_consistency`、`timeline_consistency`、`power_scaling_consistency` 从已有 contract 提升成更稳定、更低噪音、更强证据链的系统审查能力。

截至当前，这一阶段已经至少落地 6 类更具体、可测试的 phase-2 风险语义：
- plot: `thread_state_conflict`, `motivation_to_action_gap`
- timeline: `sequence_conflict_candidate`, `recovery_window_insufficient`
- power: `upset_without_setup`, `cost_constraint_missing`
