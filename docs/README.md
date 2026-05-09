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
- [`./architecture/ai-novel-system-blueprint.md`](./architecture/ai-novel-system-blueprint.md)
- [`./architecture/independent-agent-knowledge-and-retrieval.md`](./architecture/independent-agent-knowledge-and-retrieval.md)
- [`./architecture/novel-assistant-system-architecture.md`](./architecture/novel-assistant-system-architecture.md)
- [`./architecture/novel-assistant-business-architecture.md`](./architecture/novel-assistant-business-architecture.md)
- [`./architecture/risk-audit-semantic-enhancement.md`](./architecture/risk-audit-semantic-enhancement.md)
- [`./architecture/risk-audit-embedding-pgvector-implementation-spec.md`](./architecture/risk-audit-embedding-pgvector-implementation-spec.md)
- [`./architecture/risk-audit-completion-status.md`](./architecture/risk-audit-completion-status.md)
- [`./architecture/chapter-imitation-harness-architecture.md`](./architecture/chapter-imitation-harness-architecture.md)
- [`./architecture/imitation-commercial-agent-control-plane-architecture-20260509.md`](./architecture/imitation-commercial-agent-control-plane-architecture-20260509.md)
- [`./risk-audit-production-readiness.md`](./risk-audit-production-readiness.md)
- [`./mainline-architecture-upgrade-review-20260504.md`](./mainline-architecture-upgrade-review-20260504.md)

### 新的治理 / 战略入口
- [`./features/README.md`](./features/README.md)
- [`./features/feature-checkout-template.md`](./features/feature-checkout-template.md)
- [`./features/architecture-mainline-checkout-20260504.md`](./features/architecture-mainline-checkout-20260504.md)
- [`./features/retrieval-checkout-20260504.md`](./features/retrieval-checkout-20260504.md)
- [`./features/risk-semantic-checkout-20260504.md`](./features/risk-semantic-checkout-20260504.md)
- [`./features/imitation-checkout-20260504.md`](./features/imitation-checkout-20260504.md)
- [`./features/eval-governance-checkout-20260504.md`](./features/eval-governance-checkout-20260504.md)
- [`./features/independent-agent-capability-checkout-20260505.md`](./features/independent-agent-capability-checkout-20260505.md)
- [`./features/novel-assistant-control-checkout-20260505.md`](./features/novel-assistant-control-checkout-20260505.md)
- [`./product/ai-novel-product-strategy.md`](./product/ai-novel-product-strategy.md)
- [`./product/ai-novel-capability-scorecard.md`](./product/ai-novel-capability-scorecard.md)
- [`./product/ai-novel-capability-map.md`](./product/ai-novel-capability-map.md)
- [`./product/ai-novel-commercialization-and-moat-20260508.md`](./product/ai-novel-commercialization-and-moat-20260508.md)
- [`./strategy/ai-novel-system-benchmark.md`](./strategy/ai-novel-system-benchmark.md)
- [`./strategy/docs-governance-and-handoff-checklist.md`](./strategy/docs-governance-and-handoff-checklist.md)
- [`./strategy/docs-information-architecture-guide.md`](./strategy/docs-information-architecture-guide.md)
- [`./strategy/docs-faq-and-consolidation-guide.md`](./strategy/docs-faq-and-consolidation-guide.md)
- [`./strategy/capability-roadmap-and-deliverables.md`](./strategy/capability-roadmap-and-deliverables.md)
- [`./process/README.md`](./process/README.md)
- [`./whitepaper/ai-novel-system-whitepaper.md`](./whitepaper/ai-novel-system-whitepaper.md)
- [`./whitepaper/ai-novel-system-whitepaper-v2.md`](./whitepaper/ai-novel-system-whitepaper-v2.md)

---

## 0. 开发变更记录

- [`../CHANGELOG.md`](../CHANGELOG.md)：后续每次开发更改都需要追加记录
- 约定：每次修复 / 变动都需要同步更新文档、changelog 与 commit 记录

## 1. 使用者（只想直接用系统的人）

