# Retrieval RRF + Rerank Evaluation Contract

This note freezes the current middle-layer retrieval upgrade point for QA/search
without changing UI or checker contracts.

## Stable runtime contract

- `RetrievalService.search_branch(branch_id, query, limit)` still returns
  `list[RetrievalHit]` and remains the compatibility entry point for QA.
- `RetrievalService.search_branch_with_diagnostics(...)` is the evaluation entry
  point. It now exposes:
  - `raw_hits`: RRF-fused candidates before cross-encoder rerank.
  - `reranked_hits`: final answer/search candidates.
  - `rerank_applied`: whether the configured reranker successfully ran.
  - `fusion_applied`: whether more than one retrieval route contributed.
  - `route_counts`: per-route candidate counts for sample-based inspection.

## Multi-route retrieval lanes

PostgreSQL retrieval now keeps the existing BM25/FTS behavior and adds stable
parallel candidate lanes before rerank:

1. `fts`: `bm25_vector @@ plainto_tsquery(...)` ranked by `ts_rank_cd` plus
   trigram similarity.
2. `similarity`: trigram similarity fallback against title + retrieval text.
3. `like`: tokenized `ILIKE` fallback for exact-ish Chinese/name matching when
   lexical analyzers miss the query.
4. `keyword`: existing semantic keyword overlap fallback.

The routes are fused with reciprocal rank fusion (RRF) at chapter granularity, so
heterogeneous lane scores are not calibrated against each other. Rerank receives
the fused candidate pool and can still reorder by model relevance.

## Evaluation samples

For every release candidate, run at least these sample classes through
`search_branch_with_diagnostics` and compare `raw_hits` vs `reranked_hits`:

- Entity query: character / faction / place names that should be recoverable by
  `keyword` or `like` even when FTS tokenization is weak.
- Event query: phrase-like plot questions that should favor `fts`.
- Ambiguous query: broad terms such as “命格” or “资源” where cross-route
  consensus should rise before rerank.
- No-hit query: verify empty route counts do not break QA degradation.

Release criteria:

- QA callers do not need code changes.
- `fusion_applied` and `route_counts` are present in diagnostics for observability.
- Rerank failure still falls back to fused raw order.
- Related retrieval tests and full type checks pass.

## Freeze policy

Do not alter `RetrievalHit` fields or `search_branch` return shape without an API
versioning note. New retrieval lanes should be added behind `_search_branch_routes`
and must feed RRF before rerank rather than bypassing QA compatibility.

## Round 2 QA compatibility evidence

The round-2 closure keeps `search_branch(...)` as the public QA-compatible call and
uses `search_branch_with_diagnostics(...)` only for evaluator inspection. Focused tests
in `tests/test_retrieval_service.py` pin single-lane compatibility, RRF consensus ordering,
route counts, and rerank fallback so no UI payload changes are required.
