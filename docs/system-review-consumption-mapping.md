# 审查结论系统消费字段映射表

这份文档面向：

- 前端工作台
- agentOS 接入层
- 下游自动化消费方

目标不是重新解释 review workflow，而是回答一个更直接的问题：

> 系统里的“卡片 / 列表 / 详情区”分别应该优先消费哪些字段？

配套样例：

- `docs/examples/branch-bundle-review-summary.sample.json`

---

## 1. 系统首页总览卡

推荐数据源：

- `branch_bundle.review_summary`
- `branch_bundle.audit_conclusion`

### 1.1 数字卡

| 卡片 | 推荐字段 | 说明 |
|---|---|---|
| 问题簇总数 | `review_summary.cluster_count` | 当前分支累计问题簇数 |
| 待复核数 | `review_summary.needs_review_count` | 当前仍需人工复核的问题簇 |
| 已关闭数 | `review_summary.resolved_count` | 当前已标记 resolved 的问题簇 |
| 待升级数 | `review_summary.pending_escalation_count` | 当前需更高等级处理的问题簇 |
| 已交接未闭环数 | `review_summary.pending_assignment_count` | 最新事件为 assignment 且未 resolved 的问题簇 |

### 1.2 Top 信息卡

| 卡片 | 推荐字段 | 说明 |
|---|---|---|
| 当前负责人 Top1 | `review_summary.current_owner_top` + `current_owner_top_count` | 当前负责问题簇最多的人 |
| 最新动作执行者 Top1 | `review_summary.latest_actor_top` + `latest_actor_top_count` | 最近动作里最活跃的执行者 |
| 最新动作类型 Top1 | `review_summary.latest_event_type_top` + `latest_event_type_top_count` | 最近最常见的审查动作类型 |
| 当前队列 Top1 | `review_summary.workflow_lane_top` + `workflow_lane_top_count` | 当前最常见的处理队列 |
| 当前队列优先级 Top1 | `review_summary.queue_priority_top` + `queue_priority_top_count` | 当前最常见的处理优先级 |
| 当前建议时限 Top1 | `review_summary.deadline_level_top` + `deadline_level_top_count` | 当前最常见的处理时限等级 |
| 当前批量操作 Top1 | `review_summary.batch_operation_hint_top` + `batch_operation_hint_top_count` | 当前最适合批量执行的处理方式 |
| 当前升级层级 Top1 | `review_summary.escalation_tier_top` + `escalation_tier_top_count` | 当前最常见的升级层级 |
| 当前动作代码 Top1 | `review_summary.auto_next_action_code_top` + `auto_next_action_code_top_count` | 当前最常见的下一步动作代码 |
| 当前原因代码 Top1 | `review_summary.escalation_reason_code_top` + `escalation_reason_code_top_count` | 当前最常见的继续处理原因代码 |
| Phase-2 焦点 Top1 | `review_summary.phase2_focus_top` + `phase2_focus_top_count` | 当前最突出的 phase-2 风险焦点桶 |

### 1.3 首页一句话结论

优先展示：

- `audit_conclusion.pending_escalation_note`
- `audit_conclusion.pending_assignment_note`
- `audit_conclusion.needs_review_note`
- `audit_conclusion.latest_review_note`

推荐优先级：

1. `pending_escalation_note`
2. `pending_assignment_note`
3. `needs_review_note`
4. `latest_review_note`

### 1.4 首页批量处理入口

推荐数据源：

- `review_summary.batch_suggestions`

推荐展示：

