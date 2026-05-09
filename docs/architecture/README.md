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

适合回答：
- 风险审查主链为什么分层
- embedding / pgvector 应该落在哪
- 正式稳定生产还差哪些外部条件
- checker 为什么保持规则化判定
- LLM 为什么只做目标式复核
- 仿写能力为什么必须引入 skills + harness controller
- 当前仿写商业 Agent 控制层为什么已经不是 demo，而是在向可运营控制台结构演进
