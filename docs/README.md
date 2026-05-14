# novel-analyzer 文档中心

> 精简后的文档主入口。按角色快速分流，按深度分层阅读。

---

## 系统架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        novel-analyzer                            │
├─────────────┬──────────────┬──────────────┬────────────────────┤
│   导入层    │    分析层     │    质量层     │      产品层        │
│  ingest     │  analysis    │  risk audit  │  QA / export / API │
│  splitter   │  stages(3)   │  9 checkers  │  quality dashboard │
├─────────────┼──────────────┼──────────────┼────────────────────┤
│             │              │              │                    │
│  章节切分   │ intake+facts │ claim ground │  问答增强          │
│  规范化     │ evidence+    │ auto-repair  │  伏笔/因果导出     │
│             │  analysis    │ confidence   │  质量仪表盘        │
│             │ guard        │  gated       │                    │
├─────────────┴──────────────┴──────────────┴────────────────────┤
│                     基础设施层                                    │
│  PostgreSQL │ BM25/Vector │ GraphNode/Edge │ Provider Health    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 快速分流

| 我是... | 入口 |
|---------|------|
| 产品 / 业务 | [roles/product](./roles/product/README.md) |
| 后端 / 架构师 | [roles/backend](./roles/backend/README.md) |
| 接入者 (API/前端) | [roles/integrator](./roles/integrator/README.md) |
| 维护者 / 接手人 | [roles/maintainer](./roles/maintainer/README.md) |
| 仿写 / 创作 | [roles/imitation](./roles/imitation/README.md) |
| 直接使用 CLI | [CLI 操作手册](./cli-operations-manual.md) |

---

## 核心文档 (必读)

| 文档 | 说明 | 适合谁 |
|------|------|--------|
| [cli-operations-manual.md](./cli-operations-manual.md) | CLI 命令真相源 | 使用者 |
| [direct-usage-guide.md](./direct-usage-guide.md) | 日常操作顺序 | 使用者 |
| [novel-ingest-input-spec.md](./novel-ingest-input-spec.md) | 小说输入规范 (novel.txt 格式) | 使用者 |
| [api-current-surface.md](./api-current-surface.md) | 当前 API 端点清单 | 接入者 |
| [interface-manifest.md](./interface-manifest.md) | 稳定接口结构 | 后端 |
| [deconstruction-acceleration/roadmap-sota-optimization.md](./deconstruction-acceleration/roadmap-sota-optimization.md) | SOTA 优化路线图 + 架构图 | 架构师 |
| [deconstruction-acceleration/handoff-sota-optimization.md](./deconstruction-acceleration/handoff-sota-optimization.md) | SOTA 优化交付文档 | 接手人 |

---

## 能力线索引

| 能力线 | 入口 | 状态 |
|--------|------|------|
| 拆书引擎 (SOTA) | [deconstruction-acceleration/](./deconstruction-acceleration/README.md) | Phase 4.5 完成 |
| 底座优化 | [foundation-optimization/](./foundation-optimization/README.md) | P0-P2 全部完成 |
| 风险审查 | [risk-audit-system-overview.md](./risk-audit-system-overview.md) | 9 checker 生产就绪 |
| 仿写能力 | [writer-imitation-workflow.md](./writer-imitation-workflow.md) | 全书仿写可用 |
| Review 工作流 | [minimal-review-workflow-guide.md](./minimal-review-workflow-guide.md) | DB-only 模式 |
| 读者体验 | [reader-experience-capability.md](./reader-experience-capability.md) | 基础可用 |

---

## 按深度分层

```
Level 0 (本文件)
  │
  ├── Level 1: 核心文档 (6 份，必读)
  │     cli-operations-manual / direct-usage-guide / api-current-surface
  │     interface-manifest / roadmap-sota / handoff-sota
  │
  ├── Level 2: 能力线文档 (按需深入)
  │     deconstruction-acceleration/ / risk-audit-* / imitation-* / review-*
  │
  ├── Level 3: 架构与策略 (架构师/产品)
  │     architecture/ / strategy/ / product/
  │
  └── Level 4: 历史归档 (deprecated/)
        已完成的一次性报告、旧版设计文档、冻结声明
```

---

## Level 2: 拆书引擎

