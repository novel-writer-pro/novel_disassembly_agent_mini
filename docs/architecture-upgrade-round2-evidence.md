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

## 2026-05-04 fresh sample rerun evidence

- Whole-book readiness against sample branch `62e636f0-c901-4167-aa1c-aff3da9c83ef`
  (DB `novel_analyzer`) succeeded and reported:
  - `whole_book_contract_version = whole-book-imitation.v1`
  - `chapter_analysis_count = 11`
  - provider health currently `degraded`, with latest error `503 Service temporarily unavailable`
- Whole-book sandbox rerun on the same branch succeeded:
  - output: `/tmp/whole-book-sandbox-rerun-20260504.json`
  - `execution_mode = sandbox_execute`
  - `executed_steps = 2`
  - dashboard includes `repair_lane_diagnostics`, `long_book_consistency_diagnostics`, and `book_handoff_summary`
- Whole-book provider-backed rerun on the same branch also succeeded with `--use-llm`:
  - output: `/tmp/whole-book-provider-rerun-20260504.json`
  - `execution_mode = sandbox_execute`
  - `executed_steps = 2`
  - chapter 2: `overall_score = 84`, `overall_risk_level = low`, `stop_reason = quality_iteration_required`
  - chapter 3: `overall_score = 84`, `overall_risk_level = low`, `stop_reason = critical_action_required`
  - despite readiness still reporting provider health `degraded`, the live provider path was reachable for this rerun
- Branch validation succeeded:
  - `validate-branch 62e636f0-c901-4167-aa1c-aff3da9c83ef` → `issue_count=0`
- Sample branch Markdown report rerun initially failed on legacy DB review tables that lacked
  `review_actor` / older event-history columns; leader patched `ClusterReviewService` to read
  legacy schemas with `review_owner` fallback and the report rerun then succeeded:
  - output: `/tmp/sample-branch-report-20260504.md`
  - report confirms `completed_chapters = 10`, `failed_jobs = 0`, `running_jobs = 0`,
    `next_chapter = 11`, and review storage remains on the DB path.
