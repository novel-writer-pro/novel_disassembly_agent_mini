# Independent Agent Capability Checkout — 2026-05-05

## 1. 本轮范围
- retrieval diagnostics CLI
- entity_exact / vector recall routes
- author-facing independent knowledge layer
- 目标：为未来独立 agent / OpenClaw 抽离准备稳定能力层

## 2. 当前已完成
- `search-branch-diagnostics` 已可直接暴露 raw/reranked/route/latency。
- retrieval 主链已纳入 `entity_exact` 与 `vector` 召回。
- `AuthorKnowledgeService` 已支持 chapter range / focus label / entity/rule/relation/thread 聚合。
- CLI 已支持 `show-author-knowledge` / `export-author-knowledge`。
- 已新增 `NovelAssistantService`，统一输出 branch snapshot / risk/review / retrieval diagnostics / author knowledge / whole-book readiness / preparation guidance。

## 3. 解决的问题
- 之前：能力存在于 service 内，但不够独立、也不够可用。
- 现在：能力已经能独立调用、独立测试、独立交接。

## 4. 当前测试 / 评估
- targeted retrieval + author knowledge + CLI regression 通过。
- second provider-backed success-density 样例尝试被外部 `403 SUBSCRIPTION_NOT_FOUND` 阻塞，不属于本地能力缺陷。
- DeepSeek provider-backed success-density 样例已成功补到第二轮 whole-book 真实样例。

## 5. 交付物
- `novel_analyzer/services/retrieval_service.py`
- `novel_analyzer/services/author_knowledge_service.py`
- `novel_analyzer/services/novel_assistant_service.py`
- `novel_analyzer/cli/app.py`
- `docs/architecture/independent-agent-knowledge-and-retrieval.md`
- `docs/examples/sample-branch-search-diagnostics-20260505.sample.json`
- `docs/examples/sample-branch-author-knowledge-20260505.sample.json`
- `docs/examples/sample-branch-novel-assistant-20260505.sample.json`

## 6. 下一步闭环
1. retrieval 真实 branch benchmark
2. whole-book / planner 更直接消费 author knowledge
3. assistant pack 的续写/仿写控制入口继续增强
