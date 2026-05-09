# 仿写 / 创作角色入口

**适合场景：**
- 做章节仿写或全书仿写
- 引入创新导向（新世界观、套路、创新实验）
- 把仿写链接入 agentOS 或下游系统
- 了解商业 Agent 控制层架构（0509 最新）

---

## 我想做什么？

| 场景 | 入口 |
|------|------|
| 快速跑单章仿写 | [writer-imitation-workflow.md](../../writer-imitation-workflow.md) |
| 理解仿写方法论 | [chapter-imitation-method.md](../../chapter-imitation-method.md) |
| 接入全书仿写 API | [whole-book-imitation-integration-quickstart.md](../../whole-book-imitation-integration-quickstart.md) |
| 引入创新导向 | [imitation-innovation-and-steering.md](../../imitation-innovation-and-steering.md) |
| 看控制层完整架构 | [architecture/imitation-commercial-agent-control-plane-architecture-20260509.md](../../architecture/imitation-commercial-agent-control-plane-architecture-20260509.md) |
| 看哪些能力已落地 | [architecture/imitation-control-plane-implementation-status-map-20260509.md](../../architecture/imitation-control-plane-implementation-status-map-20260509.md) |
| 看不懂英文术语 | [imitation-control-plane-glossary.md](../../imitation-control-plane-glossary.md) |
| 接手/继续开发 | [imitation-next-dev-handoff.md](../../imitation-next-dev-handoff.md) |

---

## 推荐阅读顺序

### 第一步：方法论

1. [chapter-imitation-method.md](../../chapter-imitation-method.md) — 章节仿写方法论
2. [architecture/chapter-imitation-harness-architecture.md](../../architecture/chapter-imitation-harness-architecture.md) — Harness 架构（推荐生产路线）
3. [chapter-planning-capability-proposal.md](../../chapter-planning-capability-proposal.md) — 章节规划能力提案

### 第二步：日常工作流

4. [writer-imitation-workflow.md](../../writer-imitation-workflow.md) — 实战工作流（CLI 命令、output 目录）⭐ 0509 更新
5. [reader-sim-review-usage.md](../../reader-sim-review-usage.md) — 模拟读者阅读使用说明

### 第三步：创新导向

6. [imitation-innovation-and-steering.md](../../imitation-innovation-and-steering.md) — 创新导向与 steering
7. [trope-worldview-rag-library-format.md](../../trope-worldview-rag-library-format.md) — Trope/Worldview RAG 库格式
8. [batch-innovation-experiment-workflow.md](../../batch-innovation-experiment-workflow.md) — 批量创新实验工作流

### 第四步：全书仿写

9. [whole-book-imitation-docs-index.md](../../whole-book-imitation-docs-index.md) — 全书仿写文档索引
10. [whole-book-imitation-integration-quickstart.md](../../whole-book-imitation-integration-quickstart.md) — 接入快速入门
11. [whole-book-imitation-api-stability-summary.md](../../whole-book-imitation-api-stability-summary.md) — API 稳定字段收口

### 第五步：商业 Agent 控制层（0509 最新）

12. [architecture/imitation-control-plane-implementation-status-map-20260509.md](../../architecture/imitation-control-plane-implementation-status-map-20260509.md) — ✅/🟡/🔴 实现状态（先看这个）
13. [architecture/imitation-commercial-agent-control-plane-architecture-20260509.md](../../architecture/imitation-commercial-agent-control-plane-architecture-20260509.md) — 完整控制层架构图
14. [architecture/imitation-commercial-agent-ops-closed-loop-20260509.md](../../architecture/imitation-commercial-agent-ops-closed-loop-20260509.md) — 商业运营闭环视角
15. [architecture/imitation-control-plane-field-artifact-console-map-20260509.md](../../architecture/imitation-control-plane-field-artifact-console-map-20260509.md) — 字段→产物→控制台映射
16. [architecture/imitation-legacy-retirement-roadmap-20260509.md](../../architecture/imitation-legacy-retirement-roadmap-20260509.md) — legacy retirement 路线
17. [architecture/imitation-live-mutation-bridge-roadmap-20260509.md](../../architecture/imitation-live-mutation-bridge-roadmap-20260509.md) — 到第一次 live mutation 还差什么

### 第六步：术语与交接

18. [imitation-control-plane-glossary.md](../../imitation-control-plane-glossary.md) — 控制层术语表（0509 更新）
19. [imitation-next-dev-handoff.md](../../imitation-next-dev-handoff.md) — 下一阶段开发交接（P1/P2/P3）

---

## 当前能力边界

- ✅ 单章仿写：规划、草案、比较、review、gate、risk、迭代优化
- ✅ 多章一致性摘要
- ✅ Whole-book orchestration + sandbox execute
- ✅ 创新导向 steering（worldview/trope/audience）
- ✅ 商业 Agent 控制层（session → operator → action → execution → replay/apply/resume）
- ✅ Primary/Legacy 双层治理 + retirement preview
- 🟡 Primary-first display policy（过渡中）
- 🔴 真实 live mutation / checkpoint writeback（未实现）
- 限制：生成正文不会直接写入 live branch artifact

---

返回 [角色导航](../README.md) | [能力线导航](../../tracks/imitation/README.md) | [文档中心](../../README.md)
