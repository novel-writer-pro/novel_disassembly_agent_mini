# Whole-Book Imitation Sample Coverage Matrix

## 1. 当前样例资产

| 样例 | 作用 | 当前状态 |
|---|---|---|
| `docs/examples/whole-book-imitation-run.request.sample.json` | API 请求体样例 | 已有 executable regression |
| `docs/examples/whole-book-imitation-run.sample.json` | 成功响应样例 | 已有 executable stable-field regression |
| `docs/examples/whole-book-imitation-run.error.provider-billing.sample.json` | 错误响应样例 | 已有 executable regression |
| `docs/examples/whole-book-imitation-readiness.sample.json` | readiness 响应样例 | 已有 executable regression |

---

## 2. 当前回归覆盖

已落地的关键回归：

- request sample → `test_whole_book_imitation_run_request_sample_is_executable`
- success sample → `test_whole_book_imitation_success_sample_matches_live_stable_fields`
- readiness sample → `test_whole_book_imitation_readiness_sample_is_executable`
- error sample → `test_whole_book_imitation_error_sample_matches_billing_error_shape`
- success contract → `test_whole_book_imitation_run_endpoint_returns_contract_payload`

---

## 3. 一句话结论

> 当前 whole-book imitation 的 request / readiness / error 三类样例，已经都不是“展示样例”，而是“可执行合同样例”。
