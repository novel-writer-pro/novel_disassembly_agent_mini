# Interface Manifest / Schema Guide

本文件说明拆书 agent 当前稳定可消费的 JSON 输出接口，供前端、下游 agent、问答层和写作者工具接入。

> 说明：这里是“结构契约文档”，不是强约束 JSON Schema 文件，但字段已对齐当前实现与 live export。

---

## 1. Chapter Bundle

来源：
- `novel-analyzer show-chapter <branch_id> <chapter_index>`
- `novel-analyzer export-chapter-bundle <branch_id> <chapter_index> <output_path>`

顶层字段：
- `chapter_index: int`
- `artifact: object`
- `facts: list[object]`
- `retrieval: object`
- `graph_nodes: list[object]`
- `graph_edges: list[object]`
- `reasoning_graph: object`
- `state_summary: object`

### 1.1 artifact
关键字段：
- `chapter_index`
- `normalized_title`
- `chapter_summary`
- `key_entities`
- `key_events`
- `continuity_notes`
- `state_transition_notes`
- `evidence_backed_resolutions`
- `unresolved_threads`
- `writer_learning_notes`
- `unsupported_inferences`
- `ambiguous_points`
- `needs_human_review`
- `quality_gate_notes`
- `hook_score`
- `state_summary`

### 1.2 state_summary
字段：
- `new_foreshadowing`
- `paid_off_foreshadowing`
- `new_conflicts`
- `escalated_conflicts`
- `stable_relations`
- `evolved_relations`
- `observed_world_rules`
- `constraining_world_rules`

### 1.3 reasoning_graph
关键字段：
- `overview`
- `central_nodes`
- `recent_timeline`
- `reasoning_paths`
- `active_conflicts`
- `open_foreshadowing`
- `world_rules`
- `state_machine`
- `nodes`
- `edges`

---

## 2. Branch Bundle

来源：
- `novel-analyzer export-branch-bundle <run_id> <branch_id> <output_path>`

顶层字段：
- `status`
- `chapter_index`
- `windows`
- `graph_nodes`
- `graph_edges`
- `reasoning_graph`
- `state_summary`
- `chapter_output_summary`
- `failed_summary`
- `audit_conclusion`
- `review_summary`
- `risk_summary`

### 2.1 chapter_output_summary
用于整本/整分支级汇总：
- `state_transition_notes: list[{chapter_index, note}]`
- `evidence_backed_resolutions: list[{chapter_index, note}]`
- `unresolved_threads: list[{chapter_index, note}]`

### 2.2 risk_summary
当前已扩展包含：
- `risk_card_count`
- `checker_result_count`
- `review_candidate_count`
- `high_risk_chapters`
- `risk_counts_by_domain`
- `risk_counts_by_severity`
- `review_candidates_summary`
- `review_candidate_clusters`

### 2.3 audit_conclusion
当前已扩展包含：
- `content_judgement`
- `risk_judgement`
- `blocking_judgement`
- `recommended_action`
- `review_progress_note`
- `needs_review_note`
- `resolved_cluster_note`
- `review_result_note`
- `pending_escalation_note`
- `review_owner_note`
- `current_owner_note`
- `review_actor_note`
- `latest_event_type_note`
- `pending_assignment_note`
- `latest_review_note`

### 2.4 review_summary
当前已扩展包含：
- `cluster_count`
- `by_status`
- `by_result`
- `by_owner`
- `by_actor`
- `by_latest_event_type`
- `by_priority`
- `by_pattern`
- `history_event_count`
- `latest_review_at`
- `latest_review_owner`
- `latest_review_actor`
- `latest_review_event_type`
- `latest_review_result`
- `latest_review_result_label`
- `current_owner_top`
- `current_owner_top_count`
- `latest_actor_top`
- `latest_actor_top_count`
- `latest_event_type_top`
- `latest_event_type_top_count`
- `pending_assignment_count`
- `pending_escalation_count`
- `resolved_count`
- `needs_review_count`

稳定样例：
- `docs/examples/branch-bundle-review-summary.sample.json`

### 2.5 review workflow stability note

对于 review workflow 相关字段，当前建议：

- 顶层 contract 字段：
  - `contract_version`
  - `stable_contract_version`
  - `allowed_cluster_statuses`
  - `allowed_review_results`

- 稳定对外字段：
  - `cluster_key`
  - `cluster_title`
  - `checker_names`
  - `risk_types`
  - `review_priority`
  - `cluster_status`
  - `review_result`
  - `review_result_label`
  - `chapter_span`
  - `review_owner`

- 更偏内部 / 实验字段：
  - `review_history`
  - `review_history_count`
  - `latest_review_event`
  - `review_progress_note`
  - `review_result_note`
  - `review_owner_note`
  - `latest_review_note`

---

## 3. Chapter QA Context

