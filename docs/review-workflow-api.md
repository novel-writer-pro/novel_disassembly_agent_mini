# Review Workflow API 说明

## 1. 目的

这份文档用于说明当前第二阶段 review workflow 已经暴露的最小 API 能力。

面向读者：

- 前端接入者
- 下游 agent / 工具接入者
- 后端维护者

---

## 2. 当前已提供的接口

### A. `GET /api/review-clusters`

作用：

- 读取某个 branch 当前的 review candidate clusters

请求参数：

- `run_id`
- `branch_id`
- `database_url`（可选）
- `cluster_status`（可选）
- `review_owner`（可选）
- `review_result`（可选）

当前返回重点字段：

- `contract_version`
- `stable_contract_version`
- `allowed_cluster_statuses`
- `allowed_review_results`
- `review_storage_mode`
- `filters`
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
- `review_history_count`
- `latest_review_event`

当前过滤语义：

- `cluster_status`
  - 只返回指定状态的问题簇
- `review_owner`
  - 只返回指定处理人的问题簇
- `review_result`
  - 只返回指定复核结果的问题簇

---

### B. `GET /api/review-cluster-history`

作用：

- 读取某个问题簇的 review history

请求参数：

- `branch_id`
- `cluster_key`
- `database_url`（可选）
- `event_type`（可选）
- `review_owner`（可选）
- `review_result`（可选）
- `limit`（可选）

当前返回重点字段：

- `contract_version`
- `stable_contract_version`
- `allowed_cluster_statuses`
- `allowed_review_results`
- `review_storage_mode`
- `filters`
- `event_index`
- `audit_key`
- `previous_values`
- `current_values`
- `previous_cluster_status`
- `previous_review_result`
- `previous_review_notes`
- `previous_review_owner`
- `previous_resolved_at`
- `cluster_status`
- `review_result`
- `review_notes`
- `review_owner`
- `resolved_at`
- `event_type`
- `created_at`
- `changed_fields`
- `transition`

当前 event_type 语义：

- `status_update`
- `result_update`
- `assignment_update`
- `owner_update`
- `actor_update`
- `note_update`
- `resolution_marker_update`
- `review_update`
- `noop_update`

当前过滤语义：

- `event_type`
  - 只返回指定事件类型
- `review_owner`
  - 只返回指定处理人的历史事件
- `review_result`
  - 只返回指定结论的历史事件
- `limit`
  - 只保留最后 N 条匹配事件

---

### C. `GET /api/review-cluster-summary`

作用：

- 返回当前 branch 的问题簇汇总统计

请求参数：

- `run_id`
- `branch_id`
- `database_url`（可选）

当前返回重点字段：

- `contract_version`
- `stable_contract_version`
- `allowed_cluster_statuses`
- `allowed_review_results`
- `review_storage_mode`
- `filters`
- `cluster_count`
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
- `workflow_lane_top`
- `workflow_lane_top_count`
- `queue_priority_top`
- `queue_priority_top_count`
- `deadline_level_top`
- `deadline_level_top_count`
- `batch_operation_hint_top`
- `batch_operation_hint_top_count`
- `auto_next_action_code_top`
- `auto_next_action_code_top_count`
- `auto_next_action_top`
- `auto_next_action_top_count`
- `escalation_reason_code_top`
- `escalation_reason_code_top_count`
- `escalation_reason_top`
- `escalation_reason_top_count`
- `phase2_focus_top`
- `phase2_focus_top_count`
- `pending_assignment_count`
- `pending_escalation_count`
- `resolved_count`
- `needs_review_count`
- `action_required_count`
- `batch_suggestions`
- `by_status`
- `by_result`
- `by_owner`
- `by_actor`
- `by_latest_event_type`
- `by_workflow_lane`
- `by_queue_priority`
- `by_deadline_level`
- `by_batch_operation_hint`
- `by_auto_next_action_code`
- `by_auto_next_action`
- `by_escalation_reason_code`
- `by_escalation_reason`
- `by_phase2_focus`
- `by_priority`
- `by_pattern`

当前过滤语义：

- `cluster_status`
  - 只聚合指定状态的问题簇
- `review_owner`
  - 只聚合指定处理人的问题簇
- `review_result`
  - 只聚合指定复核结果的问题簇

当前额外结构化聚合字段：

- `current_owner_top`
  - 当前问题簇负责人分布中的最高频 owner
- `latest_actor_top`
  - 最新动作记录中的最高频 actor
- `latest_event_type_top`
  - 最新动作记录中的最高频 event_type
