# 架构专题文档入口

> 系统设计、模块边界、演进路线的权威参考。按专题查找，不要从这里开始读——先从 [角色入口](../roles/README.md) 或 [能力线入口](../tracks/README.md) 找到你的场景，再来这里深入。

---

## 架构文档分层

| 层次 | 说明 | 文档 |
|------|------|------|
| **系统全景** | 整体蓝图、业务架构、系统架构 | 见下方"系统全景"节 |
| **检索与 Agent** | 独立 Agent 知识与检索设计 | 见下方"检索与 Agent"节 |
| **风险审查** | 语义增强、embedding/pgvector 实现 | 见下方"风险审查"节 |
| **仿写控制层** | 0509 最新：控制层架构、运营闭环、实现状态 | 见下方"仿写控制层（0509）"节 |

---

## 下一代架构：Loom

> Loom 是在当前架构基础上的升级层，不替换现有系统。
> 与 0509 仿写控制层的冲突点和对齐方案，见专项分析文档。

| 文档 | 说明 |
|------|------|
| [../loom/README.md](../loom/README.md) | Loom 架构总入口 |
| [../loom/arch-diff-and-alignment.md](../loom/arch-diff-and-alignment.md) | **0509 vs Loom 冲突点与对齐方案**（必读） |
| [../loom/overview.md](../loom/overview.md) | 完整架构图 + SOTA 对比表 |
| [../loom/roadmap.md](../loom/roadmap.md) | Phase 1/2/3 开发路线图 |

---

| 文档 | 说明 |
|------|------|
| [ai-novel-system-blueprint.md](./ai-novel-system-blueprint.md) | 系统蓝图（最高层全景图） |
| [novel-assistant-system-architecture.md](./novel-assistant-system-architecture.md) | 系统架构详解（模块与数据流） |
| [novel-assistant-business-architecture.md](./novel-assistant-business-architecture.md) | 业务架构（角色、流程、价值链） |

---

## 检索与 Agent

| 文档 | 说明 |
|------|------|
| [independent-agent-knowledge-and-retrieval.md](./independent-agent-knowledge-and-retrieval.md) | 独立 Agent 知识体系与检索设计 |

---

## 风险审查

| 文档 | 说明 |
|------|------|
| [risk-audit-completion-status.md](./risk-audit-completion-status.md) | 风险审查完成度 / 测试 / 使用说明 |
| [risk-audit-semantic-enhancement.md](./risk-audit-semantic-enhancement.md) | 语义增强设计（为什么分层、如何演进） |
| [risk-audit-embedding-pgvector-implementation-spec.md](./risk-audit-embedding-pgvector-implementation-spec.md) | ONNX embedding + pgvector 实现规范 |
| [../risk-audit-production-readiness.md](../risk-audit-production-readiness.md) | 风险审查生产就绪状态 |

---

## 仿写控制层（0509 最新）

> 这批文档描述当前仿写商业 Agent 控制层的完整架构与演进路线，是 0509 最新产出。

### 先看哪份？

- **不熟悉控制层** → 先看 [实现状态图](./imitation-control-plane-implementation-status-map-20260509.md)（✅/🟡/🔴 一目了然）
- **想看完整架构** → 看 [控制层架构图](./imitation-commercial-agent-control-plane-architecture-20260509.md)
- **产品/运营视角** → 看 [运营闭环](./imitation-commercial-agent-ops-closed-loop-20260509.md)
- **前端/接入视角** → 看 [字段→产物→控制台映射](./imitation-control-plane-field-artifact-console-map-20260509.md)
- **维护/退场路线** → 看 [legacy retirement 路线图](./imitation-legacy-retirement-roadmap-20260509.md)
- **下一步执行** → 看 [live mutation bridge 路线图](./imitation-live-mutation-bridge-roadmap-20260509.md)

### 文档清单

| 文档 | 说明 | 适合角色 |
|------|------|---------|
| [imitation-commercial-agent-control-plane-architecture-20260509.md](./imitation-commercial-agent-control-plane-architecture-20260509.md) | 完整控制层架构图（innovation experiment → session → operator → action → execution → replay/apply/resume → primary/legacy → retirement） | 架构师、后端 |
| [imitation-commercial-agent-ops-closed-loop-20260509.md](./imitation-commercial-agent-ops-closed-loop-20260509.md) | 商业运营闭环视角（为什么已经不是 demo） | 产品、架构师 |
| [imitation-control-plane-implementation-status-map-20260509.md](./imitation-control-plane-implementation-status-map-20260509.md) | 实现状态图（✅已落地 / 🟡预演中 / 🔴未实现） | 所有人 |
| [imitation-control-plane-field-artifact-console-map-20260509.md](./imitation-control-plane-field-artifact-console-map-20260509.md) | 字段层→产物层→控制台层 三层映射 | 前端、接入者、产品 |
| [imitation-legacy-retirement-roadmap-20260509.md](./imitation-legacy-retirement-roadmap-20260509.md) | legacy 字段 retirement 路线（readiness → plan → pilot wave → preview → patch） | 后端、维护者 |
| [imitation-live-mutation-bridge-roadmap-20260509.md](./imitation-live-mutation-bridge-roadmap-20260509.md) | 从当前 preview/governance 到第一次真实 live mutation 还差哪几步 | 架构师、后端 |

### 配套文档（docs 根目录）

| 文档 | 说明 |
|------|------|
| [../imitation-control-plane-glossary.md](../imitation-control-plane-glossary.md) | 控制层术语表（control plane / runtime / governance / retirement 等，0509 更新） |
| [../writer-imitation-workflow.md](../writer-imitation-workflow.md) | 实战工作流（已更新引用所有 0509 文档） |
| [../imitation-next-dev-handoff.md](../imitation-next-dev-handoff.md) | 下一阶段开发交接（0509 完整新增产物清单 + P1/P2/P3） |

---

## 仿写 Harness（基础架构）

| 文档 | 说明 |
|------|------|
| [chapter-imitation-harness-architecture.md](./chapter-imitation-harness-architecture.md) | 章节仿写 Harness 架构（skills pipeline + harness controller + preflight + risk audit） |

---

返回 [文档中心](../README.md)