### 推荐阅读顺序
1. [`./cli-operations-manual.md`](./cli-operations-manual.md)
2. [`./direct-usage-guide.md`](./direct-usage-guide.md)
3. [`./novel-ingest-chapter-standard.md`](./novel-ingest-chapter-standard.md)
4. [`./real-run-checklist.md`](./real-run-checklist.md)
5. [`./novel-assistant-manual-eval-handbook-20260505.md`](./novel-assistant-manual-eval-handbook-20260505.md)
6. [`./manual-eval-record-template.md`](./manual-eval-record-template.md)
7. [`./review-template.md`](./review-template.md)
8. [`./session-handoff-manual.md`](./session-handoff-manual.md)
9. [`./writer-imitation-workflow.md`](./writer-imitation-workflow.md)
10. `../output/novel-imitation-21-30/README.md`（本地仿写正文评审入口，不提交）
11. [`./reader-sim-review-usage.md`](./reader-sim-review-usage.md)
12. [`./imitation-innovation-and-steering.md`](./imitation-innovation-and-steering.md)
13. [`./trope-worldview-rag-library-format.md`](./trope-worldview-rag-library-format.md)
14. [`./batch-innovation-experiment-workflow.md`](./batch-innovation-experiment-workflow.md)
15. [`./imitation-next-dev-handoff.md`](./imitation-next-dev-handoff.md)
16. [`./imitation-control-plane-glossary.md`](./imitation-control-plane-glossary.md)

