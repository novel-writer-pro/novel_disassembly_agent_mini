# 审查结论系统接入最小清单

这份清单面向：

- 前端接入者
- agentOS 接入者
- 系统集成人员

目标：

> 用最小步骤把 review workflow 的审查结论能力接到系统里。

配套文档：

- `docs/interface-manifest.md`
- `docs/system-review-consumption-mapping.md`
- `docs/system-review-display-rules.md`
- `docs/examples/branch-bundle-review-summary.sample.json`

---

## 1. 最小接入目标

如果只做一个基础可用版本，至少完成下面三块：

1. 首页总览卡
2. 问题簇列表
3. 审查结论框

---

## 2. 首页总览卡检查项

数据源：

- `branch_bundle.review_summary`

至少接入：

- [ ] `cluster_count`
- [ ] `needs_review_count`
- [ ] `pending_escalation_count`
- [ ] `pending_assignment_count`
- [ ] `resolved_count`
- [ ] `action_required_count`
- [ ] `close_ready_count`

建议接入：

- [ ] `current_owner_top`
- [ ] `latest_actor_top`
- [ ] `latest_event_type_top`
- [ ] `workflow_lane_top`
- [ ] `queue_priority_top`
- [ ] `deadline_level_top`
- [ ] `batch_operation_hint_top`
- [ ] `auto_next_action_code_top`
- [ ] `escalation_reason_code_top`
- [ ] `phase2_focus_top`
- [ ] `prioritize_phase2_human_review`
- [ ] `phase2_risk_requires_human_confirmation`

展示规则：

- [ ] 当 `auto_next_action_code_top = prioritize_phase2_human_review` 时，首页应突出“优先人工复核”
- [ ] 当 `phase2_focus_top` 存在时，可显示 `plot-phase2 / timeline-phase2 / power-phase2` 焦点标签
- [ ] 红色卡展示 `pending_escalation_count`
- [ ] 蓝色卡展示 `pending_assignment_count`
- [ ] 黄色卡展示 `needs_review_count`
- [ ] 绿色卡展示 `resolved_count`

---

## 3. 问题簇列表检查项

数据源：

- `branch_bundle.risk_summary.review_candidate_clusters`

至少接入：

- [ ] `cluster_title`
- [ ] `cluster_status`
- [ ] `review_result_label`
- [ ] `review_owner`
- [ ] `chapter_span`

建议接入：

- [ ] `review_priority`
- [ ] `workflow_lane`
- [ ] `queue_priority`
- [ ] `action_required`
- [ ] `suggested_deadline_level`
- [ ] `batch_operation_hint`
- [ ] `auto_next_action_code`
- [ ] `escalation_reason_code`
- [ ] `phase2_focus_top`（如 summary/batch 层已接入）
- [ ] `prioritize_phase2_human_review` 行为已接入（如 phase-2 风险存在）
- [ ] `phase2_risk_requires_human_confirmation` 行为已接入（如 phase-2 风险存在）
- [ ] `latest_review_event.event_type`
- [ ] `latest_review_event.review_actor`
- [ ] `review_history_count`

排序规则：

- [ ] 优先把 `needs-escalation` 放前面
- [ ] 其次把 `needs_review` 放前面
- [ ] 再把 `assignment_update` 放前面

---

## 4. 审查结论框检查项

数据源：

- `branch_bundle.audit_conclusion`

至少接入：

- [ ] `content_judgement`
- [ ] `risk_judgement`
- [ ] `recommended_action`

建议接入：

- [ ] `pending_escalation_note`
- [ ] `pending_assignment_note`
- [ ] `needs_review_note`
- [ ] `latest_review_note`

补充信息：

- [ ] `review_progress_note`
- [ ] `resolved_cluster_note`
- [ ] `current_owner_note`
- [ ] `review_actor_note`
- [ ] `latest_event_type_note`

---

## 5. 详情页 / 抽屉检查项

数据源：

- `review_candidate_clusters[*]`
- `latest_review_event`
- `review_history`

至少接入：

