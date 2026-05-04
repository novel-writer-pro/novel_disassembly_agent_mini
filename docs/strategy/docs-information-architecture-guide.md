# Docs Information Architecture Guide

## 1. 文档分层
### Layer A — Canonical entrypoints
- `docs/README.md`
- `docs/roles/**`
- `docs/tracks/**`
- `docs/architecture/README.md`

### Layer B — Strategy / governance
- `docs/features/**`
- `docs/product/**`
- `docs/strategy/**`
- `docs/whitepaper/**`

### Layer C — Technical source-of-truth
- `interface-manifest.md`
- `api-contract.md`
- `api-current-surface.md`
- risk / imitation / review workflow contract docs

### Layer D — Historical evidence and samples
- `docs/examples/**`
- `docs/*-evidence-*.md`
- `.omx/reports/**`

## 2. 维护原则
- 新人先看 A/B 层，深入实施再看 C 层。
- 真实 rerun / fresh sample 优先固化到 D 层。
- 每个 B 层文档都应链接到对应的 C/D 层证据。

## 3. 什么时候新增文档，什么时候只改索引
- 新能力方向 / 新产品叙事：新增文档
- 只是入口混乱：优先改索引，不要重复写内容
- 临时验证：先写 evidence，再决定是否升格为 canonical doc
