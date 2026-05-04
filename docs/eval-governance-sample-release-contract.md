# Eval Governance Sample Release Contract

This contract keeps the retrieval/rerank/risk/generation lanes releasable without adding UI scope.
It is intentionally sample-based and deterministic so CI can run it before a freeze or handoff.

## Stable lane contracts

| Lane | Stable contract | Required sample signal |
| --- | --- | --- |
| retrieval | `retrieval-search.v1` | hit-rate, MRR, p95 latency |
| rerank | `retrieval-rerank-diagnostics.v1` | NDCG lift / ordering quality, p95 latency |
| risk | `risk-checker-contract.v1` | checker contract pass rate, p95 latency |
| generation | `whole-book-imitation.v1` | overall score and long-book consistency score |

## Freeze policy

A release may freeze only when all required lanes have at least one sample and every lane summary
passes its thresholds. Missing lanes are release blockers, not warnings. Failed lanes require a handoff
note that includes the sample id, metric, observed value, threshold, and whether the failure is a data,
latency, or contract regression.

## Implementation surface

`novel_analyzer.services.eval_governance_service.EvalGovernanceService` aggregates
`SampleEvaluation` records into a `ReleaseReadinessReport`. The report exposes:

- per-lane summaries and blockers;
- stable contract versions to include in handoff docs;
- `freeze_policy.may_freeze`, which is the single release gate for this sample-based layer.

The service does not call models, databases, or network backends; retrieval/rerank/risk/generation
pipelines own sample production and pass normalized metrics into this gate.

## Round 2 cross-lane handoff policy

The cross-lane sample bundle must include retrieval, rerank, risk, and generation lanes
before freeze. Missing or below-threshold lanes keep `overall_status=blocked`, set
`freeze_policy.handoff_required=true`, and enumerate blockers for the release handoff.
