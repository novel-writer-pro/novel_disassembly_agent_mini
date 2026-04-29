# Review Workflow 第二阶段设计稿

## 1. 目标

当前系统已经具备：

- `review_candidate_clusters`
- `cluster_status`
- `review_notes`
- `review_owner`
- `resolved_at`
- `review_result`
- `review_progress_note`

以及最小写回原型。

补充说明：

- 当前原型已开始优先走 **DB-backed review object**
- runtime file registry 仅保留为兼容 fallback

第二阶段的目标不是再证明“能不能写回”，而是把这套能力正式化为：

> **可管理、可追踪、可被多人协作使用的 review workflow**

---

## 2. 当前原型能力

### 已经具备

1. 问题簇对象
2. 状态字段
3. review result 字段
4. 最小约束
5. CLI 写回入口
6. bundle / report 展示

### 当前限制

1. 仍然是运行时 registry
2. 还不是数据库正式对象
3. 没有变更历史
4. 没有 reviewer 协作语义
5. 没有 UI 入口

---

## 2.1 当前状态分层（已设计 / 已实现 / 未实现）

### 已设计且已实现

- DB-backed review object
- DB-backed review history
- CLI 写回 / 读取
- API 读 cluster / history / update
- bundle / report 展示当前 review 元数据
- `review_progress_note`
- `review_result_note`
- `review_owner_note`
- `latest_review_note`

### 已设计但尚未完整实现

- 更完整的 reviewer 审计链
- 更细粒度状态流（完整 reviewer 协同语义）
- API/CLI 的完整 history 运营使用方式
- review workflow 的正式 UI

### 当前明确未实现

- 多人并发协作控制
- 权限模型
- review owner 指派流程
- review SLA / 催办 / 通知

---

## 3. 第二阶段推荐目标

### 目标 A：Review Object 正式化

把 cluster 的 review 状态从 runtime 覆盖对象，升级为正式 review object。

建议字段：

- `branch_id`
- `cluster_key`
- `cluster_status`
- `review_result`
- `review_notes`
- `review_owner`
- `resolved_by`
- `resolved_at`
- `updated_at`

### 目标 B：状态流正式化

建议状态：

- `open`
- `needs_review`
- `reviewed`
- `escalated`
- `reopened`
- `resolved`

### 目标 C：审计链

建议补：

- 状态变更历史
- 谁改的
- 为什么改

---

## 4. 推荐状态流

```text
open
  ↓
needs_review
  ├─ reviewed
  ├─ escalated
  └─ reopened
       ↓
    needs_review
  ↓
resolved
```

说明：

- `reviewed`：已看过但未关闭
- `escalated`：需要上升处理
- `reopened`：之前处理过，但重新打开
- `resolved`：当前问题完成关闭

---

## 5. 推荐约束

### 必须保留

1. `resolved` 必须有非空 `review_result`
2. `needs-escalation` 必须有非空 `review_notes`
3. `escalated` 必须对应 `review_result=needs-escalation`

### 后续可增加

4. `resolved` 必须有 `resolved_at`
5. `resolved` 建议有 `resolved_by`
6. `reviewed` 建议有 `review_owner`

---

## 6. 数据层建议

### 当前原型

- runtime file registry

### 第二阶段建议

引入正式 review state storage：

- 首选：数据库表
- 次选：独立 review state JSON + 版本历史

优先建议数据库化的原因：

1. 更适合多角色协作
2. 更适合历史追踪
3. 更适合后续 API / UI 接入

---

## 7. API / CLI 建议

### CLI

继续保留：

- `set-cluster-status`
- `show-cluster-status`

并建议后续补：

- `list-cluster-reviews`
- `show-cluster-review-history`

### API

建议后续补：

- `GET /api/review-clusters`
- `POST /api/review-clusters/update`
- `GET /api/review-clusters/history`

---

## 8. Report / Bundle 继续保留的字段

第二阶段不建议推翻当前输出骨架。

建议继续保留：

- `cluster_status`
- `review_result`
- `review_result_label`
- `review_notes`
- `review_owner`
- `resolved_at`
- `review_progress_note`
- `review_result_note`

---

## 9. 推荐推进顺序

### 第一步

正式定义 review object schema

### 第二步

把 runtime registry 升级成持久化 state

### 第三步

补状态历史

### 第四步

补 API / UI

---

## 10. 一句话总结

> 第二阶段的 review workflow 重点不是再补字段，而是把当前最小原型升级成正式的 review object、状态流和审计链。