| 展示区 | 推荐字段 | 说明 |
|---|---|---|
| 批量处理类型 | `hint_title` | 如批量升级 / 批量交接 / 批量关闭 |
| 动作桶 | `action_bucket` | `escalate / followup / review / close / archive / monitor` |
| 批量优先级 | `batch_priority` | 用于决定入口排序 |
| 批次总排序分 | `suggestion_rank_score` | 决定多个批次之间先处理哪一批 |
| 分组方式 | `group_strategy` + `group_key` | 按 owner 还是按 checker 聚合 |
| 跨度桶 | `span_bucket` | 对人工复核/升级批次区分 `single / burst / long_run` |
| 模式标签 | `pattern_label_top` | 当前批次里最代表性的风险爆发模式 |
| 推荐处理顺序 | `suggested_cluster_order_details` | 系统建议先处理哪些簇 |
| 批次排序解释 | `suggestion_rank_reason` | 解释为什么这批排在当前顺位 |
| Phase-2 焦点 | `phase2_focus_top` | 标识该批次主要聚焦哪类 phase-2 风险 |
| 推荐动作 | `recommended_batch_action` | 面向人的批量动作提示 |

如果要做“批量升级入口”，建议额外展示：

- `suggested_cluster_order_details[*].escalation_urgency_score`
- `suggested_cluster_order_details[*].escalation_rank_reason`
- `suggested_cluster_order_details[*].escalation_batch_rank_score`
- `suggested_cluster_order_details[*].escalation_batch_rank_reason`
- `span_bucket`

如果要做“批量复核入口”，建议额外展示：

- `suggested_cluster_order_details[*].human_review_batch_rank_score`
- `suggested_cluster_order_details[*].human_review_batch_rank_reason`
- `span_bucket`

如果要做“批量关闭入口”，建议额外展示：

- `suggested_cluster_order_details[*].close_stability_score`
- `suggested_cluster_order_details[*].close_ready_rank_reason`
- `suggested_cluster_order_details[*].close_batch_rank_score`
- `suggested_cluster_order_details[*].close_batch_rank_reason`

---

## 2. 问题簇列表页

推荐数据源：

- `branch_bundle.risk_summary.review_candidate_clusters`

### 2.1 列表主字段

| UI 列 | 推荐字段 |
|---|---|
| 标题 | `cluster_title` |
| 优先级 | `review_priority` |
| 当前状态 | `cluster_status` |
| 当前结论 | `review_result` + `review_result_label` |
| 当前负责人 | `review_owner` |
| 涉及章节 | `chapter_span` |
| 类型 | `risk_types` |
| 检查器 | `checker_names` |

### 2.2 列表辅助字段

| UI 列 / 标签 | 推荐字段 | 用法 |
|---|---|---|
| 最近动作类型 | `latest_review_event.event_type` | 显示 assignment/status/review 等 |
| 最近执行人 | `latest_review_event.review_actor` | 显示谁真正做了最近动作 |
| 当前队列 | `workflow_lane` | 显示当前处于升级/交接/复核/关闭/观察哪个队列 |
| 队列优先级 | `queue_priority` | 显示当前簇在处理队列中的紧急程度 |
| 是否需要动作 | `action_required` | 判断当前是否需要继续推进 |
| 建议时限 | `suggested_deadline_level` | 显示 urgent/soon/normal/none/backlog |
| 批量操作提示 | `batch_operation_hint` | 判断该簇更适合并入哪类批量处理 |
| 升级层级 | `escalation_tier` | 显示 `critical / high / medium` 等升级等级 |
| 下一步动作代码 | `auto_next_action_code` | 供系统逻辑或 agentOS 直接判断下一步；phase-2 风险可出现 `prioritize_phase2_human_review` |
| 原因代码 | `escalation_reason_code` | 供系统逻辑或 agentOS 直接判断原因分类；phase-2 风险可出现 `phase2_risk_requires_human_confirmation` |
| 历史条数 | `review_history_count` | 进入详情前判断复杂度 |
| 样例摘要 | `sample_summary` | 列表 hover / 二级文案 |

### 2.3 列表高亮规则

推荐：

- 红色高亮：`review_result == "needs-escalation"`
- 黄色高亮：`cluster_status == "needs_review"`
- 蓝色提示：`latest_review_event.event_type == "assignment_update"`
- 绿色收口：`cluster_status == "resolved"`