来源：
- `novel-analyzer export-chapter-qa-context <branch_id> <chapter_index> <output_path>`
- package 导出中的 `chapters/chapter_XXXX.qa-context.json`

顶层字段：
- `chapter_index`
- `title`
- `chapter_summary`
- `key_events`
- `state_transition_notes`
- `evidence_backed_resolutions`
- `unresolved_threads`
- `facts`
- `retrieval`
- `query_hints`
- `recommended_questions`
- `reasoning_graph`
- `state_summary`

---

## 4. Branch QA Context

来源：
- `novel-analyzer export-branch-qa-context <run_id> <branch_id> <output_path>`
- package 导出中的 `branch_qa_context.json`

顶层字段：
- `status`
- `chapter_index`
- `windows`
- `state_summary`
- `chapter_output_summary`
- `recommended_questions`
- `reasoning_graph`
- `retrieval_documents`
- `thematic_contexts`

### 4.1 retrieval_documents
每项字段：
- `chapter_index`
- `title`
- `summary_text`
- `keyword_list`
- `query_hints`

---

## 5. Thematic Contexts

字段路径：
- `branch_qa_context.thematic_contexts`

当前固定主题：
- `character_arc`
- `conflict_arc`
- `foreshadow_arc`
- `world_rule_arc`

### 5.1 通用字段
大多数主题入口包含：
- `recommended_questions`
- `question_sequence`
- `related_chapters`
- `evidence_summaries`
- `reasoning_paths`
- `state_signals`
- `supporting_facts`
- `node_refs`
- `edge_refs`
- `timeline_points`

### 5.2 可视化友好字段
#### `node_refs`
节点引用列表，常用字段：
- `node_type`
- `label`
- `chapter_first_seen`
- `chapter_last_seen`

#### `edge_refs`
边引用列表，常用字段：
- `edge_type`
- `source`
- `target`
- `chapter_first_seen`
- `chapter_last_seen`

#### `timeline_points`
用于时间线展示，字段：
- `chapter_index`
- `summary`

---

## 6. Review Workflow / Batch Execution Views

来源：
- `GET /api/review-clusters?branch_id=...`
- `GET /api/review-cluster-history?branch_id=...&cluster_key=...`
- `GET /api/review-summary?branch_id=...`
- `POST /api/review-batch-execute`
- `GET /api/review-batch-history?branch_id=...`

### 6.1 `review-clusters`

建议稳定消费字段：
- `cluster_key`
- `cluster_title`
- `checker_names`
- `risk_types`
- `review_priority`
- `cluster_status`
- `review_result`
- `review_result_label`
- `chapter_span`
- `review_owner`

可增强消费字段：
- `latest_review_event`
- `review_history_count`
- `review_progress_note`
- `review_result_note`
- `latest_review_note`

### 6.2 `review-summary`

当前系统已稳定提供的聚合视图包括：
- `cluster_count`
- `by_status`
- `by_result`
- `by_owner`
- `by_priority`
- `history_event_count`
- `pending_assignment_count`
- `pending_escalation_count`
- `resolved_count`
- `needs_review_count`
- `batch_suggestions`

phase-2 聚合增强字段：
- `by_phase2_focus`
- `phase2_focus_top`
- `phase2_focus_top_count`
- `auto_next_action_code_top`
- `escalation_reason_code_top`

### 6.3 `review-batch-execute`

当前执行回执建议消费字段：
- `execution_id`
- `action`
- `hint_code`
- `target_count`
- `success_count`
- `failed_count`
- `skipped_count`
- `preview`
- `successes`
- `failed`
- `skipped`

### 6.4 `review-batch-history`

当前批量执行历史建议消费字段：
- `items[*].execution_id`
- `items[*].created_at`
- `items[*].action`
- `items[*].hint_code`
- `items[*].group_strategy`
- `items[*].group_key`
- `items[*].dry_run`
- `items[*].target_count`
- `items[*].success_count`
- `items[*].failed_count`
- `items[*].skipped_count`
- `items[*].preview`

说明：
- 当前是 runtime file-backed 最小审计链
- 对系统集成方来说已经足够承接回执、操作历史、批量确认弹窗
- 更完整语义见 [`./review-batch-execution-contract.md`](./review-batch-execution-contract.md)

## 7. Recommended Integration Order

### 7.1 前端最小接入
1. `chapter bundle`
2. `branch report`
3. `chapter QA context`
4. `branch QA context`

### 7.2 问答工具接入
1. 先用 `branch QA context.recommended_questions`
2. 再按 `thematic_contexts.*.question_sequence` 引导追问
3. 需要图谱视图时使用：
   - `node_refs`
   - `edge_refs`
   - `timeline_points`

### 7.3 写作者参考接入
优先使用：
- `artifact.chapter_summary`
- `artifact.state_transition_notes`
- `artifact.evidence_backed_resolutions`
- `artifact.unresolved_threads`
- `writer_learning_notes`
- `branch chapter_output_summary`

