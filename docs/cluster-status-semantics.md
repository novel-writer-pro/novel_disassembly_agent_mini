# 问题簇状态语义说明

## 1. 目的

这份文档说明当前 `review_candidate_clusters[].cluster_status` 的语义。

当前它还不是一个可回写的 workflow 字段，而是：

> **运行时导出层的最小状态语义**

用于：

- 报告排序
- 人工优先级提示
- 为未来 review workflow 留扩展入口

---

## 2. 当前支持的状态

### `needs_review`

含义：

- 当前问题簇应优先进入人工复核

当前触发条件（启发式）：

- `review_priority == P1`
- 或 `chapter_count >= 3`
- 或 `max_confidence >= 0.5`

### `open`

含义：

- 当前问题簇存在，但紧急程度较低

当前触发条件：

- 不满足 `needs_review`

### `reviewed`

含义：

- 已完成一轮人工复核，但未必最终关闭

### `escalated`

含义：

- 当前问题需要升级处理

### `reopened`

含义：

- 之前处理过的问题再次被打开

### `resolved`

含义：

- 预留给未来 review workflow 的闭环状态

当前说明：

- 现阶段仅作为语义预留
- 当前运行时不会自动进入 `resolved`
- 当前最小写回约束：
  - 如果写成 `resolved`，必须同时提供非空 `review_result`
  - 如果 `review_result=needs-escalation`，必须同时提供非空 `review_notes`
  - 如果写成 `escalated`，必须同时提供 `review_result=needs-escalation`

---

## 3. 当前边界

需要明确：

1. `cluster_status` 目前是**导出时推导**，不是持久化 review 状态。
2. 它不代表人工已经处理，只代表系统建议优先级层次。
3. 当前已补上**最小写回原型**：
   - 可通过运行时 review registry 覆盖导出层的 `cluster_status`
   - 当前还可附带：
     - `review_notes`
     - `review_owner`
     - `resolved_at`
     - `review_result`
   - 当前结论层还会基于问题簇状态生成：
     - `review_progress_note`
   - 但这还不是完整 workflow
4. 后续如果要做 review workflow，应该把 `resolved / reviewed / open / escalated / reopened` 等状态真正落到可回写对象里。

---

## 4. 当前 `review_result` 推荐取值

当前建议只使用以下有限集合：

- `confirmed-issue`
- `confirmed-benign`
- `needs-escalation`
- `deferred`

空字符串表示：

- 尚未给出明确 review result

这样做的目的，是避免不同使用者写出风格不一致的自由文本值。

---

## 5. 后续扩展建议

未来如果进入 review workflow 阶段，建议：

1. `cluster_status` 从 runtime heuristic 升级为持久化字段
2. 增加：
   - `review_owner`
   - `review_notes`
   - `resolved_by`
   - `resolved_at`

---

## 6. 一句话总结

> 当前 `cluster_status` 是“最小可扩展状态语义入口”，  
> 用于当前导出层排序和提示，也为未来 review workflow 留好挂点。

关联文档：

- `minimal-review-workflow-guide.md`
- `minimal-review-workflow-state-machine.md`
