# 架构专题文档入口

当前建议优先看：

1. [`./risk-audit-completion-status.md`](./risk-audit-completion-status.md)
2. [`./risk-audit-semantic-enhancement.md`](./risk-audit-semantic-enhancement.md)
3. [`./risk-audit-embedding-pgvector-implementation-spec.md`](./risk-audit-embedding-pgvector-implementation-spec.md)
4. [`../risk-audit-production-readiness.md`](../risk-audit-production-readiness.md)
5. [`../risk-audit-runtime-architecture.md`](../risk-audit-runtime-architecture.md)
6. [`../skills-vs-risk-checkers-boundary.md`](../skills-vs-risk-checkers-boundary.md)
7. [`./chapter-imitation-harness-architecture.md`](./chapter-imitation-harness-architecture.md)
8. [`./imitation-commercial-agent-control-plane-architecture-20260509.md`](./imitation-commercial-agent-control-plane-architecture-20260509.md)
9. [`./imitation-commercial-agent-ops-closed-loop-20260509.md`](./imitation-commercial-agent-ops-closed-loop-20260509.md)
10. [`./imitation-control-plane-implementation-status-map-20260509.md`](./imitation-control-plane-implementation-status-map-20260509.md)
11. [`./imitation-control-plane-field-artifact-console-map-20260509.md`](./imitation-control-plane-field-artifact-console-map-20260509.md)
12. [`./imitation-legacy-retirement-roadmap-20260509.md`](./imitation-legacy-retirement-roadmap-20260509.md)

适合回答：
- 风险审查主链为什么分层
- embedding / pgvector 应该落在哪
- 正式稳定生产还差哪些外部条件
- checker 为什么保持规则化判定
- LLM 为什么只做目标式复核
- 仿写能力为什么必须引入 skills + harness controller
- 当前仿写商业 Agent 控制层为什么已经不是 demo，而是在向可运营控制台结构演进
- 当前仿写商业 Agent 控制层距离真正商业运营闭环还差哪些环节
- 当前控制层哪些层已经落地，哪些还只是 preview / 规划目标
- 当前字段层、产物层、控制台层之间到底如何映射
- 当前 legacy 字段真正 retirement 前要经过哪些步骤
