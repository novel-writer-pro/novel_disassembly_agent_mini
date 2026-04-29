# 最小 Review Workflow 状态机说明

## 1. 目的

这份文档用于说明当前最小 review workflow 原型中：

1. `cluster_status` 的推荐状态流
2. `review_result` 与 `cluster_status` 的推荐组合
3. 哪些状态转换是合理的
4. 哪些状态转换应当避免

---

## 2. 当前涉及的核心字段

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

---

## 3. 推荐状态流

### 标准流

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

解释：

- `open`：问题簇存在，但优先级较低
- `needs_review`：应优先进入人工复核
- `reviewed`：已完成一轮复核，但未必最终关闭
- `escalated`：当前问题需升级处理
- `reopened`：已处理问题再次被打开
- `resolved`：已完成人工复核并给出明确结论

---

## 4. 推荐的状态与结果组合

### A. `open`

适合搭配：

- `review_result = ""`
- `review_result = deferred`

说明：

- 当前没有完成复核
- 或暂时不做明确判断

### B. `needs_review`

适合搭配：

- `review_result = ""`
- `review_result = needs-escalation`
- `review_result = deferred`

说明：

- 仍处于人工复核中
- 或需要升级处理
- 或暂缓判断

### C. `resolved`

适合搭配：

- `review_result = confirmed-issue`
- `review_result = confirmed-benign`
- `review_result = deferred`（不推荐，但可临时容忍）

说明：

- `resolved` 应尽量代表“当前轮人工处理已完成”

当前系统已强约束：

- `resolved` 必须提供非空 `review_result`

### D. `reviewed`

适合搭配：

- `review_result = confirmed-issue`
- `review_result = confirmed-benign`
- `review_result = deferred`

说明：

- 已经过一轮人工复核
- 但不一定代表最终关闭

### E. `escalated`

适合搭配：

- `review_result = needs-escalation`

说明：

- 当前问题需要进入更高层处理

当前系统已强约束：

- `escalated` 必须搭配 `review_result = needs-escalation`

### F. `reopened`

适合搭配：

- `review_result = ""`
- `review_result = deferred`

说明：

- 之前处理过的问题重新被打开

---

## 5. 当前运行时约束

### 已有硬约束

1. `cluster_status = resolved`
   - 必须提供非空 `review_result`

2. `review_result = needs-escalation`
   - 必须提供非空 `review_notes`

3. `cluster_status = escalated`
   - 必须提供 `review_result = needs-escalation`

---

## 6. 当前不推荐的状态组合

### 不推荐组合

1. `resolved + ""`
   - 无明确复核结果

2. `resolved + needs-escalation`
   - 语义上矛盾：既“已完成”又“仍需升级”

3. `open + confirmed-issue`
   - 已确认问题却仍是 open，语义不清

4. `open + confirmed-benign`
   - 已确认无问题却仍是 open，语义不清

5. `escalated + confirmed-benign`
   - 语义矛盾：一边升级，一边确认无问题

---

## 7. 当前建议的人工作业口径

### 当问题未开始处理

- `cluster_status = open`
- `review_result = ""`

### 当问题已进入人工复核

- `cluster_status = needs_review`
- `review_result = ""`

### 当人工确认“确有问题”

- `cluster_status = resolved`
- `review_result = confirmed-issue`

### 当人工确认“无需升级”

- `cluster_status = resolved`
- `review_result = confirmed-benign`

### 当需要更高层处理

- `cluster_status = escalated`
- `review_result = needs-escalation`
- `review_notes` 必填

---

## 8. 后续正式 workflow 可以怎么扩展

如果后续进入正式 workflow 阶段，建议扩展：

- `reviewed`
- `escalated`
- `reopened`

并增加：

- `review_owner`
- `resolved_by`
- `resolved_at`
- `review_notes`
- 状态变更历史

---

## 9. 一句话总结

> 当前最小 review workflow 原型适合采用  
> `open -> needs_review -> resolved`  
> 的简单状态流，并通过 `review_result` 区分“确认有问题 / 确认无问题 / 需升级处理 / 暂缓判断”。
