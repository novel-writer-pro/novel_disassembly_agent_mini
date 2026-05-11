# 维护者 / 接手人入口

**适合场景：**
- 接手项目，需要快速了解当前状态
- 做文档治理，整理文档结构
- 做版本交接，准备 release
- 了解文档真相来源，避免信息冲突

---

## 推荐阅读顺序

### 第一步：了解当前 release 状态

1. [release-handoff-brief.md](../../release-handoff-brief.md) — 简版交接说明（先看这个）
2. [final-handoff.md](../../final-handoff.md) — 完整交付说明（边界、风险、已知问题）
3. [../CHANGELOG.md](../../../CHANGELOG.md) — 最近几轮改了什么

### 第二步：了解文档治理结构

4. [strategy/docs-information-architecture-guide.md](../../strategy/docs-information-architecture-guide.md) — 文档分层架构指南（A/B/C/D 层定义）
5. [strategy/docs-governance-and-handoff-checklist.md](../../strategy/docs-governance-and-handoff-checklist.md) — 文档治理与交接 checklist
6. [strategy/docs-faq-and-consolidation-guide.md](../../strategy/docs-faq-and-consolidation-guide.md) — 文档 FAQ 与合并指南

### 第三步：了解当前能力状态

7. [features/README.md](../../features/README.md) — Feature Checkout 入口（各能力线当前状态）
8. [features/feature-checkout-template.md](../../features/feature-checkout-template.md) — Feature Checkout 模板
9. [features/architecture-mainline-checkout-20260504.md](../../features/architecture-mainline-checkout-20260504.md) — 主线架构当前状态

### 第四步：了解文档真相来源

10. [risk-audit-docs-index.md](../../risk-audit-docs-index.md) — 风险审查文档索引
11. [risk-audit-doc-source-of-truth-matrix.md](../../risk-audit-doc-source-of-truth-matrix.md) — 文档真相来源矩阵
12. [risk-audit-doc-consistency-checklist.md](../../risk-audit-doc-consistency-checklist.md) — 文档一致性 checklist

### 第五步：了解架构与 API

13. [architecture/README.md](../../architecture/README.md) — 架构专题入口
14. [api-current-surface.md](../../api-current-surface.md) — 当前已实现 API surface

---

## 关键文档速查

| 问题 | 文档 |
|------|------|
| 当前 release 到了什么程度？ | [release-handoff-brief](../../release-handoff-brief.md) |
| 已知风险和问题有哪些？ | [final-handoff](../../final-handoff.md) |
| 文档怎么分层管理？ | [docs-information-architecture-guide](../../strategy/docs-information-architecture-guide.md) |
| 哪份文档是真相来源？ | [doc-source-of-truth-matrix](../../risk-audit-doc-source-of-truth-matrix.md) |
| 各能力线当前状态？ | [features/README](../../features/README.md) |
| 最近改了什么？ | [CHANGELOG](../../../CHANGELOG.md) |

---

## 文档维护约定

- 每次修复 / 变动必须同步：文档、`CHANGELOG.md`、git commit 记录
- 新能力方向 / 新产品叙事：新增文档
- 只是入口混乱：优先改索引，不要重复写内容
- 临时验证：先写 evidence，再决定是否升格为 canonical doc

---

返回 [角色导航](../README.md) | [文档中心](../../README.md)
