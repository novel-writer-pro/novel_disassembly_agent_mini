# 审查结论系统上线 / 回归清单

这份清单用于：

- 系统上线前自检
- 回归测试时快速核对
- 多角色协同时统一验收口径

配套文档：

- `docs/system-review-integration-checklist.md`
- `docs/system-review-consumption-mapping.md`
- `docs/system-review-display-rules.md`

---

## 1. 数据契约检查

- [ ] `branch_bundle` 顶层包含 `review_summary`
- [ ] `branch_bundle` 顶层包含 `audit_conclusion`
- [ ] `review_summary` 包含：
  - [ ] `cluster_count`
  - [ ] `pending_assignment_count`
  - [ ] `pending_escalation_count`
  - [ ] `resolved_count`
  - [ ] `needs_review_count`
  - [ ] `action_required_count`
  - [ ] `close_ready_count`
  - [ ] `workflow_lane_top`
  - [ ] `queue_priority_top`
  - [ ] `deadline_level_top`
  - [ ] `batch_operation_hint_top`
  - [ ] `auto_next_action_code_top`
  - [ ] `escalation_reason_code_top`
  - [ ] `phase2_focus_top`
- [ ] `batch_suggestions`
- [ ] phase-2 专门动作码/原因码已在数据中可见
- [ ] `audit_conclusion` 包含：
  - [ ] `pending_assignment_note`
  - [ ] `pending_escalation_note`
  - [ ] `needs_review_note`
  - [ ] `resolved_cluster_note`
  - [ ] `latest_review_note`

---

## 2. 首页总览卡检查

- [ ] 能显示问题簇总数
- [ ] 能显示待复核数
- [ ] 能显示待升级数
- [ ] 能显示已交接未闭环数
- [ ] 能显示已关闭数
- [ ] 颜色语义正确：
  - [ ] 红色 = 升级
  - [ ] 蓝色 = 交接
  - [ ] 黄色 = 待复核
  - [ ] 绿色 = 已关闭

---

## 3. 问题簇列表检查

- [ ] 能显示 `cluster_title`
- [ ] 能显示 `cluster_status`
- [ ] 能显示 `review_result_label`
- [ ] 能显示 `review_owner`
- [ ] 能显示 `workflow_lane`
- [ ] 能显示 `queue_priority`
- [ ] 能显示 `action_required`
- [ ] 能显示 `suggested_deadline_level`
- [ ] 能显示 `batch_operation_hint`
- [ ] 能显示 `span_bucket`
- [ ] 能显示 `pattern_label_top`
- [ ] 能显示 `close_ready_gate`
- [ ] 能显示 `close_ready_reason`
- [ ] 能显示 `close_stability_score`
- [ ] 能显示 `suggested_cluster_order_details[*].close_batch_rank_score`
- [ ] 能显示 `suggested_cluster_order_details[*].close_batch_rank_reason`
- [ ] 能显示 `auto_next_action_code`
- [ ] 能显示 `escalation_reason_code`
- [ ] 能显示 `phase2_focus_top`（如 summary/batch/列表已接入）
- [ ] 能显示 `prioritize_phase2_human_review`
- [ ] 能显示 `phase2_risk_requires_human_confirmation`
- [ ] 能显示 `escalation_urgency_score`
- [ ] 能显示 `escalation_rank_reason`
- [ ] 能显示 `suggested_cluster_order_details[*].escalation_batch_rank_score`
- [ ] 能显示 `suggested_cluster_order_details[*].escalation_batch_rank_reason`
- [ ] 能显示 `latest_review_event.event_type`
- [ ] 能显示 `latest_review_event.review_actor`
- [ ] 批量处理入口能按 `suggestion_rank_score` 排序
- [ ] 排序符合预期：
- [ ] 待升级优先
- [ ] 待复核其次
- [ ] 已交接未闭环再次
- [ ] 升级入口能按 `span_bucket` 区分批次

---

## 4. 详情页 / 抽屉检查

- [ ] 能显示 `sample_summary`
- [ ] 能显示 `suggested_review_action`
- [ ] 能显示 `supporting_evidence_preview`
- [ ] 能显示 `counter_evidence_preview`
- [ ] 能显示 `suggested_cluster_order_details[*].human_review_batch_rank_score`
- [ ] 能显示 `suggested_cluster_order_details[*].human_review_batch_rank_reason`
- [ ] 能显示 history 时间线
- [ ] 时间线能区分：
  - [ ] `assignment_update`
  - [ ] `status_update`
  - [ ] `review_update`
  - [ ] `needs-escalation` 相关动作

---

## 5. 结论框检查

- [ ] 主结论可见：
  - [ ] `content_judgement`
  - [ ] `risk_judgement`
  - [ ] `recommended_action`
- [ ] 补充结论可见：
  - [ ] `pending_escalation_note`
  - [ ] `pending_assignment_note`
  - [ ] `needs_review_note`
  - [ ] `latest_review_note`

---

## 6. API / Bundle 一致性检查

- [ ] `/api/review-cluster-summary` 与 `branch_bundle.review_summary` 核心计数字段一致
- [ ] `latest_review_owner` 一致
- [ ] `latest_review_actor` 一致
- [ ] `latest_review_event_type` 一致
- [ ] `pending_assignment_count` 一致
- [ ] `pending_escalation_count` 一致
- [ ] `close_ready_count` 一致
- [ ] `queue_priority_top` 一致
- [ ] `deadline_level_top` 一致
- [ ] `batch_operation_hint_top` 一致
- [ ] `phase2_focus_top` 一致
- [ ] `prioritize_phase2_human_review` 一致
- [ ] `phase2_risk_requires_human_confirmation` 一致

---

## 7. 回归场景检查

至少覆盖以下 4 类场景：

- [ ] 正常待复核场景
- [ ] 已交接未闭环场景
- [ ] 待升级场景
- [ ] 已关闭场景

推荐额外覆盖：

- [ ] owner / actor 变化同时发生
- [ ] fallback 路径读取 history
- [ ] summary API 过滤后结果仍然正确

---

## 8. 上线前最终确认

- [ ] 文档索引已更新
- [ ] sample JSON 已更新
- [ ] 相关 pytest 已通过
- [ ] 已知 warning 已记录
- [ ] 无阻塞上线的未处理错误

---

## 9. 一句话总结

> 上线前先核对数据契约，再核对首页、列表、详情、结论框，  
> 最后确认 API / bundle 一致性与 4 类核心回归场景。
