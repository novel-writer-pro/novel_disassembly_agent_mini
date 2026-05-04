# Architecture Upgrade Round 2 Evidence Pack

This pack records the testable closure points for the second-round middle-layer
upgrade. It intentionally avoids UI changes and keeps the checker contracts stable.

## Retrieval / RRF / rerank lane

- Contract source: `docs/retrieval-rrf-rerank-contract.md`.
- Evaluation source: `docs/retrieval-rrf-rerank-eval.md`.
- Runtime assertions: `tests/test_retrieval_service.py` covers single-lane compatibility,
  reciprocal-rank fusion ordering, diagnostics shape, and rerank fallback behavior.
- Freeze rule: `RetrievalService.search_branch(...)` remains the QA-compatible public
  method; evaluators use `search_branch_with_diagnostics(...)` for raw/fused/reranked
  evidence without changing UI payloads.

## Risk semantic lane

- Canonical identity now lives in each semantic signal's `metadata_json.canonical_key`.
  It is derived from `signal_type + normalized text` so later embeddings or clusters can
  reuse a stable key without changing the checker result contract.
- Evidence reasons live in `metadata_json.evidence_reason` for artifact/checker-derived
  signals, and link candidates include `evidence_json.candidate_reason` plus both endpoint
  canonical keys.
- Runtime assertions: `tests/test_risk_signal_store_service.py` verifies canonical keys,
  evidence reasons, and candidate-link samples while leaving checker verdict schemas
  unchanged.

## Whole-book imitation / generation lane

- Whole-book execution now publishes `long_book_consistency_diagnostics` in both
  `policy_summary` and `dashboard_summary`.
- The diagnostic bundle counts weak repair lanes (`style` remains represented through
  chapter imitation scores, while rhythm/dialogue/reader/research are explicit action
  families), records carry-over gaps, and sets `requires_consistency_pass` for handoff.
- Runtime assertions: `tests/test_whole_book_imitation_service.py` verifies the diagnostic
  contract on the sandbox whole-book main chain.

## Eval / governance lane

- Contract source: `docs/eval-governance-sample-release-contract.md`.
- Runtime assertions: `tests/test_eval_governance_service.py` covers pass/block release
  decisions, missing lanes, contract versions, and freeze policy output.
- Freeze policy: a release may freeze only when every required lane has samples meeting
  thresholds; otherwise handoff remains required and blockers are enumerated.

## Handoff checklist

1. Run focused tests for retrieval, risk semantic, imitation/generation, and eval governance.
2. Run full type check (`mypy novel_analyzer`) before release handoff.
3. Run lint on modified files and keep this lane UI-free.
4. Attach this evidence pack to the release handoff note with command output.
