# Review Workflow API 冻结就绪判断

## 1. 当前结论

当前 review workflow API 更准确的状态是：

> **Phase 2 pre-v1，已接近可冻结，但尚未达到正式 freeze 条件。**

也就是说：

- 已经具备可接入能力
- 已经具备契约、样例、测试、版本化策略
- 但仍不建议现在就宣布“正式冻结”

---

## 2. 为什么说“接近可冻结”

当前已经具备：

### A. 实现层

- DB-backed review object
- DB-backed review history
- API 可读写
- summary API 可读

### B. 契约层

- `review-workflow-api.md`
- `api-contract.md`
- `interface-manifest.md`
- `review-api-stability-summary.md`
- `review-workflow-api-versioning.md`

### C. 样例层

- request / response / error 样例
- stable sample
- summary stable sample
- full sample（pre-v1 / phase-2 扩展样例）

补充说明：
- 当前 full sample 已包含 `phase2_focus_top`、`by_phase2_focus`、`prioritize_phase2_human_review`、`phase2_risk_requires_human_confirmation`。
- 当前 stable sample 仍刻意保持稳定字段子集，不强制包含这些 phase-2 扩展字段。

### D. 测试层

- `test_api_main.py`
- 相关回归已稳定通过

---

## 3. 为什么还不建议立即 freeze

因为当前仍有几项更像第二阶段中的“演进中能力”：

1. review history 仍在持续增强
2. review owner / 指派语义还没正式化
3. DB-only 仍未切换完成
4. state machine 仍可能继续收敛
5. phase-2 扩展字段与 stable sample 之间仍保留刻意差异，尚未进入统一冻结口径

这意味着：

> 接口已可接，但还不适合完全锁死成“不会再调整”的状态。

---

## 4. 当前建议判断

### 可以说

- “准稳定接口”
- “Phase 2 pre-v1”
- “可试接 / 可联调 / 可逐步上线”

### 不建议说

- “已经正式 v1 冻结”
- “后续字段不会再变”

---

## 5. 进入正式 freeze 的建议条件

建议至少满足：

1. DB-only 路径明确
2. history / owner / result / summary 语义不再继续变化
3. API 稳定字段清单连续 2 个迭代不变
4. 接入方已完成一轮实际对接验证
5. full sample 与 stable sample 的字段边界不再继续变化，或已显式冻结到版本文档

---

## 6. 当前推荐做法

当前最合理的策略是：

- 把 review workflow API 按 **pre-v1** 管理
- 允许在实验字段层继续演化
- 对稳定字段保持克制，不轻易破坏

---

## 7. 一句话总结

> 当前 review workflow API 已经很接近正式冻结，但更合理的口径仍然是 `pre-v1`；  
> 等 DB-only 路径、状态机和稳定字段集都再收口一轮后，再正式宣布 freeze 更稳。