- [ ] `sample_summary`
- [ ] `suggested_review_action`
- [ ] `latest_review_event.event_type`
- [ ] `latest_review_event.review_owner`
- [ ] `latest_review_event.review_actor`

建议接入：

- [ ] `supporting_evidence_preview`
- [ ] `counter_evidence_preview`
- [ ] `continuity_evidence_preview`
- [ ] `branch_signal_preview`
- [ ] `suggested_cluster_order_details[*].human_review_batch_rank_score`
- [ ] `suggested_cluster_order_details[*].human_review_batch_rank_reason`
- [ ] `close_ready_gate`
- [ ] `close_ready_reason`
- [ ] `close_stability_score`
- [ ] `suggested_cluster_order_details[*].close_batch_rank_score`
- [ ] `suggested_cluster_order_details[*].close_batch_rank_reason`
- [ ] `auto_next_action_code`
- [ ] `escalation_reason_code`
- [ ] `phase2_focus_top`（如 summary/batch 层已接入）
- [ ] `prioritize_phase2_human_review` 行为已接入（如 phase-2 风险存在）
- [ ] `phase2_risk_requires_human_confirmation` 行为已接入（如 phase-2 风险存在）
- [ ] `escalation_urgency_score`
- [ ] `escalation_rank_reason`
- [ ] `suggested_cluster_order_details[*].escalation_batch_rank_score`
- [ ] `suggested_cluster_order_details[*].escalation_batch_rank_reason`
- [ ] `review_history[*].transition`
- [ ] `review_history[*].changed_fields`

---

## 5.1 批量处理入口检查项

数据源：

- `branch_bundle.review_summary.batch_suggestions`

至少接入：

- [ ] `hint_title`
- [ ] `action_bucket`
- [ ] `batch_priority`
- [ ] `suggestion_rank_score`
- [ ] `cluster_count`
- [ ] `recommended_batch_action`

建议接入：

- [ ] `group_strategy`
- [ ] `group_key`
- [ ] `span_bucket`
- [ ] `pattern_label_top`
- [ ] `suggestion_rank_reason`
- [ ] `suggested_cluster_order`
- [ ] `suggested_cluster_order_details`
- [ ] `suggested_first_cluster_reason`
- [ ] `phase2_focus_top`

补充建议：

- [ ] 升级入口按 `span_bucket` 做二次分组

---

## 6. agentOS / 自动化接入检查项

优先消费结构化字段：

- [ ] `pending_escalation_count`
- [ ] `pending_assignment_count`
- [ ] `needs_review_count`
- [ ] `latest_event_type_top`
- [ ] `queue_priority_top`
- [ ] `deadline_level_top`
- [ ] `batch_operation_hint_top`
- [ ] `auto_next_action_code_top`
- [ ] `escalation_reason_code_top`
- [ ] `phase2_focus_top`

只把自然语言字段用于解释：

- [ ] `pending_escalation_note`
- [ ] `pending_assignment_note`
- [ ] `latest_review_note`

不要只靠自然语言做路由判断：

- [ ] 不直接用 note 文本做核心流程决策

---

## 7. 联调验收清单

- [ ] branch bundle 中存在 `review_summary`
- [ ] branch bundle 中存在 `audit_conclusion`
- [ ] 系统能读取 `review-batch-history`
- [ ] 系统能显示首页四张核心卡片
- [ ] 系统能显示问题簇列表
- [ ] 系统能显示至少一条审查结论 note
- [ ] 系统能在详情中展示最近动作类型与执行人
- [ ] 系统能显示至少一条 batch execute 回执
- [ ] 待升级 / 待交接 / 待复核 / 已关闭 四类状态能正确区分

---

## 8. 最小上线建议

如果要快速上线一个可用版本，推荐顺序：

1. 首页四张数字卡
2. 问题簇列表
3. 审查结论框
4. 详情历史抽屉

也就是：

> 先把“看得见风险”做出来，  
> 再把“解释风险为什么这样判断”补齐。

---

## 9. 一句话总结

> 最小接入先做总览卡、列表、结论框；  
> 结构化字段保证系统可控，note 字段保证系统可读。
