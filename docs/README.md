# Docs Index / 文档导航

这份索引页把文档按 **阅读顺序** 和 **角色类型** 整理出来。

---

## 快速分流入口（新目录）

### 按角色
- [`./roles/README.md`](./roles/README.md)
- [`./roles/product/README.md`](./roles/product/README.md)
- [`./roles/backend/README.md`](./roles/backend/README.md)
- [`./roles/integrator/README.md`](./roles/integrator/README.md)
- [`./roles/maintainer/README.md`](./roles/maintainer/README.md)
- [`./roles/imitation/README.md`](./roles/imitation/README.md)

### 按能力线 / 主题
- [`./tracks/README.md`](./tracks/README.md)
- [`./tracks/risk-audit/README.md`](./tracks/risk-audit/README.md)
- [`./tracks/review-workflow/README.md`](./tracks/review-workflow/README.md)
- [`./tracks/reader-experience/README.md`](./tracks/reader-experience/README.md)
- [`./tracks/imitation/README.md`](./tracks/imitation/README.md)

### 按架构专题
- [`./architecture/README.md`](./architecture/README.md)
- [`./architecture/risk-audit-semantic-enhancement.md`](./architecture/risk-audit-semantic-enhancement.md)
- [`./architecture/risk-audit-embedding-pgvector-implementation-spec.md`](./architecture/risk-audit-embedding-pgvector-implementation-spec.md)
- [`./architecture/risk-audit-completion-status.md`](./architecture/risk-audit-completion-status.md)
- [`./architecture/chapter-imitation-harness-architecture.md`](./architecture/chapter-imitation-harness-architecture.md)
- [`./risk-audit-production-readiness.md`](./risk-audit-production-readiness.md)

---

## 0. 开发变更记录

- [`../CHANGELOG.md`](../CHANGELOG.md)：后续每次开发更改都需要追加记录
- 约定：每次修复 / 变动都需要同步更新文档、changelog 与 commit 记录

## 1. 使用者（只想直接用系统的人）

### 推荐阅读顺序
1. [`./cli-operations-manual.md`](./cli-operations-manual.md)
2. [`./direct-usage-guide.md`](./direct-usage-guide.md)
3. [`./real-run-checklist.md`](./real-run-checklist.md)
4. [`./review-template.md`](./review-template.md)
5. [`./session-handoff-manual.md`](./session-handoff-manual.md)

### 说明
- 第 1 步：先看怎么跑 CLI
- 第 2 步：再看日常使用细节
- 第 3 步：真实小说试跑前看清单
- 第 4 步：试跑后用模板做复盘

---

## 2. 接入者（前端 / 工具 / 下游 agent）

### 推荐阅读顺序
1. [`./interface-manifest.md`](./interface-manifest.md)
2. [`./api-current-surface.md`](./api-current-surface.md)
3. [`./examples/`](./examples/)
4. [`./system-review-consumption-mapping.md`](./system-review-consumption-mapping.md)
5. [`./system-review-display-rules.md`](./system-review-display-rules.md)
6. [`./system-review-integration-checklist.md`](./system-review-integration-checklist.md)
7. [`./system-review-release-checklist.md`](./system-review-release-checklist.md)
8. [`./real-run-evaluation-1-12.md`](./real-run-evaluation-1-12.md)
9. [`./final-handoff.md`](./final-handoff.md)

### 说明
- 第 1 步：先看稳定接口结构
- 第 2 步：再看当前已实现 API surface
- 第 3 步：再对照样例 JSON
- 第 4 步：看系统消费字段映射
- 第 5 步：看系统展示规则建议
- 第 6 步：看最小接入 checklist
- 第 7 步：看上线 / 回归 checklist
- 第 8 步：看真实试跑结果
- 第 9 步：看整体交付边界与风险

---

## 3. 开发者（继续开发 / 维护 / 接手的人）

### 推荐阅读顺序
1. [`./final-handoff.md`](./final-handoff.md)
2. [`./release-handoff-brief.md`](./release-handoff-brief.md)
3. [`./api-current-surface.md`](./api-current-surface.md)
4. [`./agent-skills-and-embedding.md`](./agent-skills-and-embedding.md)
5. [`./model-eval-template.md`](./model-eval-template.md)
6. [`./review-template.md`](./review-template.md)
7. [`./session-handoff-manual.md`](./session-handoff-manual.md)
8. [`./chapter-imitation-method.md`](./chapter-imitation-method.md)

### 说明
- 第 1 步：先看完整交付说明
- 第 2 步：再看简版交接说明
- 第 3 步：再看当前已实现 API surface
- 第 4 步：看内部 agent / skills / embedding 设计
- 第 5 步：后续换模型时参考评测模板
- 第 6 步：做真实章节复盘时参考记录模板
- 第 8 步：继续做仿写/全书改写链时，直接看仿写方法与 whole-book 输入输出

---