| 文档 | 说明 |
|------|------|
| [deconstruction-acceleration/README.md](./deconstruction-acceleration/README.md) | 拆书加速文档入口 |
| [deconstruction-acceleration/architecture.md](./deconstruction-acceleration/architecture.md) | Quick/Deep 双档架构 |
| [deconstruction-acceleration/roadmap-sota-optimization.md](./deconstruction-acceleration/roadmap-sota-optimization.md) | SOTA 路线图 + benchmark + 风险矩阵 |
| [deconstruction-acceleration/handoff-sota-optimization.md](./deconstruction-acceleration/handoff-sota-optimization.md) | 交付文档 |
| [deconstruction-acceleration/user-manual.md](./deconstruction-acceleration/user-manual.md) | 用户使用说明 |

## Level 2: 风险审查

| 文档 | 说明 |
|------|------|
| [risk-audit-system-overview.md](./risk-audit-system-overview.md) | 系统总览 |
| [risk-audit-capability.md](./risk-audit-capability.md) | 能力说明 |
| [risk-audit-runtime-architecture.md](./risk-audit-runtime-architecture.md) | 运行时架构 |
| [risk-audit-checker-roadmap.md](./risk-audit-checker-roadmap.md) | Checker 路线图 |
| [risk-audit-production-readiness.md](./risk-audit-production-readiness.md) | 生产就绪评估 |

## Level 2: 仿写

| 文档 | 说明 |
|------|------|
| [writer-imitation-workflow.md](./writer-imitation-workflow.md) | 仿写工作流 |
| [chapter-imitation-method.md](./chapter-imitation-method.md) | 章节仿写方法 |
| [chapter-imitation-capability-matrix.md](./chapter-imitation-capability-matrix.md) | 仿写能力矩阵 |
| [imitation-control-plane-glossary.md](./imitation-control-plane-glossary.md) | 仿写控制面术语表 |
| [whole-book-imitation-integration-quickstart.md](./whole-book-imitation-integration-quickstart.md) | 全书仿写快速接入 |
| [whole-book-imitation-handoff-brief.md](./whole-book-imitation-handoff-brief.md) | 全书仿写交接 |

## Level 2: API 与接入

| 文档 | 说明 |
|------|------|
| [api-current-surface.md](./api-current-surface.md) | 当前 API 端点 |
| [api-contract.md](./api-contract.md) | API 合同 (稳定字段) |
| [review-workflow-api.md](./review-workflow-api.md) | Review API |
| [review-batch-execution-contract.md](./review-batch-execution-contract.md) | 批量执行合同 |

---

## Level 3: 架构与策略

| 目录 | 说明 |
|------|------|
| [architecture/](./architecture/) | 系统蓝图、业务架构、Agent 知识架构 |
| [strategy/](./strategy/) | 文档治理、能力路线图、基准对比 |
| [product/](./product/) | 产品策略、能力地图、商业化 |
| [loom/](./loom/) | Loom 记忆系统 (Phase 1-5) |

---

## Level 4: 历史归档

已移入 `docs/deprecated/`，包含：
- 一次性评估报告 (manual-eval, stage-evaluation, real-run-evaluation)
- 已冻结的 API 版本声明 (freeze-evidence, api-versioning)
- 旧版设计文档 (phase2-design, persistence-strategy)
- 模板文件 (review-template, rewrite-brief-template)
- 已完成的 checklist (phase-completion, doc-consistency)

这些文档保留完整内容但不再作为活跃参考。如需查阅，直接进入 `docs/deprecated/` 目录。

---

## 当前推荐运行配置

```bash
NOVEL_ANALYZER_LLM_PROVIDER_NAME=deepseek
NOVEL_ANALYZER_LLM_BASE_URL=https://api.deepseek.com/v1
NOVEL_ANALYZER_LLM_MODEL_NAME=deepseek-v4-flash
NOVEL_ANALYZER_LLM_STAGE_MODEL_NAME=deepseek-v4-flash
NOVEL_ANALYZER_USE_MERGED_STAGES=true
```

---

## 接手建议阅读顺序

- [release-handoff-brief.md](./release-handoff-brief.md) — 当前 release 到了什么程度
- [final-handoff.md](./final-handoff.md) — 完整交付边界与风险
- [deconstruction-acceleration/handoff-sota-optimization.md](./deconstruction-acceleration/handoff-sota-optimization.md) — SOTA 优化交付
- [../apps/web/README.md](../apps/web/README.md) — 前端启动
- [../apps/api/README.md](../apps/api/README.md) — 后端启动
- [../CHANGELOG.md](../CHANGELOG.md) — 最近变更记录