- `workflow_lane_top`
  - 当前问题簇最常见的工作流队列
- `queue_priority_top`
  - 当前问题簇最常见的队列优先级
- `deadline_level_top`
  - 当前问题簇最常见的建议处理时限等级
- `batch_operation_hint_top`
  - 当前问题簇最常见的批量处理提示
- `auto_next_action_code_top`
  - 当前问题簇最常见的下一步动作代码
  - phase-2 风险当前可出现 `prioritize_phase2_human_review`
- `auto_next_action_top`
  - 当前问题簇最常见的下一步动作建议
- `escalation_reason_code_top`
  - 当前问题簇最常见的原因代码
  - phase-2 风险当前可出现 `phase2_risk_requires_human_confirmation`
- `escalation_reason_top`
  - 当前问题簇最常见的升级/继续处理原因说明
- `phase2_focus_top`
  - 当前最突出的 phase-2 风险焦点桶（如 `plot-phase2` / `timeline-phase2` / `power-phase2`）
- `pending_assignment_count`
  - 最新事件为 `assignment_update` 且尚未 `resolved` 的问题簇数量
- `pending_escalation_count`
  - 当前 `review_result=needs-escalation` 的问题簇数量
- `resolved_count`
  - 当前 `cluster_status=resolved` 的问题簇数量
- `needs_review_count`
  - 当前 `cluster_status=needs_review` 的问题簇数量
- `action_required_count`
  - 当前仍需要执行后续动作的问题簇数量
- `batch_suggestions`
  - 系统推荐的一组可批量处理簇摘要，适合做批量升级/交接/复核/归档入口
  - 每条 suggestion 当前包含：
    - `hint_code`
    - `hint_title`
    - `action_bucket`
    - `batch_priority`
    - `suggestion_rank_score`
    - `suggestion_rank_reason`
    - `group_strategy`
    - `group_key`
    - `span_bucket`
    - `cluster_count`
    - `cluster_keys`
    - `suggested_cluster_order`
    - `suggested_cluster_order_titles`
    - `suggested_cluster_order_details`
    - `ordering_strategy`
    - `suggested_first_cluster_reason`
    - `cluster_titles`
    - `owners`
    - `suggested_owner`
    - `primary_checker`
    - `pattern_label_top`
    - `risk_types`
    - `phase2_focus_top`
    - `chapter_spans`
    - `queue_priority_top`
    - `deadline_level_top`
    - `action_required`
    - `resolved_candidate_count`
    - `escalation_candidate_count`
    - `suggested_cluster_order_details[*].close_batch_rank_score`
    - `suggested_cluster_order_details[*].close_batch_rank_reason`
    - `suggested_cluster_order_details[*].human_review_batch_rank_score`
    - `suggested_cluster_order_details[*].human_review_batch_rank_reason`
    - `suggested_cluster_order_details[*].escalation_batch_rank_score`
    - `suggested_cluster_order_details[*].escalation_batch_rank_reason`
    - `recommended_batch_action`

---

### D. `POST /api/review-cluster-update`

作用：

- 写入 / 更新某个问题簇的当前 review 状态

请求 body：

- `branch_id`
- `cluster_key`
- `cluster_status`
- `review_result`
- `review_notes`
- `review_owner`
- `review_actor`
- `resolved_at`
- `database_url`（可选）

当前行为：

- 会优先更新 DB-backed review object
- 会追加一条 review history event
- 响应同时返回 `contract_version=review-workflow.v1`
- 响应包含 `stable_contract_version=review-api-pre-v1`，用于下游判断当前合同仍处于 Phase 2 pre-v1

### 常见错误语义

- `400 Bad Request`
  - review 状态组合不合法
  - 例如：
    - `cluster_status=resolved` 但 `review_result` 为空
    - `review_result=needs-escalation` 但 `review_notes` 为空

### fallback / 审计链说明

- DB 表已迁移时，`review_storage_mode=db` 是主路径，history 来自 `cluster_review_event_records`。
- review 表未迁移时，读取接口会显式回落到 `review_storage_mode=file-fallback`；fallback history 现在也补齐统一审计字段，但来源仍应视为兼容路径而非正式 DB 审计链。
- history 事件现在包含 `event_index`、`audit_key`、`previous_values`、`current_values`、`changed_fields` 与 `transition`，用于审计链展示；稳定消费仍应优先绑定基础状态字段。
- `event_type` 会根据实际变更内容自动推导，不再一律固定为 `status_update`，从而区分指派交接、结果确认、备注补录等操作。

---

## 3. 当前约束

### `cluster_status`

当前支持：

