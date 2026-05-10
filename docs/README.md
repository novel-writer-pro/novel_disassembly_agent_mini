# novel-analyzer 文档中心

> 本文件是所有文档的**唯一主入口**。按角色或能力线找到你的入口，再深入对应子目录。

---

## 快速分流 — 我是谁？

| 角色 | 我想做什么 | 入口 |
|------|-----------|------|
| **产品 / 业务** | 了解系统能力、产品策略、商业化方向 | [→ roles/product](./roles/product/README.md) |
| **后端 / 架构师** | 理解系统架构、开发新功能、维护核心链路 | [→ roles/backend](./roles/backend/README.md) |
| **接入者** | 对接 API、集成前端或下游系统 | [→ roles/integrator](./roles/integrator/README.md) |
| **维护者 / 接手人** | 接手项目、做文档治理、做版本交接 | [→ roles/maintainer](./roles/maintainer/README.md) |
| **仿写 / 创作** | 做章节仿写、全书仿写、创新导向实验 | [→ roles/imitation](./roles/imitation/README.md) |
| **使用者** | 直接跑 CLI、导入小说、查看分析结果 | [→ 使用者快速入口](#使用者快速入口) |

---

## 使用者快速入口

> 只想跑起来、导入小说、看分析结果的人，按顺序看这几份文档。

1. [CLI 操作手册](./cli-operations-manual.md) — 所有命令一览，快速上手
2. [日常使用指南](./direct-usage-guide.md) — 导入、切章、续传细节
3. [导入与切章规范](./novel-ingest-chapter-standard.md) — 导入前必读
4. [真实试跑清单](./real-run-checklist.md) — 正式跑前的 checklist
5. [工作台说明](../apps/web/README.md) — 前端工作台启动与页面说明

---

## 按能力线深入

| 能力线 | 说明 | 入口 |
|--------|------|------|
| **风险审查** | checker 体系、语义增强、生产就绪 | [→ tracks/risk-audit](./tracks/risk-audit/README.md) |
| **Review Workflow** | 批量 review、API 稳定性、DB 切换 | [→ tracks/review-workflow](./tracks/review-workflow/README.md) |
| **仿写能力** | 章节仿写、全书仿写、创新导向 | [→ tracks/imitation](./tracks/imitation/README.md) |
| **读者体验** | 读者模拟、反馈收集、体验规划 | [→ tracks/reader-experience](./tracks/reader-experience/README.md) |

---

## 按文档类型查找

### A 层 — 规范入口（稳定，优先看）

| 文档 | 说明 |
|------|------|
| [interface-manifest.md](./interface-manifest.md) | 稳定接口结构定义 |
| [api-current-surface.md](./api-current-surface.md) | 当前已实现 API surface |
| [api-contract.md](./api-contract.md) | API 合同（稳定字段） |
| [agent-skills-and-embedding.md](./agent-skills-and-embedding.md) | 内部 agent pipeline 与 ONNX embedding |
| [storage-lifecycle.md](./storage-lifecycle.md) | 数据存储生命周期 |
| [application-seams.md](./application-seams.md) | 应用层接缝设计 |

### B 层 — 策略 / 治理（产品与架构决策）

| 文档 | 说明 |
|------|------|
| [product/ai-novel-product-strategy.md](./product/ai-novel-product-strategy.md) | 产品策略 |
| [product/ai-novel-capability-map.md](./product/ai-novel-capability-map.md) | 能力地图 |
| [product/ai-novel-capability-scorecard.md](./product/ai-novel-capability-scorecard.md) | 能力评分卡 |
| [product/ai-novel-commercialization-and-moat-20260508.md](./product/ai-novel-commercialization-and-moat-20260508.md) | 商业化与护城河 |
| [strategy/ai-novel-system-benchmark.md](./strategy/ai-novel-system-benchmark.md) | 系统基准对比 |
| [strategy/capability-roadmap-and-deliverables.md](./strategy/capability-roadmap-and-deliverables.md) | 能力路线图与交付物 |
| [whitepaper/ai-novel-system-whitepaper-v2.md](./whitepaper/ai-novel-system-whitepaper-v2.md) | 系统白皮书 v2（最新） |
| [whitepaper/ai-novel-system-whitepaper.md](./whitepaper/ai-novel-system-whitepaper.md) | 系统白皮书 v1 |
| [features/README.md](./features/README.md) | Feature Checkout 入口（各能力线当前状态） |
| [features/feature-checkout-template.md](./features/feature-checkout-template.md) | Feature Checkout 模板 |
| [features/architecture-mainline-checkout-20260504.md](./features/architecture-mainline-checkout-20260504.md) | 架构主线 Checkout（2026-05-04） |
| [features/retrieval-checkout-20260504.md](./features/retrieval-checkout-20260504.md) | 检索能力 Checkout（2026-05-04） |
| [features/risk-semantic-checkout-20260504.md](./features/risk-semantic-checkout-20260504.md) | 风险语义 Checkout（2026-05-04） |
| [features/imitation-checkout-20260504.md](./features/imitation-checkout-20260504.md) | 仿写能力 Checkout（2026-05-04） |
| [features/eval-governance-checkout-20260504.md](./features/eval-governance-checkout-20260504.md) | Eval/Governance Checkout（2026-05-04） |
| [features/independent-agent-capability-checkout-20260505.md](./features/independent-agent-capability-checkout-20260505.md) | 独立 Agent 能力 Checkout（2026-05-05） |
| [process/README.md](./process/README.md) | 开发流程入口 |

### C 层 — 技术实现（开发与接入参考）

| 文档 | 说明 |
|------|------|
| [risk-audit-system-overview.md](./risk-audit-system-overview.md) | 风险审查系统总览 |
| [risk-audit-runtime-architecture.md](./risk-audit-runtime-architecture.md) | 风险审查运行时架构 |
| [risk-audit-capability.md](./risk-audit-capability.md) | 风险审查能力说明 |
| [./risk-audit-production-readiness.md](./risk-audit-production-readiness.md) | 风险审查生产就绪状态 |
| [review-workflow-api.md](./review-workflow-api.md) | Review Workflow API |
| [review-api-stability-summary.md](./review-api-stability-summary.md) | Review API 稳定字段收口 |
| [whole-book-imitation-docs-index.md](./whole-book-imitation-docs-index.md) | 全书仿写文档索引 |
| [whole-book-imitation-integration-quickstart.md](./whole-book-imitation-integration-quickstart.md) | 全书仿写接入快速入门 |
| [whole-book-imitation-api-stability-summary.md](./whole-book-imitation-api-stability-summary.md) | 全书仿写 API 稳定性摘要 |
| [whole-book-imitation-api-versioning.md](./whole-book-imitation-api-versioning.md) | 全书仿写 API 版本管理 |
| [whole-book-imitation-api-freeze-readiness.md](./whole-book-imitation-api-freeze-readiness.md) | 全书仿写 API 冻结就绪状态 |
| [whole-book-imitation-freeze-evidence-20260503.md](./whole-book-imitation-freeze-evidence-20260503.md) | 全书仿写冻结证据（2026-05-03） |
| [whole-book-imitation-provider-recovery-checklist.md](./whole-book-imitation-provider-recovery-checklist.md) | 全书仿写 Provider 恢复 Checklist |
| [whole-book-imitation-sample-coverage-matrix.md](./whole-book-imitation-sample-coverage-matrix.md) | 全书仿写样例覆盖矩阵 |
| [whole-book-imitation-handoff-brief.md](./whole-book-imitation-handoff-brief.md) | 全书仿写交接简报 |
| [examples/whole-book-imitation-run.sample.json](./examples/whole-book-imitation-run.sample.json) | 全书仿写运行样例 |
| [examples/whole-book-imitation-readiness.sample.json](./examples/whole-book-imitation-readiness.sample.json) | 全书仿写就绪状态样例 |
| [examples/whole-book-imitation-run.request.sample.json](./examples/whole-book-imitation-run.request.sample.json) | 全书仿写请求样例 |
| [examples/whole-book-imitation-run.provider-success-20260504.sample.json](./examples/whole-book-imitation-run.provider-success-20260504.sample.json) | 全书仿写 Provider 成功样例 |
| [examples/whole-book-imitation-run.error.provider-billing.sample.json](./examples/whole-book-imitation-run.error.provider-billing.sample.json) | 全书仿写 Provider 计费错误样例 |
| [chapter-imitation-method.md](./chapter-imitation-method.md) | 章节仿写方法论 |
| [eval-governance-sample-release-contract.md](./eval-governance-sample-release-contract.md) | Eval/Governance 冻结口径 |
| [./imitation-control-plane-glossary.md](./imitation-control-plane-glossary.md) | 控制层术语表（control plane / runtime / governance 等） |
| [./novel-assistant-manual-eval-handbook-20260505.md](./novel-assistant-manual-eval-handbook-20260505.md) | 人工评估操作手册 |
| [./manual-eval-record-template.md](./manual-eval-record-template.md) | 人工评估记录模板 |
| [../runs/manual_eval/_template/README.md](../runs/manual_eval/_template/README.md) | 人工评估工作区模板（bootstrap_manual_eval_workspace.py） |

### D 层 — 历史证据 / 样例（归档参考）

| 文档 | 说明 |
|------|------|
| [examples/](./examples/) | 所有样例 JSON / Markdown |
| [real-run-evaluation-1-12.md](./real-run-evaluation-1-12.md) | 真实试跑 1-12 章评估 |
| [risk-audit-fresh10-verification-20260502.md](./risk-audit-fresh10-verification-20260502.md) | 前10章风险核验 |
| [chapter-imitation-ch3-live-report-20260502.md](./chapter-imitation-ch3-live-report-20260502.md) | 第3章仿写 live 报告 |
| [release-delivery-archive-index-20260505.md](./release-delivery-archive-index-20260505.md) | Release 交付归档索引 |
| [../.omx/reports/sample-novel-first-10-risk-check-20260502.md](../.omx/reports/sample-novel-first-10-risk-check-20260502.md) | 样例小说前10章风险核验报告 |
| [./examples/sample-branch-report.post-migration-20260504.sample.md](./examples/sample-branch-report.post-migration-20260504.sample.md) | 样例分支报告（迁移后） |
| [./examples/sample-branch-search-diagnostics-20260505.sample.json](./examples/sample-branch-search-diagnostics-20260505.sample.json) | 样例搜索诊断 |
| [./examples/sample-branch-author-knowledge-20260505.sample.json](./examples/sample-branch-author-knowledge-20260505.sample.json) | 样例作者知识 |
| [./examples/sample-branch-novel-assistant-20260505.sample.json](./examples/sample-branch-novel-assistant-20260505.sample.json) | 样例小说助手 |
| [./chapter-planning-capability-proposal.md](./chapter-planning-capability-proposal.md) | 章节规划能力提案 |

---

## 架构专题

> 深入系统设计、模块边界、演进路线，看这里。

→ [architecture/README.md](./architecture/README.md)

---

## Loom 架构（下一代）

> Loom 是在现有 GraphRAG 基础设施与 0509 仿写控制层之上的升级层，
> 填补五个关键缺口：分层记忆代谢、学习型评估、叙事张力调节、文风/节奏量化（Phase 4）、角色认知基（Phase 4）。

→ [loom/README.md](./loom/README.md)

| 文档 | 说明 |
|------|------|
| [loom/overview.md](./loom/overview.md) | 完整架构图、SOTA 对比、风险分析 |
| [loom/arch-diff-and-alignment.md](./loom/arch-diff-and-alignment.md) | **0509 vs Loom 冲突点与对齐方案**（必读） |
| [loom/roadmap.md](./loom/roadmap.md) | Phase 1-5 开发路线图 + 验收标准 |
| [loom/gap-analysis-and-evolution.md](./loom/gap-analysis-and-evolution.md) | 商业水准差距分析 + Phase 4/5 演进规划 |

核心文档：
- [ai-novel-system-blueprint.md](./architecture/ai-novel-system-blueprint.md) — 系统蓝图
- [novel-assistant-system-architecture.md](./architecture/novel-assistant-system-architecture.md) — 系统架构
- [novel-assistant-business-architecture.md](./architecture/novel-assistant-business-architecture.md) — 业务架构
- [independent-agent-knowledge-and-retrieval.md](./architecture/independent-agent-knowledge-and-retrieval.md) — 独立 Agent 知识与检索
- [chapter-imitation-harness-architecture.md](./architecture/chapter-imitation-harness-architecture.md) — 仿写 Harness 架构

---

## 交付与版本管理

| 文档 | 说明 |
|------|------|
| [final-handoff.md](./final-handoff.md) | 完整交付说明（边界、风险、已知问题） |
| [release-handoff-brief.md](./release-handoff-brief.md) | 简版交接说明 |
| [session-handoff-manual.md](./session-handoff-manual.md) | 会话交接手册 |
| [../CHANGELOG.md](../CHANGELOG.md) | 开发变更记录（每次变更必须追加） |

---

## 文档治理

| 文档 | 说明 |
|------|------|
| [strategy/docs-information-architecture-guide.md](./strategy/docs-information-architecture-guide.md) | 文档分层架构指南（A/B/C/D 层定义） |
| [strategy/docs-governance-and-handoff-checklist.md](./strategy/docs-governance-and-handoff-checklist.md) | 文档治理与交接 checklist |
| [strategy/docs-faq-and-consolidation-guide.md](./strategy/docs-faq-and-consolidation-guide.md) | 文档 FAQ 与合并指南 |
| [risk-audit-doc-source-of-truth-matrix.md](./risk-audit-doc-source-of-truth-matrix.md) | 文档真相来源矩阵 |

---

## 当前推荐运行配置

```
provider: vip1129
base_url: https://api.vip1129.cc/v1
model: gpt-5.4-mini
```

失败恢复策略：自动重试最多 5 次，超过 5 次才需要人工介入。

---

## 接手 Release 建议阅读顺序

如果你现在要接手当前 release，按此顺序：

1. [release-handoff-brief.md](./release-handoff-brief.md) — 当前 release 到了什么程度
2. [final-handoff.md](./final-handoff.md) — 完整交付边界与风险
3. [../apps/web/README.md](../apps/web/README.md) — 前端启动
4. [../apps/api/README.md](../apps/api/README.md) — 后端启动
5. [../CHANGELOG.md](../CHANGELOG.md) — 最近几轮改了什么

---

## 后端 / 开发者建议阅读顺序

- [roles/backend/README.md](./roles/backend/README.md) — 后端角色入口
- [interface-manifest.md](./interface-manifest.md) — 稳定接口结构
- 3. [`./api-current-surface.md`](./api-current-surface.md) — 第 3 步：再看当前已实现 API surface

---

## 接入者建议阅读顺序

- [roles/integrator/README.md](./roles/integrator/README.md) — 接入者角色入口
- [`./api-current-surface.md`](./api-current-surface.md) — 第 2 步：再看当前已实现 API surface
