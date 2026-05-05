# Retrieval Checkout — 2026-05-04

## 1. 本轮范围
- 能力线：retrieval / QA / search diagnostics / RRF / rerank
- 关联样例：sample branch `62e636f0-c901-4167-aa1c-aff3da9c83ef`
- 目标用户：作者问答、编辑检索、系统接入方

## 2. 当前已完成
- `RetrievalService.search_branch()` 保持 QA/search 兼容。
- 已具备多路召回融合（RRF）与 optional rerank。
- `search_branch_with_diagnostics()` 已能暴露 raw / reranked / route / latency 证据。
- retrieval related docs/sample/release gate 已接入文档体系。

## 3. 当前未完成
- vector / entity-exact 路线尚未正式并入当前 RRF 主链。
- live PostgreSQL latency / route effectiveness 还缺更系统的 benchmark。
- 作者/编辑视角的 retrieval UX 文档仍偏技术化。

## 4. 预期效果
- 问答与搜索结果更稳、更可解释。
- 检索主链具备可评估、可回退、可灰度升级能力。
- 后续 retrieval 升级不破坏现有 QA/search 消费面。

## 5. 解决的问题
- 之前：retrieval 有结果，但 raw/fused/reranked 之间难观测。
- 现在：评估面与主链已分层，便于持续优化。

## 6. 测试 / 评估状态
- `tests/test_retrieval_service.py` 通过
- `tests/test_qa_service.py` 通过
- 真实 sample branch report / branch validation 已通过
- 当前结论：满足“继续扩召回而不破坏主链”的标准

## 7. 下一步闭环
### 必做
1. vector / entity-exact recall 接入
2. live PG latency evidence
3. retrieval 成功样例密度提升

### 快速可补
1. search result 摘要层
2. retrieval FAQ / operator 文档

## 8. 结论
retrieval 线当前已经从“可用检索”进入“可观测、可评估、可持续优化”的阶段。
