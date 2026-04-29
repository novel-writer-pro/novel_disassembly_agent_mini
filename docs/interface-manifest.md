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
- `review_result_note`
- `review_owner_note`
- `latest_review_note`

### 2.4 review workflow stability note

对于 review workflow 相关字段，当前建议：

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

## 6. Recommended Integration Order

### 前端最小接入
1. `chapter bundle`
2. `branch report`
3. `chapter QA context`
4. `branch QA context`

### 问答工具接入
1. 先用 `branch QA context.recommended_questions`
2. 再按 `thematic_contexts.*.question_sequence` 引导追问
3. 需要图谱视图时使用：
   - `node_refs`
   - `edge_refs`
   - `timeline_points`

### 写作者参考接入
优先使用：
- `artifact.chapter_summary`
- `artifact.state_transition_notes`
- `artifact.evidence_backed_resolutions`
- `artifact.unresolved_threads`
- `writer_learning_notes`
- `branch chapter_output_summary`

---

## 7. Stability Notes

当前这些接口可视为“项目内稳定输出面”：
- chapter bundle
- branch bundle
- chapter QA context
- branch QA context
- thematic contexts

未来允许新增字段，但应尽量保持已有字段名与基础层级不破坏。

## 8. Example Files

- [`./examples/chapter-bundle.sample.json`](./examples/chapter-bundle.sample.json)
- [`./examples/branch-bundle.sample.json`](./examples/branch-bundle.sample.json)
- [`./examples/chapter-qa-context.sample.json`](./examples/chapter-qa-context.sample.json)
- [`./examples/branch-qa-context.sample.json`](./examples/branch-qa-context.sample.json)
- [`./examples/review-clusters.stable.sample.json`](./examples/review-clusters.stable.sample.json)
- [`./examples/review-cluster-history.stable.sample.json`](./examples/review-cluster-history.stable.sample.json)
- [`./examples/review-cluster-summary.sample.json`](./examples/review-cluster-summary.sample.json)
- [`./examples/review-cluster-summary.stable.sample.json`](./examples/review-cluster-summary.stable.sample.json)