- `open`
- `needs_review`
- `reviewed`
- `escalated`
- `reopened`
- `resolved`

### `review_result`

当前支持：

- `confirmed-issue`
- `confirmed-benign`
- `needs-escalation`
- `deferred`

### 运行时硬约束

1. `cluster_status = resolved`
   - 必须带非空 `review_result`

2. `review_result = needs-escalation`
   - 必须带非空 `review_notes`

3. `cluster_status = escalated`
   - 必须搭配 `review_result = needs-escalation`

---

## 4. 当前交付语义

### `review-clusters`

这是面向“当前状态”的读取接口，更适合：

- 前端列表页
- 问题簇当前状态展示
- 当前人工处理结果展示

### `review-cluster-history`

这是面向“历史事件”的读取接口，更适合：

- 历史抽屉
- 审计辅助
- 后续 workflow 升级

### `review-cluster-summary`

这是面向“管理视图 / 聚合视图”的读取接口，更适合：

- 按状态汇总
- 按结果汇总
- 按 owner 汇总

稳定样例：

- `docs/examples/review-cluster-summary.sample.json`
- `docs/examples/review-cluster-summary.stable.sample.json`
- `docs/examples/review-cluster-summary.stable.v1.sample.json`
- `docs/examples/branch-bundle-review-summary.sample.json`（用于系统消费 `review_summary + audit_conclusion` 联合片段）
- `docs/review-batch-execution-contract.md`（用于 batch execution 请求/响应结构与阶段落地状态说明）

当前批量执行历史接口：

- `GET /api/review-batch-history?branch_id=...`
  - 用于读取 batch execute 的执行回执历史

### `review-cluster-update`

这是最小写回接口，更适合：

- 小团队内部试用
- 最小 review workflow 原型

---

## 5. 当前边界

需要明确：

1. 当前 API 已可用，但仍属于第二阶段最小实现
2. 还没有完整 reviewer 审计链
3. 还没有完整权限/协作模型
4. 还没有正式 UI 对接

---

## 6. 字段稳定性建议

### 当前建议视为“正式对外字段”

#### `GET /api/review-clusters`

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

#### `GET /api/review-cluster-history`

- `cluster_status`
- `review_result`
- `review_notes`
- `review_owner`
- `review_actor`
- `resolved_at`
- `event_type`

#### `POST /api/review-cluster-update`

- `branch_id`
- `cluster_key`
- `cluster_status`
- `review_result`
- `review_notes`
- `review_owner`
- `resolved_at`

### 当前更偏“内部 / 实验字段”

这些字段目前可消费，但后续仍可能调整：

- `review_history`
- `review_history_count`
- `latest_review_event`
- `review_storage_mode`
- `review_progress_note`
- `review_result_note`
- `review_owner_note`
- `current_owner_note`
- `review_actor_note`
- `latest_event_type_note`
- `pending_assignment_note`
- `needs_review_note`
- `resolved_cluster_note`
- `pending_escalation_note`
- `latest_review_note`

建议：

- 面向正式接入优先依赖“正式对外字段”
- 对内部/实验字段做宽松消费，不要强绑定

---

## 7. 稳定样例契约

建议正式接入方优先参考：

- `docs/examples/review-clusters.stable.sample.json`
- `docs/examples/review-cluster-history.stable.sample.json`

这两份样例只保留当前建议视为“正式对外字段”的最小集合。

---

## 8. 一句话总结

> 当前 review workflow API 已经具备最小可接入能力：  
> 可读当前 cluster、可读 history、可写当前 review 状态，适合作为第二阶段正式化的起点。

---

## 7. 请求 / 响应样例

可参考：

- `docs/examples/review-clusters.sample.json`
- `docs/examples/review-cluster-history.sample.json`
- `docs/examples/review-cluster-update.request.sample.json`
- `docs/examples/review-cluster-update.response.sample.json`
- `docs/examples/review-cluster-update.error.sample.json`


## Stable sample note

- `docs/examples/review-cluster-summary.sample.json` 表示当前较完整的 pre-v1 / phase-2 扩展合同样例。
- `docs/examples/review-cluster-summary.stable.sample.json` 与 `docs/examples/review-cluster-summary.stable.v1.sample.json` 目前刻意保持为较小的稳定字段子集，用于演示下游只消费稳定核心字段的场景。
- 因此 stable sample 不强制包含 `phase2_focus_top`、`by_phase2_focus`、`prioritize_phase2_human_review`、`phase2_risk_requires_human_confirmation`。
- 当这些字段进入明确冻结合同后，再统一升级 stable sample。
