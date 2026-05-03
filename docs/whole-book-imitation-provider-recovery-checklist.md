# Whole-Book Imitation Provider Recovery Checklist

## 1. 适用场景

当上游 provider 的配额/计费/网关问题恢复后，用这份清单快速补齐成功的 provider-backed freeze evidence。

---

## 2. 第一步：先查 readiness

```bash
novel-analyzer show-whole-book-imitation-readiness \
  --branch-id 62e636f0-c901-4167-aa1c-aff3da9c83ef \
  --database-url "postgresql+psycopg://d2:d2pass@127.0.0.1:5432/novel_analyzer"
```

至少确认：
- `provider.api_key_present = true`
- `provider.provider_health.last_status` 不再持续 degraded
- `branch_candidate.chapter_analysis_count >= 2`
- `branch_candidate.fact_record_count > 0`

---

## 3. 第二步：重跑 whole-book execute

```bash
novel-analyzer export-whole-book-imitation-run \
  62e636f0-c901-4167-aa1c-aff3da9c83ef \
  "freeze-evidence" \
  "示例小说-fresh10-db-v2" \
  "示例小说-fresh10-db-v2-仿写评估" \
  /tmp/whole-book-provider-run.success.json \
  "2:延续前文资源铺垫与关系推进" \
  "3:延续主角获得功法后的行动线并保持克制成长节奏" \
  --execute \
  --max-rounds 1 \
  --use-llm \
  --database-url "postgresql+psycopg://d2:d2pass@127.0.0.1:5432/novel_analyzer"
```

---

## 4. 第三步：核对成功输出

重点核对：
- `contract_version`
- `stable_contract_version`
- `execution_mode = sandbox_execute`
- `policy_summary.next_stage_focus`
- `dashboard_summary.book_handoff_summary`
- `executed_steps[*].overall_score`
- `executed_steps[*].overall_risk_level`

---

## 5. 第四步：补 freeze evidence

建议把成功样本中的以下信息摘录回文档：
- 使用 branch
- 使用模型
- 章节范围
- stop reason
- top priority chapters
- next stage focus
- 是否仍存在中高风险

并更新：
- `docs/whole-book-imitation-freeze-evidence-20260503.md`
- `docs/whole-book-imitation-api-freeze-readiness.md`

---

## 6. 一句话

> provider 恢复后，先 readiness，再 execute，再把成功 JSON 摘录回 freeze evidence。
