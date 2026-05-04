# API Contract / Web Backend 契约（Future Target）

> 本文件描述未来 `apps/api` 的目标契约，不代表 Phase 1 已全部实现。
> 当前已经实现并可调用的 API surface 请参考 `docs/api-current-surface.md`。

## 1. 总体约束
- 首期采用 HTTP + polling
- 不做实时推送必选项
- 不做首期鉴权/多用户
- API 只能依赖 `novel_analyzer/application/*`
- Web 首期采用 **multipart/form-data 直接上传文本文件**，不做二段式上传
- export endpoints 首期统一返回 `{download_ref, content_type}`

## 2. Endpoints

### 2.1 POST /novels/import
创建 novel / manifest / run / branch，并按 profile 接受自动推进请求。

**Transport**
- `multipart/form-data`
- fields:
  - `file`: 小说文本文件（必填）
  - `title`: 标题（可选）
  - `pipeline_profile`: `manual | auto-lite | auto-full`
  - `idempotency_key`: 可选，**仅用于客户端请求去重审计；不覆盖服务端 source-hash 幂等规则**
  - `force_new_run`: `true | false`（默认 `false`）

**Target response: 202 Accepted**
```json
{
  "novel_id": "...",
  "manifest_id": "...",
  "run_id": "...",
  "branch_id": "...",
  "pipeline_profile": "auto-lite",
  "pipeline_state": "accepted",
  "existing": false
}
```

**Target response: 200 OK（幂等复用）**
```json
{
  "novel_id": "...",
  "manifest_id": "...",
  "run_id": "...",
  "branch_id": "...",
  "pipeline_profile": "auto-lite",
  "pipeline_state": "auto_running",
  "existing": true
}
```

**Target response: 500 Setup Partial Failure**
```json
{
  "novel_id": "...",
  "manifest_id": "...",
  "run_id": null,
  "branch_id": null,
  "pipeline_state": "failed_terminal",
  "setup_status": "setup_incomplete",
  "error_type": "RunCreationError",
  "message": "run creation failed"
}
```

**Target idempotency rule**
- 以 `source_hash + normalized_title + pipeline_profile` 作为服务端幂等判定主键
- `idempotency_key` 仅用于请求级去重审计/重放保护，不改变主判定规则
- 若提交内容相同且当前存在未归档 run，且 `force_new_run=false`：**复用已有 run/branch，返回 200 OK + existing=true**
- 其余情况：新建并返回 `202 Accepted`

### 2.2 POST /runs/{run_id}/start
为 `manual` / `ready` 状态显式启动 pipeline。

**Request**
```json
{
  "branch_id": "...",
  "pipeline_profile": "auto-lite"
}
```

**Response**
```json
{
  "run_id": "...",
  "branch_id": "...",
  "pipeline_state": "accepted",
  "message": "pipeline start accepted"
}
```

### 2.3 GET /runs/{run_id}
返回 run 级快照、pipeline 状态、下一动作建议。

**Response schema**
```json
{
  "run_id": "...",
  "branch_id": "...",
  "branch_name": "main",
  "pipeline_state": "auto_running",
  "manifest_chapter_count": 120,
  "completed_chapters": 3,
  "failed_jobs": 0,
  "running_jobs": 1,
  "next_chapter": 4,
  "allowed_actions": ["refresh"],
  "warnings": [],
  "setup_status": "ok"
}
```

### 2.4 GET /branches/{branch_id}
返回 branch 级章节索引、失败章摘要、允许动作。

**Response schema**
```json
{
  "branch_id": "...",
  "pipeline_state": "needs_recovery",
  "allowed_actions": ["retry-failed", "retry-chapter", "clear-running", "repair"],
  "chapter_rows": [
    {
      "chapter_index": 1,
      "title": "第1章",
      "job_status": "validated",
      "has_artifact": true,
      "has_retrieval": true,
      "hook_score": 0.82,
      "needs_human_review": false
    }
  ],
  "failed_summary": [
    {
      "chapter_index": 4,
      "error": "..."
    }
  ]
}
```

### 2.5 GET /branches/{branch_id}/exports/branch-bundle
### 2.6 GET /branches/{branch_id}/exports/branch-qa-context
### 2.7 GET /branches/{branch_id}/exports/branch-report
统一返回：
```json
{
  "download_ref": "/downloads/...",
  "content_type": "application/json"
}
```
`branch-report` 的 `content_type` 为 `text/markdown`。

**Operational smoke path**

对于真实 PostgreSQL 运行时，当前推荐把下面三步视为最小 smoke chain：

1. `init-db`
2. `db-capabilities`
3. `export-branch-report`

它们共同验证：
- Alembic schema 已升级
- cluster-review 相关缺列已被发现或修复
- branch 级 Markdown export 仍可在真实 sample branch 上成功导出

参考样例：
- `docs/examples/sample-branch-report.post-migration-20260504.sample.md`

