# Review API 稳定字段收口清单

## 1. 目的

这份文档用于给接入方一个更短、更明确的结论：

1. 哪些字段当前可视为稳定字段
2. 哪些字段仍属于实验/增强字段
3. 后续如果有字段变化，应该怎么处理

---

## 2. 当前建议的稳定接口

### `GET /api/review-clusters`

当前建议稳定字段：

- `stable_contract_version`
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

### `GET /api/review-cluster-history`

当前建议稳定字段：

- `stable_contract_version`
- `review_storage_mode`
- `filters`
- `event_index`
- `audit_key`
- `cluster_status`
- `review_result`
- `review_notes`
- `review_owner`
- `resolved_at`
- `event_type`
- `created_at`

### `POST /api/review-cluster-update`

当前建议稳定输入字段：

- `branch_id`
- `cluster_key`
- `cluster_status`
- `review_result`
- `review_notes`
- `review_owner`
- `resolved_at`

### `GET /api/review-cluster-summary`

当前建议稳定字段：

- `stable_contract_version`
- `review_storage_mode`
- `filters`
- `cluster_count`
- `by_status`
- `by_result`
- `by_owner`

---

## 3. 当前更偏实验/增强字段

这些字段当前可以使用，但不建议下游强绑定：

- `review_history`
- `review_history_count`
- `latest_review_event`
- `previous_values`
- `current_values`
- `changed_fields`
- `transition`
- `review_progress_note`
- `review_result_note`
- `review_owner_note`
- `latest_review_note`
- `pattern_label`
- `review_storage_note`

---

## 4. 建议接入策略

### 稳定字段

建议：

- 可以直接接入
- 可以作为正式依赖字段

### 实验字段

建议：

- 宽松消费
- 允许不存在
- 允许未来增强或收敛

---

## 5. 废弃策略建议

### 对稳定字段

- 不轻易改名
- 不轻易删除
- 优先新增字段而不是破坏旧字段

### 对实验字段

- 允许继续增强
- 允许在后续版本中收口
- 变更前应至少在文档中说明

---

## 6. 当前建议的版本语义

当前建议：

> review API 作为 **Phase 2 pre-v1** 管理

也就是说：

- 稳定字段已经可以按“准正式字段”使用
- 实验字段仍不建议强绑定

---

## 7. 一句话总结

> 接入方当前可以把 review API 当作“准稳定接口”使用：  
> 稳定字段可接，实验字段宽松消费，后续等 Phase 2 收口后再正式宣布 `v1`。

当前响应中的 `stable_contract_version=review-api-pre-v1` 是显式合同标记；在正式 v1 前，下游应把它当作兼容判断字段，而不是 UI 文案。