## 4. 文档清单

### 使用类文档
1. [`./cli-operations-manual.md`](./cli-operations-manual.md)
2. [`./direct-usage-guide.md`](./direct-usage-guide.md)
3. [`./real-run-checklist.md`](./real-run-checklist.md)
4. [`./review-template.md`](./review-template.md)
5. [`./session-handoff-manual.md`](./session-handoff-manual.md)
6. [`../apps/web/README.md`](../apps/web/README.md)
7. [`../apps/api/README.md`](../apps/api/README.md)

### 接口类文档
1. [`./interface-manifest.md`](./interface-manifest.md)
2. [`./examples/chapter-bundle.sample.json`](./examples/chapter-bundle.sample.json)
3. [`./examples/branch-bundle.sample.json`](./examples/branch-bundle.sample.json)
4. [`./examples/branch-bundle-review-summary.sample.json`](./examples/branch-bundle-review-summary.sample.json)
5. [`./system-review-consumption-mapping.md`](./system-review-consumption-mapping.md)
6. [`./system-review-display-rules.md`](./system-review-display-rules.md)
7. [`./system-review-integration-checklist.md`](./system-review-integration-checklist.md)
8. [`./system-review-release-checklist.md`](./system-review-release-checklist.md)
9. [`./examples/chapter-qa-context.sample.json`](./examples/chapter-qa-context.sample.json)
10. [`./examples/branch-qa-context.sample.json`](./examples/branch-qa-context.sample.json)
11. [`./examples/whole-book-imitation-run.sample.json`](./examples/whole-book-imitation-run.sample.json)
12. [`./examples/whole-book-imitation-run.request.sample.json`](./examples/whole-book-imitation-run.request.sample.json)
13. [`./examples/whole-book-imitation-run.error.provider-billing.sample.json`](./examples/whole-book-imitation-run.error.provider-billing.sample.json)
14. [`./whole-book-imitation-api-stability-summary.md`](./whole-book-imitation-api-stability-summary.md)
15. [`./whole-book-imitation-api-versioning.md`](./whole-book-imitation-api-versioning.md)
16. [`./whole-book-imitation-api-freeze-readiness.md`](./whole-book-imitation-api-freeze-readiness.md)
17. [`./whole-book-imitation-freeze-evidence-20260503.md`](./whole-book-imitation-freeze-evidence-20260503.md)
18. [`./examples/whole-book-imitation-readiness.sample.json`](./examples/whole-book-imitation-readiness.sample.json)
19. [`./whole-book-imitation-integration-quickstart.md`](./whole-book-imitation-integration-quickstart.md)
20. [`./whole-book-imitation-docs-index.md`](./whole-book-imitation-docs-index.md)
21. [`./whole-book-imitation-provider-recovery-checklist.md`](./whole-book-imitation-provider-recovery-checklist.md)
22. [`./whole-book-imitation-sample-coverage-matrix.md`](./whole-book-imitation-sample-coverage-matrix.md)
23. [`./whole-book-imitation-handoff-brief.md`](./whole-book-imitation-handoff-brief.md)

### 交付与维护类文档
1. [`./final-handoff.md`](./final-handoff.md)
2. [`./release-handoff-brief.md`](./release-handoff-brief.md)
3. [`./real-run-evaluation-1-12.md`](./real-run-evaluation-1-12.md)
4. [`./model-eval-template.md`](./model-eval-template.md)
5. [`./agent-skills-and-embedding.md`](./agent-skills-and-embedding.md)
6. [`./application-seams.md`](./application-seams.md)
7. [`./api-contract.md`](./api-contract.md)
8. [`./storage-lifecycle.md`](./storage-lifecycle.md)