---

## 8. Stability Notes

当前这些接口可视为“项目内稳定输出面”：
- chapter bundle
- branch bundle
- chapter QA context
- branch QA context
- thematic contexts
- whole-book imitation run report（CLI / service contract）

未来允许新增字段，但应尽量保持已有字段名与基础层级不破坏。

## 9. Example Files

- [`./examples/chapter-bundle.sample.json`](./examples/chapter-bundle.sample.json)
- [`./examples/branch-bundle.sample.json`](./examples/branch-bundle.sample.json)
- [`./examples/chapter-qa-context.sample.json`](./examples/chapter-qa-context.sample.json)
- [`./examples/branch-qa-context.sample.json`](./examples/branch-qa-context.sample.json)
- [`./examples/review-clusters.stable.sample.json`](./examples/review-clusters.stable.sample.json)
- [`./examples/review-cluster-history.stable.sample.json`](./examples/review-cluster-history.stable.sample.json)
- [`./examples/review-cluster-summary.sample.json`](./examples/review-cluster-summary.sample.json)
- [`./examples/review-cluster-summary.stable.sample.json`](./examples/review-cluster-summary.stable.sample.json)
- [`./examples/review-cluster-summary.stable.v1.sample.json`](./examples/review-cluster-summary.stable.v1.sample.json)
- [`./examples/whole-book-imitation-run.sample.json`](./examples/whole-book-imitation-run.sample.json)

## 10. Whole-Book Imitation Run Report

来源：
- `novel-analyzer run-whole-book-imitation ...`
- `WholeBookImitationService.build_run_queue(...)`
- `WholeBookImitationService.run_in_sandbox(...)`

用途：
- 供系统直接查看整本仿写/续写编排结果
- 供 agentOS 或调度器读取“下一步先修什么 / 哪几章优先”
- 供后续 API/export 层继续冻结为稳定 contract

### 10.1 顶层字段

- `branch_id`
- `project_title`
- `queue`
- `carry_over_notes`
- `execution_mode`
- `executed_steps`
- `final_carry_over_state`
- `policy_summary`
- `dashboard_summary`
- `run_notes`

### 10.2 dry-run 必看字段

当 `execution_mode = "dry_run"` 时，建议系统优先消费：

- `queue[*].order`
- `queue[*].source_chapter_index`
- `queue[*].target_goal`
- `queue[*].prerequisites`
- `queue[*].carry_over_inputs`
- `queue[*].risk_focus`
- `queue[*].scheduling_priority`
- `queue[*].scheduling_reason`

- `policy_summary.queue_length`
- `policy_summary.highest_queue_priority`
- `policy_summary.queue_priorities`
- `policy_summary.priority_reason_histogram`

- `dashboard_summary.queue_priority_preview`
- `dashboard_summary.top_queue_priority_chapters`
- `dashboard_summary.queue_cluster_buckets`
- `dashboard_summary.queue_next_actions`

### 10.3 sandbox execute 必看字段

当 `execution_mode = "sandbox_execute"` 时，建议系统优先消费：

- `executed_steps[*].source_chapter_index`
- `executed_steps[*].overall_score`
- `executed_steps[*].overall_risk_level`
- `executed_steps[*].stop_reason`
- `executed_steps[*].scheduling_priority`
- `executed_steps[*].scheduling_reason`
- `executed_steps[*].strategy_input`
- `executed_steps[*].policy_summary`
- `executed_steps[*].carry_over_state`
- `executed_steps[*].action_queue`
- `executed_steps[*].revise_payload`

- `policy_summary.executed_step_count`
- `policy_summary.chapter_ranking`
- `policy_summary.book_priority_ranking`
- `policy_summary.severity_histogram`
- `policy_summary.risk_bucket_histogram`
- `policy_summary.next_stage_focus`

- `dashboard_summary.highest_priority_chapters`
- `dashboard_summary.top_risk_chapters`
- `dashboard_summary.strategy_targets`
- `dashboard_summary.top_priority_summary`
- `dashboard_summary.top_risk_summary`
- `dashboard_summary.chapter_flags`
- `dashboard_summary.book_handoff_summary`

### 10.4 `book_handoff_summary`

这是当前最适合系统侧直接读取的聚合层：

- `top_repair_recommendations`
  - 每项包含：
    - `action_type`
    - `count`
    - `highest_priority`
    - `highest_severity`
    - `chapter_indexes`
    - `targets`
    - `issue_families`
- `next_stage_focus`
- `highest_priority_chapters`
- `risk_chapters`
- `final_verdicts`

建议用法：
- 调度器先看 `next_stage_focus`
- 任务分派器先看 `top_repair_recommendations`
- 章节回看列表先看 `highest_priority_chapters`
- 风险复核列表再看 `risk_chapters`

稳定样例：
- `docs/examples/whole-book-imitation-run.sample.json`
