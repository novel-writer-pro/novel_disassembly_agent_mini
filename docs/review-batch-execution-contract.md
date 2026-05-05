# Review Batch Execution Contract（草案）

这份文档定义的是**下一阶段执行层 contract**，不是当前已实现 API。

目标：

> 把现有的批量处理建议（`batch_suggestions`）推进成可执行的系统动作入口。

当前状态：

- `review_summary.batch_suggestions` 已实现
- 可用于发现：
  - 哪一批适合升级
  - 哪一批适合人工复核
  - 哪一批适合交接催办
  - 哪一批适合关闭 / 归档

这份文档回答的是：

> 当系统真正开始执行这些批量动作时，请求和响应应该长什么样。

---

## 1. 设计原则

1. **建议与执行分离**
   - `batch_suggestions` 负责“建议”
   - execution contract 负责“执行”

2. **先批次确认，再单簇写回**
   - 系统先确认要执行哪一批
   - 再逐个 cluster 写回状态 / owner / notes

3. **执行必须可审计**
   - 每次批量动作都应保留：
     - 谁触发的
     - 作用到哪些 cluster
     - 成功 / 失败分别多少

4. **失败允许部分成功**
   - 一个 batch 中可以部分成功、部分失败
   - 不要求全有或全无

---

## 2. 推荐的批量执行动作类型

建议先支持 4 类：

- `batch_review_assign`
- `batch_escalate`
- `batch_close`
- `batch_archive`

说明：

### `batch_review_assign`
- 用于把一批 `needs_review` / `assignment_queue` 的簇统一指派给 owner

### `batch_escalate`
- 用于把一批升级候选统一打到更高等级处理

### `batch_close`
- 用于把 `close_ready_gate=true` 的簇统一关闭

### `batch_archive`
- 用于把已关闭簇统一归档

---

## 3. 推荐请求结构

### `POST /api/review-batch-execute`

请求体建议：

```json
{
  "branch_id": "branch-001",
  "action": "batch_close",
  "hint_code": "batch_close_ready_candidates",
  "group_strategy": "by_owner",
  "group_key": "editor-a",
  "cluster_keys": [
    "character_ooc|::|human_review_candidate"
  ],
  "review_owner": "editor-a",
  "review_actor": "review-bot",
  "review_result": "confirmed-benign",
  "review_notes": "批量关闭：已满足关闭条件",
  "resolved_at": "2026-04-30T12:00:00Z",
  "dry_run": false
}
```

---

## 4. 推荐响应结构

```json
{
  "branch_id": "branch-001",
  "action": "batch_close",
  "hint_code": "batch_close_ready_candidates",
  "target_count": 3,
  "success_count": 2,
  "failed_count": 1,
  "skipped_count": 1,
  "dry_run": false,
  "successes": [
    {
      "cluster_key": "character_ooc|::|human_review_candidate",
      "status": "ok",
      "cluster_status": "resolved",
      "review_result": "confirmed-benign"
    },
  ],
  "failed": [
    {
      "cluster_key": "timeline_consistency|::|timeline_review_candidate",
      "status": "failed",
      "error": "cluster not close-ready"
    }
  ],
  "skipped": [
    {
      "cluster_key": "plot_logic_consistency|::|logic_review_candidate",
      "reason": "not_in_batch_suggestion"
    }
  ]
}
```

说明：

- `successes`
  - 已成功执行写回的 cluster 列表
- `failed`
  - 执行时写回失败的 cluster 列表
- `skipped`
  - 本次请求传入但未纳入当前 batch suggestion 的 cluster 列表
- `skipped_count`
  - 被跳过的 cluster 数量

当前已实现返回中还会带：

- `execution_id`
  - 本次批量执行 / 预演的唯一标识
- `preview`
  - 本次命中的 cluster 预览，用于前端确认或 agentOS 预演

---

## 5. 执行前校验建议

### `batch_review_assign`
- cluster 必须属于：
  - `needs_review`
  - 或 `assignment_queue`

### `batch_escalate`
- cluster 必须属于：
  - `escalation_queue`
  - 或 review_result 已判定为 `needs-escalation`

### `batch_close`
- cluster 必须满足：
  - `close_ready_gate = true`

### `batch_archive`
- cluster 必须满足：
  - `cluster_status = resolved`

---

## 6. dry-run 建议

建议所有批量执行动作都支持：

- `dry_run = true`

作用：

- 只返回哪些 cluster 将被影响
- 不真正写库
- dry-run 也建议返回：
  - `preview`
  - `target_count`
  - `skipped_count`
  - `skipped`
  - `execution_id`

这对前端确认弹窗、agentOS 预演都很有用。

---

## 6.1 当前已落地的执行动作

截至当前阶段，`/api/review-batch-execute` 已经落地支持：

- `batch_review_assign`
- `batch_escalate`
- `batch_close`
- `batch_archive`

当前能力特征：

- 支持 `dry_run`
- 支持 `hint_code + group_strategy + group_key` 校验
- `batch_close` 严格校验 `close_ready_gate = true`
- `batch_archive` 允许对已关闭但未满足 close-ready 的簇做归档类写回
- 已返回分离的：
  - `successes`
  - `failed`
  - `skipped`

因此，这份文档现在既可视为下一阶段 contract 草案，也可视为当前最小执行层的描述基础。

---

## 6.2 当前已落地的批量执行历史

当前系统已经落地：

- `GET /api/review-batch-history?branch_id=...`

当前返回重点字段：

- `branch_id`
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
- `items[*].successes`
- `items[*].failed`
- `items[*].skipped`

当前说明：

- 这是 **runtime file-backed** 的最小审计历史
- 适合当前阶段做：
  - 前端执行回执
  - agentOS 执行回执
  - 批量执行历史抽屉
- 后续如果进入更强协作 / 更强审计阶段，建议升级为正式 DB 对象

---

## 7. 与当前系统能力的衔接

当前已具备：

- `batch_suggestions[*].hint_code`
- `group_strategy`
- `group_key`
- `cluster_keys`
- `suggested_cluster_order`

因此 execution contract 的输入已经有上游来源，不需要重新发明。

也就是说：

> 当前 suggestion 层已经具备执行层所需的大部分定位信息。

---

## 8. 最小落地顺序

推荐：

### Phase A
- 先做 `batch_review_assign`
- 先做 `dry_run`

### Phase B
- 做 `batch_escalate`

### Phase C
- 做 `batch_close`
- 严格依赖 `close_ready_gate`

### Phase D
- 做 `batch_archive`

---

## 9. 一句话总结

> 当前系统已经能产出“批量处理建议”，  
> 下一阶段应把这些建议收口为统一的 batch execution contract，并先从 `dry_run + assign + escalate` 开始落地。
