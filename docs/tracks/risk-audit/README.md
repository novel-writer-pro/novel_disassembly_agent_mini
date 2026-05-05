# 风险审查主线文档入口

主看：
1. [`../../risk-audit-docs-index.md`](../../risk-audit-docs-index.md)
2. [`../../api-current-surface.md`](../../api-current-surface.md)
2. [`../../risk-audit-system-overview.md`](../../risk-audit-system-overview.md)
3. [`../../risk-audit-capability.md`](../../risk-audit-capability.md)
4. [`../../risk-audit-checker-roadmap.md`](../../risk-audit-checker-roadmap.md)
5. [`../../architecture/risk-audit-semantic-enhancement.md`](../../architecture/risk-audit-semantic-enhancement.md)
6. [`../../architecture/risk-audit-embedding-pgvector-implementation-spec.md`](../../architecture/risk-audit-embedding-pgvector-implementation-spec.md)

当前建议的生产向演进路线：
- 先走 `semantic signal builder`
- 再升级为 **ONNX embedding + pgvector**
- checker 保持可解释判定
- LLM 只做目标式复核
