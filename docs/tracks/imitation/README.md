# 仿写能力线文档入口

> 本页覆盖从单章仿写到全书仿写、创新导向实验、商业 Agent 控制层的完整文档链。

---

## 阅读路径选择

| 我想做什么 | 从这里开始 |
|-----------|-----------|
| 快速跑单章仿写 | [writer-imitation-workflow.md](../../writer-imitation-workflow.md) |
| 理解仿写方法论 | [chapter-imitation-method.md](../../chapter-imitation-method.md) |
| 接入全书仿写 API | [whole-book-imitation-integration-quickstart.md](../../whole-book-imitation-integration-quickstart.md) |
| 引入创新导向 | [imitation-innovation-and-steering.md](../../imitation-innovation-and-steering.md) |
| 理解控制层架构 | [architecture/imitation-commercial-agent-control-plane-architecture-20260509.md](../../architecture/imitation-commercial-agent-control-plane-architecture-20260509.md) |
| 看哪些能力已落地 | [architecture/imitation-control-plane-implementation-status-map-20260509.md](../../architecture/imitation-control-plane-implementation-status-map-20260509.md) |
| 看不懂英文术语 | [imitation-control-plane-glossary.md](../../imitation-control-plane-glossary.md) |
| 接手/继续开发 | [imitation-next-dev-handoff.md](../../imitation-next-dev-handoff.md) |

---

## 第一层：方法论与基础

1. [chapter-imitation-method.md](../../chapter-imitation-method.md) — 章节仿写方法论（输入输出、约束、评估）
2. [chapter-planning-capability-proposal.md](../../chapter-planning-capability-proposal.md) — 章节规划能力提案
3. [architecture/chapter-imitation-harness-architecture.md](../../architecture/chapter-imitation-harness-architecture.md) — Harness 架构（推荐生产路线）
4. [chapter-imitation-ch3-live-report-20260502.md](../../chapter-imitation-ch3-live-report-20260502.md) — 第3章 live 实验报告（D层证据）
5. [chapter-imitation-capability-matrix.md](../../chapter-imitation-capability-matrix.md) — 能力矩阵

---

## 第二层：日常仿写工作流

6. [writer-imitation-workflow.md](../../writer-imitation-workflow.md) — 实战工作流（CLI 命令、output 目录管理）⭐ 最新 0509
7. [reader-sim-review-usage.md](../../reader-sim-review-usage.md) — 模拟读者阅读 / reader sim 使用说明

---

## 第三层：创新导向与实验

8. [imitation-innovation-and-steering.md](../../imitation-innovation-and-steering.md) — 创新导向与 steering 说明
9. [trope-worldview-rag-library-format.md](../../trope-worldview-rag-library-format.md) — Trope/Worldview RAG 库格式
10. [batch-innovation-experiment-workflow.md](../../batch-innovation-experiment-workflow.md) — 批量创新实验工作流

---

## 第四层：全书仿写

11. [whole-book-imitation-docs-index.md](../../whole-book-imitation-docs-index.md) — 全书仿写文档索引（全景）
12. [whole-book-imitation-integration-quickstart.md](../../whole-book-imitation-integration-quickstart.md) — 接入快速入门
13. [whole-book-imitation-api-stability-summary.md](../../whole-book-imitation-api-stability-summary.md) — API 稳定字段收口
14. [whole-book-imitation-api-versioning.md](../../whole-book-imitation-api-versioning.md) — API 版本化策略
15. [whole-book-imitation-api-freeze-readiness.md](../../whole-book-imitation-api-freeze-readiness.md) — API 冻结就绪判断
16. [whole-book-imitation-freeze-evidence-20260503.md](../../whole-book-imitation-freeze-evidence-20260503.md) — 冻结证据（D层）
17. [whole-book-imitation-provider-recovery-checklist.md](../../whole-book-imitation-provider-recovery-checklist.md) — Provider 恢复 checklist
18. [whole-book-imitation-handoff-brief.md](../../whole-book-imitation-handoff-brief.md) — 全书仿写交接说明

---

## 第五层：商业 Agent 控制层（0509 最新）

> 这批文档描述当前仿写控制层从 preview 走向商业可运营闭环的架构与路线。

| 文档 | 用途 | 适合谁看 |
|------|------|---------|
| [imitation-commercial-agent-control-plane-architecture-20260509.md](../../architecture/imitation-commercial-agent-control-plane-architecture-20260509.md) | 完整控制层架构图（最新全景） | 架构师、后端 |
| [imitation-commercial-agent-ops-closed-loop-20260509.md](../../architecture/imitation-commercial-agent-ops-closed-loop-20260509.md) | 商业运营闭环视角（为什么不是 demo） | 产品、架构师 |
| [imitation-control-plane-implementation-status-map-20260509.md](../../architecture/imitation-control-plane-implementation-status-map-20260509.md) | ✅/🟡/🔴 哪些已落地、哪些 preview、哪些未做 | 所有人 |
| [imitation-control-plane-field-artifact-console-map-20260509.md](../../architecture/imitation-control-plane-field-artifact-console-map-20260509.md) | 字段→产物→控制台 三层映射 | 前端、接入者 |
| [imitation-legacy-retirement-roadmap-20260509.md](../../architecture/imitation-legacy-retirement-roadmap-20260509.md) | legacy 字段 retirement 路线（readiness→pilot→patch） | 后端、维护者 |
| [imitation-live-mutation-bridge-roadmap-20260509.md](../../architecture/imitation-live-mutation-bridge-roadmap-20260509.md) | 从当前 preview 到第一次真实 live mutation 还差什么 | 架构师、后端 |

---

## 第六层：术语与交接

19. [imitation-control-plane-glossary.md](../../imitation-control-plane-glossary.md) — 控制层术语表（control plane / runtime / governance 等）⭐ 0509 更新
20. [imitation-next-dev-handoff.md](../../imitation-next-dev-handoff.md) — 下一阶段开发交接（当前完成状态 + P1/P2/P3 优先级）⭐ 0509 更新

---

## 当前能力边界

- ✅ 单章仿写：规划、草案、比较、review、gate、risk、迭代优化
- ✅ 多章一致性摘要
- ✅ Whole-book orchestration + sandbox execute
- ✅ 创新导向 steering（worldview/trope/audience）
- ✅ 商业 Agent 控制层（session state → operator surface → action queue → execution → replay/apply/resume）
- ✅ Primary/Legacy 双层治理 + retirement preview
- 🟡 Primary-first display policy（过渡中）
- 🔴 真实 live mutation / checkpoint writeback（未实现）
- 🔴 External runtime executor（未实现）
- 限制：生成正文不会直接写入 live branch artifact

---

返回 [能力线导航](../README.md) | [文档中心](../../README.md)
