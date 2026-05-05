# Whole-Book Imitation Integration Quickstart

## 1. 最短接入路径

如果你是 system / agentOS / orchestration 接入方，建议按这个顺序：

1. 先看 `apps/api/README.md`
2. 再看 `docs/interface-manifest.md`
3. 再看下面四个样例：
   - `docs/examples/whole-book-imitation-run.request.sample.json`
   - `docs/examples/whole-book-imitation-run.sample.json`
   - `docs/examples/whole-book-imitation-run.error.provider-billing.sample.json`
   - `docs/examples/whole-book-imitation-readiness.sample.json`

---

## 2. 先做 readiness 检查

推荐先调用：

```bash
curl "http://127.0.0.1:8000/api/whole-book-imitation-readiness?branch_id=<branch_id>&database_url=<database_url>"
```

重点看：
- `provider.api_key_present`
- `provider.provider_health.last_status`
- `branch_candidate.chapter_analysis_count`
- `branch_candidate.fact_record_count`

如果：
- `api_key_present=false`
- 或 `last_status=degraded`
- 或 `chapter_analysis_count < 2`

则不建议直接发 whole-book execute。

---

## 3. 发起 whole-book run

最小 POST 示例：

```bash
curl -X POST "http://127.0.0.1:8000/api/whole-book-imitation-run" \
  -H "Content-Type: application/json" \
  -d @docs/examples/whole-book-imitation-run.request.sample.json
```

当前同一个 endpoint 既可以：
- dry-run queue
- sandbox execute

通过请求体里的 `execute` 字段区分。

---

## 4. 成功时看什么

优先消费：
- `contract_version`
- `stable_contract_version`
- `execution_mode`
- `policy_summary.next_stage_focus`
- `dashboard_summary.book_handoff_summary`
- `dashboard_summary.highest_priority_chapters`

如果要做任务分派：
- 先看 `book_handoff_summary.top_repair_recommendations`

如果要做章节回看：
- 先看 `highest_priority_chapters`

---

## 5. 失败时看什么

失败时优先消费：
- `error_code`
- `retryable`
- `upstream_status`
- `error_type`

当前最重要的错误码：
- `provider_billing_limited`
- `provider_bad_gateway`
- `provider_timeout`

建议策略：
- `provider_billing_limited` → 不自动重试，先处理配额/计费
- `provider_bad_gateway` → 可重试
- `provider_timeout` → 可重试

---

## 6. 当前版本判断

当前推荐按：
- `contract_version = whole-book-imitation.v1`
- `stable_contract_version = whole-book-imitation-pre-v1`

也就是说：
- contract 家族已经固定
- 但仍按 pre-v1 稳定级别管理

---

## 7. 一句话接入建议

> 先 readiness，再 run；成功看 handoff summary，失败看 error_code / retryable。
