# 审查结论系统展示规则建议

这份文档不是 UI 实现稿，而是给系统接入方的**展示规则建议**。

目标：

- 统一系统里 review workflow 相关信息的视觉优先级
- 明确哪些字段适合做红黄绿提示
- 明确列表排序与卡片优先级

配套文档：

- `docs/system-review-consumption-mapping.md`
- `docs/examples/branch-bundle-review-summary.sample.json`

---

## 1. 首页总览卡的优先级

推荐从高到低：

1. `pending_escalation_count`
2. `pending_assignment_count`
3. `needs_review_count`
4. `resolved_count`

原因：

- 待升级问题通常最需要立刻处理
- 已交接未闭环说明流程有滞留风险
- 待复核是正常待办，但优先级通常低于升级
- 已解决更适合展示完成度

## 1.1 批量处理入口排序建议

如果首页要放“批量处理入口”，推荐按下面优先级显示 `batch_suggestions`：

1. `action_bucket == "escalate"`
2. `action_bucket == "followup"`
3. `action_bucket == "review"`
4. `action_bucket == "close"`
5. `action_bucket == "archive"`
6. `action_bucket == "monitor"`

同一动作桶内再按：

1. `batch_priority`
2. `cluster_count`
3. `group_strategy`

如果系统直接采用后端推荐顺序，建议优先按：

- `suggestion_rank_score` 倒序

并把：

- `suggestion_rank_reason`

作为“为什么这批排在这里”的解释文案。

---

## 2. 建议的颜色语义

### workflow_lane 与颜色的推荐映射

| workflow_lane | 推荐颜色 | 含义 |
|---|---|---|
| `escalation_queue` | 红色 | 需要更高等级处理 |
| `assignment_queue` | 蓝色 | 已交接但未闭环 |
| `human_review_queue` | 黄色 | 仍待人工复核 |
| `resolved_queue` | 绿色 | 已关闭 / 已确认收口 |
| `monitor_queue` | 灰色 | 暂时观察 |

### 时限等级与展示建议

| suggested_deadline_level | 展示建议 |
|---|---|
| `urgent` | 红色角标 / 置顶提醒 |
| `soon` | 蓝色或橙色提醒 |
| `normal` | 普通待办 |
| `none` | 不展示催办 |
| `backlog` | 灰色观察 |

### 升级层级与展示建议

| escalation_tier | 展示建议 |
|---|---|
| `critical` | 红色高优先告警，固定置顶 |
| `high` | 红色或橙色高优先提醒 |
| `medium` | 橙色普通升级提醒 |
| `""` | 非升级簇可不展示 |

### 动作代码 / 原因代码的使用建议

phase-2 风险额外建议：
- 当 `auto_next_action_code = prioritize_phase2_human_review` 时，前端应突出显示“优先人工复核”
- 当 `escalation_reason_code = phase2_risk_requires_human_confirmation` 时，应把该簇视为“需先人工确认后再决定升级/关闭”的特殊候选
- 当 `phase2_focus_top` 存在时，可在卡片或标签区显示 `plot-phase2 / timeline-phase2 / power-phase2` 焦点


推荐：

- 系统路由、自动化判断优先使用：
  - `auto_next_action_code`
  - `escalation_reason_code`
- 面向人的解释优先使用：
  - `auto_next_action`
  - `escalation_reason`

### 红色

适用：

- `pending_escalation_count > 0`
- `review_result == "needs-escalation"`
- `cluster_status == "escalated"`

代表：

> 需要更高等级处理 / 当前风险最强

### 黄色

适用：

- `needs_review_count > 0`
- `cluster_status == "needs_review"`

代表：

> 仍待人工复核

### 蓝色

适用：

- `pending_assignment_count > 0`
- `latest_review_event.event_type == "assignment_update"`

代表：

> 已交接 / 流程推进中，但尚未闭环

### 绿色

适用：

- `resolved_count > 0`
- `cluster_status == "resolved"`
- `review_result == "confirmed-benign"`

代表：

> 已处理或已确认无问题

---

## 3. 问题簇列表排序建议

推荐排序键：

1. `review_result == "needs-escalation"`
2. `cluster_status == "needs_review"`
3. `latest_review_event.event_type == "assignment_update"`
4. `review_priority`
5. `workflow_lane`
6. `chapter_count`
7. `latest_review_event.created_at`

可转成更具体的排序策略：

### 第一层：状态桶

1. `escalated`
2. `needs_review`
3. `reviewed`
4. `reopened`
5. `open`
6. `resolved`

### 第二层：结论桶

1. `needs-escalation`
2. `deferred`
3. `confirmed-issue`
4. `confirmed-benign`

### 第三层：业务优先级

1. `P1`
2. `P2`
3. `P3`

---

## 4. 首页一句话提示的优先级