---

## 3. 问题簇详情抽屉 / 详情页

推荐数据源：

- `branch_bundle.risk_summary.review_candidate_clusters[*]`
- `latest_review_event`
- `review_history`

### 3.1 详情头部

推荐字段：

- `cluster_title`
- `cluster_status`
- `review_result_label`
- `review_owner`
- `workflow_lane`
- `queue_priority`
- `action_required`
- `suggested_deadline_level`
- `batch_operation_hint`
- `latest_review_event.review_actor`
- `review_priority`

### 3.2 详情正文

推荐字段：

- `sample_summary`
- `suggested_review_action`
- `close_ready_gate`
- `close_ready_reason`
- `close_stability_score`
- `auto_next_action`
- `escalation_reason`
- `escalation_urgency_score`
- `escalation_rank_reason`
- `supporting_evidence_preview`
- `counter_evidence_preview`
- `continuity_evidence_preview`
- `branch_signal_preview`

### 3.3 审计时间线

推荐字段：

- `review_history[*].created_at`
- `review_history[*].event_type`
- `review_history[*].previous_values`
- `review_history[*].current_values`
- `review_history[*].changed_fields`
- `review_history[*].transition`
- `review_history[*].review_owner`
- `review_history[*].review_actor`

---

## 4. 审查结论卡

推荐数据源：

- `branch_bundle.audit_conclusion`

### 4.1 建议直接展示的字段

| 展示区 | 推荐字段 |
|---|---|
| 主结论 | `content_judgement` |
| 风险判断 | `risk_judgement` |
| 阻塞情况 | `blocking_judgement` |
| 建议动作 | `recommended_action` |

### 4.2 review workflow 补充结论

| 展示区 | 推荐字段 |
|---|---|
| 复核进度 | `review_progress_note` |
| 待复核提示 | `needs_review_note` |
| 已关闭提示 | `resolved_cluster_note` |
| 待升级提示 | `pending_escalation_note` |
| 当前负责人概览 | `current_owner_note` |
| 最近执行者概览 | `review_actor_note` |
| 最近动作类型概览 | `latest_event_type_note` |
| 已交接未闭环提示 | `pending_assignment_note` |
| 最新一条动作说明 | `latest_review_note` |

---

## 5. 对 agentOS / 自动化层的建议

如果是 agentOS 或自动化策略，不建议只消费自然语言 note。

推荐策略：

### 优先消费结构化字段

- `pending_escalation_count`
- `pending_assignment_count`
- `resolved_count`
- `needs_review_count`
- `action_required_count`
- `close_ready_count`
- `current_owner_top`
- `latest_actor_top`
- `latest_event_type_top`
- `workflow_lane_top`
- `queue_priority_top`
- `deadline_level_top`
- `batch_operation_hint_top`
- `escalation_tier_top`
- `auto_next_action_code_top`
- `escalation_reason_code_top`
- `phase2_focus_top`
- `batch_suggestions`

### 用自然语言字段补充解释

- `pending_escalation_note`
- `pending_assignment_note`
- `latest_review_note`

也就是：

> **结构化字段决定系统逻辑，note 字段负责解释给人看。**

---

## 6. 最小落地建议

如果当前只做一个很小但有用的系统界面，建议至少做：

1. 首页总览卡
   - `needs_review_count`
   - `pending_escalation_count`
   - `pending_assignment_count`
2. 问题簇列表
   - `cluster_title`
   - `cluster_status`
   - `review_result_label`
   - `review_owner`
   - `latest_review_event.event_type`
3. 底部结论框
   - `pending_escalation_note`
   - `pending_assignment_note`
   - `latest_review_note`

---

## 7. 一句话总结

> 系统首页看 `review_summary`，  
> 结论区看 `audit_conclusion`，  
> 列表与详情看 `review_candidate_clusters + review_history`。
