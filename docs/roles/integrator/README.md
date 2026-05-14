# 接入者 / 前端 / 下游系统入口

**适合场景：**
- 对接后端 API，开发前端页面
- 集成下游系统或 agent
- 了解接口稳定性与版本策略
- 做接入前的 checklist 确认

---

## 推荐阅读顺序

### 第一步：了解接口结构

1. [interface-manifest.md](../../interface-manifest.md) — 稳定接口结构定义（先看这个）
2. [api-current-surface.md](../../api-current-surface.md) — 当前已实现 API surface
3. [examples/](../../examples/) — 所有样例 JSON，对照接口结构理解字段

### 第二步：了解 Review Workflow 接入

4. [tracks/review-workflow/README.md](../../tracks/review-workflow/README.md) — Review Workflow 能力线入口
5. [system-review-consumption-mapping.md](../../system-review-consumption-mapping.md) — 系统消费字段映射
6. [system-review-display-rules.md](../../system-review-display-rules.md) — 系统展示规则建议
7. [system-review-integration-checklist.md](../../system-review-integration-checklist.md) — 最小接入 checklist
8. [system-review-release-checklist.md](../../system-review-release-checklist.md) — 上线 / 回归 checklist

### 第三步：了解全书仿写接入

9. [whole-book-imitation-integration-quickstart.md](../../whole-book-imitation-integration-quickstart.md) — 全书仿写接入快速入门
10. [whole-book-imitation-api-stability-summary.md](../../whole-book-imitation-api-stability-summary.md) — API 稳定字段收口
11. [whole-book-imitation-api-versioning.md](../../whole-book-imitation-api-versioning.md) — API 版本化策略
12. [whole-book-imitation-api-freeze-readiness.md](../../whole-book-imitation-api-freeze-readiness.md) — API 冻结就绪判断
13. [whole-book-imitation-provider-recovery-checklist.md](../../whole-book-imitation-provider-recovery-checklist.md) — Provider 恢复 checklist
14. [whole-book-imitation-docs-index.md](../../whole-book-imitation-docs-index.md) — 全书仿写文档索引
15. [whole-book-imitation-freeze-evidence-20260503.md](../../whole-book-imitation-freeze-evidence-20260503.md) — 冻结证据
16. [whole-book-imitation-readiness.sample.json](../../examples/whole-book-imitation-readiness.sample.json) — 就绪状态样例
17. [whole-book-imitation-sample-coverage-matrix.md](../../whole-book-imitation-sample-coverage-matrix.md) — 样例覆盖矩阵
18. [whole-book-imitation-handoff-brief.md](../../whole-book-imitation-handoff-brief.md) — 全书仿写交接说明

### 第四步：了解 Review API 稳定性

15. [review-workflow-api.md](../../review-workflow-api.md) — Review Workflow API 说明
16. [review-api-stability-summary.md](../../review-api-stability-summary.md) — Review API 稳定字段收口
17. [review-workflow-api-versioning.md](../../review-workflow-api-versioning.md) — Review API 版本化策略
18. [review-workflow-api-freeze-readiness.md](../../review-workflow-api-freeze-readiness.md) — Review API 冻结就绪判断

---

## 关键样例文件速查

| 场景 | 样例文件 |
|------|---------|
| 章节 bundle | [chapter-bundle.sample.json](../../examples/chapter-bundle.sample.json) |
| 分支 bundle | [branch-bundle.sample.json](../../examples/branch-bundle.sample.json) |
| 章节 QA context | [chapter-qa-context.sample.json](../../examples/chapter-qa-context.sample.json) |
| 分支 QA context | [branch-qa-context.sample.json](../../examples/branch-qa-context.sample.json) |
| 全书仿写请求 | [whole-book-imitation-run.request.sample.json](../../examples/whole-book-imitation-run.request.sample.json) |
| 全书仿写响应 | [whole-book-imitation-run.sample.json](../../examples/whole-book-imitation-run.sample.json) |
| Provider 计费错误 | [whole-book-imitation-run.error.provider-billing.sample.json](../../examples/whole-book-imitation-run.error.provider-billing.sample.json) |
| Eval governance bundle | [eval-governance-cross-lane-bundle.sample.json](../../examples/eval-governance-cross-lane-bundle.sample.json) |

---

## 关键文档速查

| 问题 | 文档 |
|------|------|
| 接口字段有哪些？ | [interface-manifest](../../interface-manifest.md) |
| 当前 API 实现了什么？ | [api-current-surface](../../api-current-surface.md) |
| 哪些字段是稳定的？ | [review-api-stability-summary](../../review-api-stability-summary.md) |
| 接入前要确认什么？ | [system-review-integration-checklist](../../system-review-integration-checklist.md) |
| 全书仿写怎么接？ | [whole-book-imitation-integration-quickstart](../../whole-book-imitation-integration-quickstart.md) |

---

返回 [角色导航](../README.md) | [文档中心](../../README.md)
