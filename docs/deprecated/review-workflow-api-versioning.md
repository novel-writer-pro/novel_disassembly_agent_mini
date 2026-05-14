# Review Workflow API 版本化策略

## 1. 目的

这份文档用于说明：

1. 当前 review API 什么时候可以视为 `v1`
2. 哪些字段可视为稳定字段
3. 哪些字段可以继续扩展
4. 后续怎么避免接口口径漂移

---

## 2. 当前建议

当前建议把 review API 视为：

> **Phase 2 pre-v1**

原因：

- 接口已经可用
- 契约与样例已经成型
- 但 review workflow 仍在继续正式化

因此现在最合适的状态是：

- 不立刻声称 fully stable v1
- 但可以开始按“准稳定接口”管理

---

## 3. 进入 `v1` 的建议条件

建议至少满足：

1. DB-backed review object / history 彻底稳定
2. fallback 角色已明确
3. review API 字段稳定集固定
4. API 集成测试稳定通过
5. review workflow 状态机语义不再频繁变化

---

## 4. 当前建议视为 v1 稳定字段

### `GET /api/review-clusters`

建议视为稳定：

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

建议视为稳定：

- `cluster_status`
- `review_result`
- `review_notes`
- `review_owner`
- `resolved_at`
- `event_type`

### `POST /api/review-cluster-update`

建议视为稳定：

- `branch_id`
- `cluster_key`
- `cluster_status`
- `review_result`
- `review_notes`
- `review_owner`
- `resolved_at`

---

## 5. 当前仍可扩展的字段

这些字段当前可以继续调整，不建议让接入方强绑定：

- `review_history`
- `review_history_count`
- `latest_review_event`
- `review_storage_mode`
- `review_progress_note`
- `review_result_note`
- `review_owner_note`
- `latest_review_note`

---

## 6. 建议的版本化规则

### 规则 A：稳定字段不轻易改名

一旦进入 v1 稳定集：

- 不轻易删除
- 不轻易改名
- 若必须变化，优先新增字段而不是破坏旧字段

### 规则 B：增强字段允许增量扩展

对于扩展字段：

- 允许新增
- 允许语义增强
- 但应避免让旧消费方崩溃

### 规则 C：状态枚举变更视为高风险变更

以下内容若变，应视为高风险接口变更：

- `cluster_status`
- `review_result`

---

## 7. 当前推荐策略

短期：

- 继续以 `pre-v1` 管理
- 对稳定字段做强文档化

中期：

- 当 DB 主路径和状态机稳定后，升级为 `v1`

长期：

- 如果 review workflow 继续演化，再在 `v2` 中处理更大的状态流和协作模型变化

---

## 8. 一句话总结

> 当前 review API 已具备准稳定契约，但仍建议作为 `pre-v1` 管理；  
> 等 DB 主路径、状态机和字段稳定集收口后，再正式宣布 `v1`。