### 说明
- 第 1 步：先看怎么跑 CLI
- 第 2 步：再看日常使用细节
- 第 3 步：先确认导入、切章、保存与续传规范
- 第 4 步：真实小说试跑前看清单
- 第 5 步：按全能力手册做拆书 / 检索 / 风险 / 仿写 / 治理人工测试
- 第 6 步：用人工测试记录模板沉淀结论与薄弱点
- 第 7 步：试跑后用模板做复盘
- 第 8 步：如果进入仿写实战，按 writer imitation workflow 走 output 工作目录
- 第 9 步：若已进入真实仿写补写，可直接查看 `output/novel-imitation-21-30/combined.md` 做连续人工审稿
- 第 10 步：若想确认“模拟读者阅读 / reader sim”怎么用，直接看 `reader-sim-review-usage.md`
- 第 11 步：若想让仿写不只保守贴原章，而是显式引入新世界观/套路/创新导向，直接看 `imitation-innovation-and-steering.md`
- 第 12 步：若想建设 trope/worldview 文档库并准备 RAG，直接看 `trope-worldview-rag-library-format.md`
- 第 13 步：若想对一批章节统一做创新导向实验，直接看 `batch-innovation-experiment-workflow.md`
- 第 14 步：若想直接从本地 trope/worldview/audience 文档装配 steering pack，先准备 `rag/` 目录再走 innovation experiment
- 第 15 步：若本轮要暂停并为后续继续开发留交接入口，直接看 `imitation-next-dev-handoff.md`
- 第 16 步：若觉得 control-plane 里英文术语过多，直接看 `imitation-control-plane-glossary.md`
- 补充：可直接从 `../runs/manual_eval/_template/README.md` 复制一套标准评估目录
- 也可运行 `python3 scripts/bootstrap_manual_eval_workspace.py <novel_slug>` 一键初始化评估目录

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
9. [`./mainline-architecture-upgrade-review-20260504.md`](./mainline-architecture-upgrade-review-20260504.md)
10. [`./eval-governance-sample-release-contract.md`](./eval-governance-sample-release-contract.md)

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
3. [`./novel-ingest-chapter-standard.md`](./novel-ingest-chapter-standard.md)
4. [`./real-run-checklist.md`](./real-run-checklist.md)
5. [`./novel-assistant-manual-eval-handbook-20260505.md`](./novel-assistant-manual-eval-handbook-20260505.md)
6. [`./manual-eval-record-template.md`](./manual-eval-record-template.md)
7. [`./review-template.md`](./review-template.md)
8. [`./session-handoff-manual.md`](./session-handoff-manual.md)
9. [`./writer-imitation-workflow.md`](./writer-imitation-workflow.md)
10. [`../apps/web/README.md`](../apps/web/README.md)
11. [`../apps/api/README.md`](../apps/api/README.md)

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
13. [`./examples/whole-book-imitation-run.provider-success-20260504.sample.json`](./examples/whole-book-imitation-run.provider-success-20260504.sample.json)
14. [`./examples/whole-book-imitation-run.sandbox-live-20260505.sample.json`](./examples/whole-book-imitation-run.sandbox-live-20260505.sample.json)
15. [`./examples/sample-branch-report.post-migration-20260504.sample.md`](./examples/sample-branch-report.post-migration-20260504.sample.md)
16. [`./examples/whole-book-imitation-run.error.provider-billing.sample.json`](./examples/whole-book-imitation-run.error.provider-billing.sample.json)
17. [`./examples/sample-branch-search-diagnostics-20260505.sample.json`](./examples/sample-branch-search-diagnostics-20260505.sample.json)
18. [`./examples/sample-branch-author-knowledge-20260505.sample.json`](./examples/sample-branch-author-knowledge-20260505.sample.json)
19. [`./examples/sample-branch-novel-assistant-20260505.sample.json`](./examples/sample-branch-novel-assistant-20260505.sample.json)
20. [`./examples/sample-branch-retrieval-benchmark-20260505.sample.json`](./examples/sample-branch-retrieval-benchmark-20260505.sample.json)
21. [`./examples/sample-branch-governance-dashboard-20260505.sample.json`](./examples/sample-branch-governance-dashboard-20260505.sample.json)
22. [`./examples/sample-branch-governance-report-brief-20260505.sample.md`](./examples/sample-branch-governance-report-brief-20260505.sample.md)
23. [`./examples/sample-branch-release-review-note-20260505.sample.md`](./examples/sample-branch-release-review-note-20260505.sample.md)
24. [`./examples/sample-branch-approval-decision-memo-20260505.sample.md`](./examples/sample-branch-approval-decision-memo-20260505.sample.md)
25. [`./examples/sample-reader-feedback-summary-20260505.sample.json`](./examples/sample-reader-feedback-summary-20260505.sample.json)
26. [`./examples/sample-branch-external-report-bundle-20260505.sample.json`](./examples/sample-branch-external-report-bundle-20260505.sample.json)
27. [`./examples/sample-branch-external-report-bundle-20260505.sample.md`](./examples/sample-branch-external-report-bundle-20260505.sample.md)
28. [`./examples/sample-branch-final-release-archive-20260505.sample.json`](./examples/sample-branch-final-release-archive-20260505.sample.json)
29. [`./whole-book-imitation-api-stability-summary.md`](./whole-book-imitation-api-stability-summary.md)
30. [`./whole-book-imitation-api-versioning.md`](./whole-book-imitation-api-versioning.md)
31. [`./whole-book-imitation-api-freeze-readiness.md`](./whole-book-imitation-api-freeze-readiness.md)
32. [`./whole-book-imitation-freeze-evidence-20260503.md`](./whole-book-imitation-freeze-evidence-20260503.md)
33. [`./examples/whole-book-imitation-readiness.sample.json`](./examples/whole-book-imitation-readiness.sample.json)
34. [`./whole-book-imitation-integration-quickstart.md`](./whole-book-imitation-integration-quickstart.md)
35. [`./whole-book-imitation-docs-index.md`](./whole-book-imitation-docs-index.md)
36. [`./whole-book-imitation-provider-recovery-checklist.md`](./whole-book-imitation-provider-recovery-checklist.md)
37. [`./whole-book-imitation-sample-coverage-matrix.md`](./whole-book-imitation-sample-coverage-matrix.md)
38. [`./whole-book-imitation-handoff-brief.md`](./whole-book-imitation-handoff-brief.md)
39. [`./eval-governance-sample-release-contract.md`](./eval-governance-sample-release-contract.md)
40. [`./examples/eval-governance-cross-lane-bundle.sample.json`](./examples/eval-governance-cross-lane-bundle.sample.json)

### 交付与维护类文档
1. [`./release-delivery-archive-index-20260505.md`](./release-delivery-archive-index-20260505.md)
2. [`./final-handoff.md`](./final-handoff.md)
3. [`./release-handoff-brief.md`](./release-handoff-brief.md)
4. [`./real-run-evaluation-1-12.md`](./real-run-evaluation-1-12.md)
5. [`./model-eval-template.md`](./model-eval-template.md)
6. [`./agent-skills-and-embedding.md`](./agent-skills-and-embedding.md)
7. [`./application-seams.md`](./application-seams.md)
8. [`./api-contract.md`](./api-contract.md)
9. [`./storage-lifecycle.md`](./storage-lifecycle.md)

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