### 2.8 POST /branches/{branch_id}/recovery/retry-chapter
### 2.9 POST /branches/{branch_id}/recovery/retry-failed
### 2.10 POST /branches/{branch_id}/recovery/clear-running
### 2.11 POST /branches/{branch_id}/recovery/repair
恢复类接口，只能在允许状态下执行。

**Recovery response schema**
```json
{
  "branch_id": "...",
  "accepted_action": "retry-failed",
  "pipeline_state": "auto_running",
  "message": "retry accepted"
}
```

### 2.12 GET /branches/{branch_id}/review-clusters
返回当前 branch 的问题簇列表。

**Query filters (optional)**
- `cluster_status`
- `review_owner`
- `review_result`

**Response schema**
```json
{
  "items": [
    {
      "cluster_key": "...",
      "cluster_title": "人物连续性复核簇",
      "checker_names": ["character_ooc"],
      "risk_types": ["human_review_candidate"],
      "review_priority": "P2",
      "cluster_status": "needs_review",
      "review_result": "deferred",
      "review_result_label": "暂缓判断"
    }
  ]
}
```

### 2.13 GET /branches/{branch_id}/review-clusters/{cluster_key}/history
返回某个问题簇的 review history。

**Response schema**
```json
{
  "review_storage_mode": "db",
  "branch_id": "branch-uuid",
  "cluster_key": "character_ooc|::|motivation_shift",
  "count": 1,
  "applied_filters": {
    "event_type": "",
    "review_owner": "editor-a",
    "review_result": "confirmed-benign",
    "limit": 1
  },
  "items": [
    {
      "event_id": "event-uuid",
      "previous_cluster_status": "needs_review",
      "previous_review_result": "deferred",
      "previous_review_notes": "...",
      "previous_review_owner": "editor-b",
      "previous_resolved_at": "",
      "cluster_status": "reviewed",
      "review_result": "confirmed-benign",
      "review_notes": "...",
      "review_owner": "editor-a",
      "resolved_at": "...",
      "event_type": "status_update"
    }
  ]
}
```

### 2.14 GET /branches/{branch_id}/review-clusters/summary
返回当前 branch 的问题簇汇总统计。

**Query filters (optional)**
- `cluster_status`
- `review_owner`
- `review_result`

**Response schema**
```json
{
  "review_storage_mode": "db",
  "cluster_count": 1,
  "history_event_count": 2,
  "latest_review_at": "2026-04-29T03:00:00Z",
  "latest_review_owner": "editor-a",
  "latest_review_result": "confirmed-benign",
  "latest_review_result_label": "确认无问题",
  "by_priority": {"P2": 1},
  "by_pattern": {"持续型问题": 1},
  "by_status": {"reviewed": 1},
  "by_result": {"confirmed-benign": 1},
  "by_owner": {"editor-a": 1}
}
```

### 2.15 POST /branches/{branch_id}/review-clusters/{cluster_key}
更新某个问题簇的当前 review 状态。

**Request**
```json
{
  "cluster_status": "reviewed",
  "review_result": "confirmed-benign",
  "review_notes": "...",
  "review_owner": "editor-a",
  "resolved_at": "2026-04-29T02:00:00Z"
}
```

**Response**
```json
{
  "branch_id": "...",
  "cluster_key": "...",
  "cluster_status": "reviewed",
  "review_result": "confirmed-benign",
  "review_notes": "...",
  "review_owner": "editor-a",
  "resolved_at": "2026-04-29T02:00:00Z"
}
```

**Validation error**
```json
{
  "error": "cluster_status=resolved requires a non-empty review_result"
}
```

## 3. Pipeline state 判定表（Target）

| state | 判定规则 | UI allowed actions |
|---|---|---|
| `accepted` | import 请求已接受，基础实体刚创建，launcher 未开始推进 | refresh |
| `ingesting` | 正在处理上传/导入、manifest 未完成 | refresh |
| `ready` | run/branch 已就绪，未进入自动推进 | start/refresh/export-basic |
| `auto_running` | 存在推进中的章节或 launcher 正在串行推进 | refresh |
| `paused` | 用户/策略主动暂停自动推进 | resume/export/read |
| `needs_recovery` | 存在失败章或僵死 running job，需要恢复动作 | retry-failed / retry-chapter / clear-running / repair / export-readonly |
| `completed` | 所需推进已完成，导出可用 | export / ask / branch-view |
| `failed_terminal` | 非可恢复性失败（配置错误、严重数据错误） | inspect / retry-from-fixed-config |

## 4. auto-full 默认停止条件（已定）
`auto-full` 的默认停止条件顺序：
1. 全书完成
2. 预算上限触发
3. 用户暂停
4. 首个失败触发 `needs_recovery`

## 5. Error responses
- `400`：请求参数错误
- `409`：状态冲突/动作不允许
- `422`：输入校验失败
- `500`：内部执行失败
- `503`：外部依赖不可用（如 LLM / embedding）

错误体：
```json
{
  "error_type": "ValidationError",
  "message": "...",
  "retryable": true
}
```