如果首页只展示一条主提示，推荐优先级：

1. `pending_escalation_note`
2. `pending_assignment_note`
3. `needs_review_note`
4. `latest_review_note`
5. `resolved_cluster_note`

原因：

- 优先展示“需要立刻动作”的信息
- “最近发生了什么”比“已经完成了什么”更重要

---

## 5. 列表行内推荐展示

每个问题簇列表项建议最少展示：

- `cluster_title`
- `cluster_status`
- `review_result_label`
- `workflow_lane`
- `queue_priority`
- `action_required`
- `suggested_deadline_level`
- `batch_operation_hint`
- `escalation_tier`
- `auto_next_action_code`
- `escalation_reason_code`
- `phase2_focus_top`
- `review_owner`
- `latest_review_event.event_type`
- `latest_review_event.review_actor`

推荐附加展示：

- `chapter_span`
- `review_priority`
- `review_history_count`

---

## 6. 详情页推荐展示

详情页建议分 3 块：

### A. 当前状态块

- `cluster_status`
- `review_result_label`
- `review_owner`
- `latest_review_event.review_actor`
- `workflow_lane`
- `queue_priority`
- `action_required`
- `suggested_deadline_level`
- `batch_operation_hint`
- `escalation_tier`
- `auto_next_action_code`
- `escalation_reason_code`
- `phase2_focus_top`

### B. 证据块

- `sample_summary`
- `close_ready_gate`
- `close_ready_reason`
- `close_stability_score`
- `auto_next_action`
- `escalation_reason`
- `escalation_urgency_score`
- `escalation_rank_reason`
- `supporting_evidence_preview`
- `counter_evidence_preview`
- `branch_signal_preview`

补充建议：

- 如果 `workflow_lane == escalation_queue`
  - 优先显示 `escalation_urgency_score`
  - 再显示 `escalation_batch_rank_score`
  - 再显示 `escalation_rank_reason`
  - 再显示 `escalation_batch_rank_reason`
- 如果 `workflow_lane == human_review_queue`
  - 优先显示 `human_review_batch_rank_score`
  - 再显示 `human_review_batch_rank_reason`
- 如果 `batch_operation_hint == batch_close_ready_candidates`
  - 优先显示 `close_ready_gate`
  - 再显示 `close_stability_score`
  - 再显示 `close_batch_rank_score`
  - 最后显示 `close_ready_reason`
  - 如需解释排序，再显示 `close_batch_rank_reason`

### C. 历史时间线块

- `review_history[*].created_at`
- `review_history[*].event_type`
- `review_history[*].transition`
- `review_history[*].review_owner`
- `review_history[*].review_actor`

---

## 7. 对 agentOS / 自动化层的展示建议

如果系统未来接 agentOS，不建议让 agent 直接从自然语言 note 做路由判断。

推荐：

### 用结构化字段做决策

- `pending_escalation_count`
- `pending_assignment_count`
- `needs_review_count`
- `latest_event_type_top`
- `queue_priority_top`
- `deadline_level_top`
- `batch_operation_hint_top`
- `escalation_tier_top`
- `auto_next_action_code_top`
- `escalation_reason_code_top`

### 用自然语言 note 做解释

- `pending_escalation_note`
- `pending_assignment_note`
- `latest_review_note`

即：

> agent 依据结构化字段决策，  
> 系统界面依据 note 向人解释。

---

## 8. 最小可用展示方案

如果当前系统只做一个最小可用版本，建议：

### 首页

- 红色卡：`pending_escalation_count`
- 蓝色卡：`pending_assignment_count`
- 黄色卡：`needs_review_count`
- 绿色卡：`resolved_count`

### 批量处理入口

- 升级入口：优先消费 `batch_suggestions` 中 `action_bucket=escalate`
- 交接催办入口：优先消费 `action_bucket=followup`
- 复核入口：优先消费 `action_bucket=review`
- 关闭入口：优先消费 `action_bucket=close`

如果是复核入口，建议进一步按 `span_bucket` 区分：

- `single`：单点问题，适合快速逐条核验
- `burst`：集中爆发，适合连续章节打包复核
- `long_run`：持续型问题，适合做纵向连续性复核

如果是升级入口，也建议按 `span_bucket` 区分：

- `single`：单点升级候选，适合快速升级判断
- `burst`：集中爆发型升级候选，适合同批次一起升级
- `long_run`：持续型升级候选，适合优先拉高处理等级

### 列表

- 标题
- 当前状态
- 当前结论
- 当前负责人
- 最近动作类型

### 结论框

- `pending_escalation_note`
- `pending_assignment_note`
- `needs_review_note`

---

## 9. 一句话总结

> 红色看升级，蓝色看交接，黄色看待复核，绿色看已关闭。  
> 决策靠结构化字段，解释靠自然语言 note。