### 风险审查体系文档
1. [`./risk-audit-docs-index.md`](./risk-audit-docs-index.md)
2. [`./risk-audit-system-overview.md`](./risk-audit-system-overview.md)
3. [`./risk-audit-delivery-summary.md`](./risk-audit-delivery-summary.md)
4. [`./architecture/risk-audit-completion-status.md`](./architecture/risk-audit-completion-status.md)
5. [`./risk-audit-capability.md`](./risk-audit-capability.md)
6. [`./risk-audit-runtime-architecture.md`](./risk-audit-runtime-architecture.md)
7. [`./risk-audit-runtime-boundary.md`](./risk-audit-runtime-boundary.md)
8. [`./skills-vs-risk-checkers-boundary.md`](./skills-vs-risk-checkers-boundary.md)
9. [`./risk-audit-checker-roadmap.md`](./risk-audit-checker-roadmap.md)
10. [`./risk-audit-phase2-checker-implementation.md`](./risk-audit-phase2-checker-implementation.md)
11. [`./risk-audit-next-batch-checkers.md`](./risk-audit-next-batch-checkers.md)
12. [`./reader-experience-capability.md`](./reader-experience-capability.md)
13. [`./risk-audit-doc-consistency-checklist.md`](./risk-audit-doc-consistency-checklist.md)
14. [`./risk-audit-doc-source-of-truth-matrix.md`](./risk-audit-doc-source-of-truth-matrix.md)
15. [`./risk-audit-doc-stability-matrix.md`](./risk-audit-doc-stability-matrix.md)
16. [`./risk-audit-code-stability-matrix.md`](./risk-audit-code-stability-matrix.md)
17. [`./risk-audit-phase-completion-checklist.md`](./risk-audit-phase-completion-checklist.md)
18. [`./risk-audit-next-phase-30-60-90.md`](./risk-audit-next-phase-30-60-90.md)
19. [`./risk-audit-team-sync-brief.md`](./risk-audit-team-sync-brief.md)
20. [`./risk-audit-phase-1-freeze-declaration.md`](./risk-audit-phase-1-freeze-declaration.md)
21. [`./risk-audit-production-readiness.md`](./risk-audit-production-readiness.md)
22. [`./risk-audit-fresh10-verification-20260502.md`](./risk-audit-fresh10-verification-20260502.md)
23. [`./chapter-planning-capability-proposal.md`](./chapter-planning-capability-proposal.md)
24. [`./chapter-imitation-method.md`](./chapter-imitation-method.md)
25. [`./chapter-imitation-ch3-live-report-20260502.md`](./chapter-imitation-ch3-live-report-20260502.md)
26. [`./chapter-imitation-capability-matrix.md`](./chapter-imitation-capability-matrix.md)
27. [`./roles/imitation/README.md`](./roles/imitation/README.md)
28. [`./tracks/imitation/README.md`](./tracks/imitation/README.md)
29. [`./cluster-status-semantics.md`](./cluster-status-semantics.md)
30. [`./minimal-review-workflow-guide.md`](./minimal-review-workflow-guide.md)
31. [`./risk-audit-artifact-manifest.md`](./risk-audit-artifact-manifest.md)
32. [`./minimal-review-workflow-state-machine.md`](./minimal-review-workflow-state-machine.md)
33. [`./review-workflow-phase2-design.md`](./review-workflow-phase2-design.md)
34. [`./review-workflow-api.md`](./review-workflow-api.md)
35. [`./review-batch-execution-contract.md`](./review-batch-execution-contract.md)
36. [`./review-workflow-db-only-cutover.md`](./review-workflow-db-only-cutover.md)
37. [`./review-workflow-api-versioning.md`](./review-workflow-api-versioning.md)
38. [`./review-api-stability-summary.md`](./review-api-stability-summary.md)
39. [`./review-workflow-api-freeze-readiness.md`](./review-workflow-api-freeze-readiness.md)
40. [`./review-workflow-team-execution-guidelines.md`](./review-workflow-team-execution-guidelines.md)
41. [`./review-workflow-phase2-priority-ranking.md`](./review-workflow-phase2-priority-ranking.md)
42. [`./review-workflow-persistence-strategy.md`](./review-workflow-persistence-strategy.md)


### 样例小说结论链（运行期报告）
1. `../.omx/reports/sample-novel-current-conclusion.md`
2. `../.omx/reports/sample-novel-phase2-offline-memo-20260430.md`
3. `../.omx/reports/sample-novel-phase2-db-blocker-20260430.md`
4. `../.omx/reports/sample-novel-first-10-risk-check-20260502.md`
5. `../.omx/reports/risk-audit-mainline-verification-20260430.md`

说明：
- 第 1 份是当前样例小说主结论
- 第 2 份是 phase-2 离线 best-effort 结论
- 第 3 份是真实 phase-2 复跑阻塞与恢复清单
- 第 4 份是当前前10章风险核验摘要
- 第 5 份是当前风险审查主链 + 文档治理 + 验证结果的快照报告

### 前端 / 部署补充
- `apps/web/README.md`：前端开发、构建、npm 源
- `apps/api/README.md`：后端原型启动与接口说明


---

## 当前推荐运行配置

真实拆书与工作台当前建议统一使用：
- provider: `vip1129`
- base_url: `https://api.vip1129.cc/v1`
- model: `gpt-5.4-mini`

同时，当前失败恢复策略已经收口为：
- 自动重试最多 5 次
- 超过 5 次才需要人工介入

---

## 当前 release 建议阅读顺序

如果你现在要接手这个“基础可用 release”，建议按下面顺序看：

1. [`./release-handoff-brief.md`](./release-handoff-brief.md)
2. [`./final-handoff.md`](./final-handoff.md)
3. [`../apps/web/README.md`](../apps/web/README.md)
4. [`../apps/api/README.md`](../apps/api/README.md)
5. [`../CHANGELOG.md`](../CHANGELOG.md)

这样可以先理解：
- 当前 release 到了什么程度
- 已经能做哪些事
- 怎么启动前后端
- 最近几轮到底改了什么
