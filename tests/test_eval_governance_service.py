import json
from pathlib import Path

from novel_analyzer.services.eval_governance_service import (
    CrossLaneSampleBundle,
    EvalGovernanceService,
    SampleEvaluation,
)


def _passing_samples() -> list[SampleEvaluation]:
    return [
        SampleEvaluation(
            lane="retrieval",
            sample_id="retrieval-hit-1",
            metric_scores={"hit_rate": 1.0, "mrr": 0.9},
            latency_ms=420.0,
        ),
        SampleEvaluation(
            lane="rerank",
            sample_id="rerank-ndcg-1",
            metric_scores={"ndcg": 0.82},
            latency_ms=780.0,
        ),
        SampleEvaluation(
            lane="risk",
            sample_id="risk-contract-1",
            metric_scores={"checker_contract_pass_rate": 1.0},
            latency_ms=230.0,
        ),
        SampleEvaluation(
            lane="generation",
            sample_id="whole-book-1",
            metric_scores={"overall_score": 86.0, "consistency_score": 82.0},
            latency_ms=0.0,
        ),
    ]


def test_eval_governance_service_passes_complete_sample_release() -> None:
    report = EvalGovernanceService.evaluate_release_readiness(_passing_samples())

    assert report.overall_status == "pass"
    assert report.freeze_policy["may_freeze"] is True
    assert report.stable_contracts["retrieval"] == "retrieval-search.v1"
    assert report.lane_summaries["generation"].passed is True
    assert report.lane_summaries["retrieval"].metric_averages["hit_rate"] == 1.0


def test_eval_governance_service_blocks_missing_and_under_threshold_lanes() -> None:
    samples = [
        SampleEvaluation(
            lane="retrieval",
            sample_id="retrieval-hit-1",
            metric_scores={"hit_rate": 0.50, "mrr": 0.40},
            latency_ms=2400.0,
        ),
    ]
    report = EvalGovernanceService.evaluate_release_readiness(samples)

    assert report.overall_status == "blocked"
    assert report.freeze_policy["may_freeze"] is False
    assert "rerank.samples missing" in report.release_blockers
    assert any("retrieval.hit_rate" in blocker for blocker in report.release_blockers)
    assert any("retrieval.latency_p95_ms" in blocker for blocker in report.release_blockers)


def test_eval_governance_cross_lane_sample_bundle_matches_freeze_policy() -> None:
    payload = json.loads(
        Path("docs/examples/eval-governance-cross-lane-bundle.sample.json").read_text()
    )
    bundle = CrossLaneSampleBundle.from_mapping(payload)

    report = EvalGovernanceService.evaluate_sample_bundle(bundle)

    assert report.overall_status == "pass"
    assert report.freeze_policy["may_freeze"] is True
    assert report.freeze_policy["policy_version"] == "eval-governance-freeze.v1"
    assert report.freeze_policy["bundle_id"] == "eval-governance-cross-lane-20260504"
    assert report.freeze_policy["sample_count"] == 4
    assert report.freeze_policy["sample_count_by_lane"] == {
        "generation": 1,
        "rerank": 1,
        "retrieval": 1,
        "risk": 1,
    }
    assert set(report.freeze_policy["required_lanes"]) == {
        "generation",
        "rerank",
        "retrieval",
        "risk",
    }
    assert report.lane_summaries["rerank"].metric_averages["ndcg"] == 0.82
