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

- `review_storage_mode`
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

当前返回重点字段：

- `cluster_status`
- `review_result`
- `review_notes`
- `review_owner`
- `resolved_at`
- `event_type`
- `created_at`

---

### C. `GET /api/review-cluster-summary`

作用：

- 返回当前 branch 的问题簇汇总统计

请求参数：

- `run_id`
- `branch_id`
- `database_url`（可选）

当前返回重点字段：

- `review_storage_mode`
- `cluster_count`
- `history_event_count`
- `latest_review_at`
- `latest_review_owner`
- `latest_review_result`
- `by_status`
- `by_result`
- `by_owner`

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
- `resolved_at`
- `database_url`（可选）

当前行为：

- 会更新 DB-backed review object
- 会追加一条 review history event

### 常见错误语义

- `400 Bad Request`
  - review 状态组合不合法
  - 例如：
    - `cluster_status=resolved` 但 `review_result` 为空
    - `review_result=needs-escalation` 但 `review_notes` 为空

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
