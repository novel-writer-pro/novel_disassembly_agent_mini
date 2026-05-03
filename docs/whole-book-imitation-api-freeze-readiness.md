# Whole-Book Imitation API 冻结就绪判断

## 1. 当前结论

当前 whole-book imitation API 更准确的状态是：

> **pre-v1，已具备 system-contract-ready 能力，provider 当前可用且已拿到 provider-backed 成功样本，但尚未正式宣布 stable freeze。**

也就是说：
- 系统可以正式接入
- 版本字段已经显式存在
- 合同、样例、CLI/export/API 已经对齐
- 但还不建议立即宣称 fully stable v1

---

## 2. 为什么说“已接近可冻结”

当前已经具备：

### A. 实现层
- whole-book service report
- CLI run
- CLI export
- API read/execute surface

### B. 契约层
- `interface-manifest.md`
- `whole-book-imitation-api-stability-summary.md`
- `whole-book-imitation-api-versioning.md`

### C. 样例层
- `docs/examples/whole-book-imitation-run.sample.json`

### D. 测试层
- service contract 回归
- CLI export 回归
- API happy-path 回归
- 文档/样例一致性回归

---

## 3. 为什么还不建议现在就 freeze

因为当前仍有几类信号更像“演进中能力”：

1. provider-backed 长链回归还不够多
2. `book_handoff_summary` 的真实下游消费证据还不足
3. 增强字段范围仍可能继续收口
4. orchestration 语义未来仍可能再补更系统化的调度字段

因此：

> 已经适合接入，但还不适合承诺“后续几乎不会再动”。

补充：2026-05-03 首轮真实 provider-backed whole-book execute 尝试，主链已成功触达 provider，但被上游返回：

- `403 Forbidden`
- `billing_error`
- `daily usage limit exceeded`

对应证据见：
- `docs/whole-book-imitation-freeze-evidence-20260503.md`

后续 2026-05-04 已补到一轮成功的 provider-backed 样本，见：

- `docs/examples/whole-book-imitation-run.provider-success-20260504.sample.json`

同时，最新 readiness 输出已经反映：

- `provider_health.last_status = ok`
- `success_events = 7`
- `last_error = null`

因此当前 freeze 未完成的原因，已经不再是“没有成功样本”或“provider 当前不可用”，而更接近：

> **虽然已有成功 provider-backed evidence，但 stable freeze 的治理口径还未正式收束。**

---

## 4. 进入正式 stable freeze 的建议条件

建议至少满足：

1. `stable_contract_version` 升级策略明确
2. provider-backed sandbox run 完成更多真实回归
3. 稳定字段集合连续 2 个迭代不变
4. 至少一类真实系统消费者完成接入验证
5. 增强字段和稳定字段边界不再移动

---

## 5. 当前推荐口径

### 可以说
- pre-v1
- system-contract-ready
- 可接入 / 可联调 / 可系统消费

### 不建议说
- fully stable v1
- 已正式冻结
- 后续字段不会再动

## 5.1 建议先跑的 readiness 命令

在真正重跑 provider-backed evidence 之前，建议先执行：

```bash
novel-analyzer show-whole-book-imitation-readiness --branch-id <branch_id>
```

它会结构化输出：
- 当前 whole-book contract 版本标记
- 数据库目标
- provider 配置是否存在
- 最近 provider health 状态
- 当前 branch 是否具备足够的 chapter_analysis / fact_records

---

## 6. 一句话总结

> 当前 whole-book imitation API 已经达到“可正式系统接入”的水准，但更稳妥的口径仍然是 `pre-v1`，下一步重点应放在真实 provider 回归与 freeze readiness 证据上。
