# 后端 / 架构师入口

**适合场景：**
- 理解系统整体架构与模块边界
- 开发新功能或维护核心链路
- 做架构决策（embedding、检索、风险审查）
- 评估技术演进路线

---

## 推荐阅读顺序

### 第一步：理解系统架构

1. [architecture/ai-novel-system-blueprint.md](../../architecture/ai-novel-system-blueprint.md) — 系统蓝图（全局视角）
2. [architecture/novel-assistant-system-architecture.md](../../architecture/novel-assistant-system-architecture.md) — 系统架构详解
3. [architecture/novel-assistant-business-architecture.md](../../architecture/novel-assistant-business-architecture.md) — 业务架构
4. [architecture/independent-agent-knowledge-and-retrieval.md](../../architecture/independent-agent-knowledge-and-retrieval.md) — 独立 Agent 知识与检索

### 第二步：了解当前能力状态

5. [features/architecture-mainline-checkout-20260504.md](../../features/architecture-mainline-checkout-20260504.md) — 主线架构当前状态
6. [features/retrieval-checkout-20260504.md](../../features/retrieval-checkout-20260504.md) — 检索能力当前状态
7. [features/independent-agent-capability-checkout-20260505.md](../../features/independent-agent-capability-checkout-20260505.md) — 独立 Agent 能力状态
8. [features/risk-semantic-checkout-20260504.md](../../features/risk-semantic-checkout-20260504.md) — 风险语义能力状态
9. [features/imitation-checkout-20260504.md](../../features/imitation-checkout-20260504.md) — 仿写能力状态
10. [features/eval-governance-checkout-20260504.md](../../features/eval-governance-checkout-20260504.md) — Eval/Governance 状态

### 第三步：深入风险审查体系

11. [tracks/risk-audit/README.md](../../tracks/risk-audit/README.md) — 风险审查能力线入口
12. [api-current-surface.md](../../api-current-surface.md) — 当前已实现 API surface
13. [risk-audit-runtime-architecture.md](../../risk-audit-runtime-architecture.md) — 风险审查运行时架构
14. [skills-vs-risk-checkers-boundary.md](../../skills-vs-risk-checkers-boundary.md) — skills 与 checker 边界
15. [architecture/risk-audit-semantic-enhancement.md](../../architecture/risk-audit-semantic-enhancement.md) — 语义增强设计
16. [architecture/risk-audit-embedding-pgvector-implementation-spec.md](../../architecture/risk-audit-embedding-pgvector-implementation-spec.md) — embedding/pgvector 实现规范
17. [risk-audit-checker-roadmap.md](../../risk-audit-checker-roadmap.md) — checker 路线图

---

## 关键文档速查

| 问题 | 文档 |
|------|------|
| 系统整体架构是什么？ | [系统蓝图](../../architecture/ai-novel-system-blueprint.md) |
| 当前 API 有哪些？ | [API surface](../../api-current-surface.md) |
| 风险审查怎么运行？ | [运行时架构](../../risk-audit-runtime-architecture.md) |
| embedding 怎么落地？ | [pgvector 实现规范](../../architecture/risk-audit-embedding-pgvector-implementation-spec.md) |
| checker 和 skills 怎么分？ | [边界说明](../../skills-vs-risk-checkers-boundary.md) |
| 下一批 checker 怎么做？ | [checker 路线图](../../risk-audit-checker-roadmap.md) |

---

## 生产向推荐重点

- **ONNX embedding + PostgreSQL/pgvector 语义信号层**
- **规则化 checker 判定层**（可解释，不依赖 LLM）
- **目标式 LLM 复核**（只在 checker 判定后做二次确认）

---

返回 [角色导航](../README.md) | [文档中心](../../README.md)
