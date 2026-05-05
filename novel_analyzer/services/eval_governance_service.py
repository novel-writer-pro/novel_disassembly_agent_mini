"""Sample-based evaluation and release-governance helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SampleEvaluation:
    """One deterministic eval sample from a retrieval/risk/generation lane."""

    lane: str
    sample_id: str
    metric_scores: dict[str, float]
    latency_ms: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CrossLaneSampleBundle:
    """Deterministic sample bundle covering every release-governed lane."""

    bundle_id: str
    generated_at: str
    samples: list[SampleEvaluation]
    source_documents: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> CrossLaneSampleBundle:
        """Build a bundle from the documented JSON sample-bundle shape."""

        samples = [
            SampleEvaluation(
                lane=str(sample["lane"]),
                sample_id=str(sample["sample_id"]),
                metric_scores={
                    str(metric_name): float(metric_value)
                    for metric_name, metric_value in sample.get("metric_scores", {}).items()
                },
                latency_ms=float(sample.get("latency_ms", 0.0)),
                notes=[str(note) for note in sample.get("notes", [])],
            )
            for sample in payload.get("samples", [])
        ]
        return cls(
            bundle_id=str(payload["bundle_id"]),
            generated_at=str(payload["generated_at"]),
            samples=samples,
            source_documents=[str(path) for path in payload.get("source_documents", [])],
            notes=[str(note) for note in payload.get("notes", [])],
        )


@dataclass(frozen=True, slots=True)
class LaneEvaluationSummary:
    """Aggregated release signal for one lane."""

    lane: str
    sample_count: int
    passed: bool
    metric_averages: dict[str, float]
    latency_p95_ms: float
    blockers: list[str]


@dataclass(frozen=True, slots=True)
class ReleaseReadinessReport:
    """Stable contract and freeze-policy verdict for evaluated samples."""

    overall_status: str
    lane_summaries: dict[str, LaneEvaluationSummary]
    release_blockers: list[str]
    stable_contracts: dict[str, str]
    freeze_policy: dict[str, object]
    cross_lane_sample_bundle: dict[str, object]
    handoff_summary: dict[str, object]


class EvalGovernanceService:
    """Evaluate sample sets against lane-specific release criteria."""

    DEFAULT_THRESHOLDS: dict[str, dict[str, float]] = {
        "retrieval": {"hit_rate": 0.80, "mrr": 0.65, "latency_p95_ms": 1500.0},
        "rerank": {"ndcg": 0.70, "latency_p95_ms": 2500.0},
        "risk": {"checker_contract_pass_rate": 0.95, "latency_p95_ms": 1000.0},
        "generation": {"overall_score": 80.0, "consistency_score": 75.0, "latency_p95_ms": 0.0},
    }

    DEFAULT_STABLE_CONTRACTS: dict[str, str] = {
        "retrieval": "retrieval-search.v1",
        "rerank": "retrieval-rerank-diagnostics.v1",
        "risk": "risk-checker-contract.v1",
        "generation": "whole-book-imitation.v1",
    }


    @classmethod
    def build_cross_lane_sample_bundle(
        cls,
        samples: list[SampleEvaluation],
        *,
        required_lanes: list[str] | None = None,
    ) -> dict[str, object]:
        """Build a deterministic handoff bundle spanning retrieval/risk/generation lanes."""

        lanes = required_lanes or sorted(cls.DEFAULT_THRESHOLDS)
        by_lane: dict[str, list[SampleEvaluation]] = {lane: [] for lane in lanes}
        for sample in samples:
            if sample.lane in by_lane:
                by_lane[sample.lane].append(sample)
        lane_samples = {
            lane: [sample.sample_id for sample in sorted(items, key=lambda item: item.sample_id)]
            for lane, items in by_lane.items()
        }
        missing_lanes = [lane for lane, items in lane_samples.items() if not items]
        return {
            "bundle_contract": "cross-lane-eval-sample-bundle.v1",
            "required_lanes": lanes,
            "lane_samples": lane_samples,
            "missing_lanes": missing_lanes,
            "sample_count": sum(len(items) for items in lane_samples.values()),
            "release_evidence_order": [
                "retrieval.diagnostics",
                "rerank.rrf",
                "risk.semantic_checker_contract",
                "generation.whole_book_consistency",
            ],
        }

    @staticmethod
    def _percentile_95(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = max(0, min(len(ordered) - 1, int((len(ordered) * 0.95) - 1)))
        return ordered[index]

    @classmethod
    def _summarize_lane(
        cls,
        lane: str,
        samples: list[SampleEvaluation],
        thresholds: dict[str, float],
    ) -> LaneEvaluationSummary:
        metric_names = sorted({name for sample in samples for name in sample.metric_scores})
        metric_averages = {
            name: sum(sample.metric_scores.get(name, 0.0) for sample in samples) / len(samples)
            for name in metric_names
        }
        latency_p95_ms = cls._percentile_95([sample.latency_ms for sample in samples])
        blockers: list[str] = []
        for metric_name, threshold in thresholds.items():
            if metric_name == "latency_p95_ms":
                if threshold > 0.0 and latency_p95_ms > threshold:
                    blockers.append(
                        f"{lane}.latency_p95_ms {latency_p95_ms:.1f} exceeds {threshold:.1f}"
                    )
                continue
            actual = metric_averages.get(metric_name, 0.0)
            if actual < threshold:
                blockers.append(f"{lane}.{metric_name} {actual:.3f} below {threshold:.3f}")
        return LaneEvaluationSummary(
            lane=lane,
            sample_count=len(samples),
            passed=not blockers,
            metric_averages=metric_averages,
            latency_p95_ms=latency_p95_ms,
            blockers=blockers,
        )

    @classmethod
    def evaluate_sample_bundle(
        cls,
        bundle: CrossLaneSampleBundle,
        *,
        thresholds: dict[str, dict[str, float]] | None = None,
        stable_contracts: dict[str, str] | None = None,
    ) -> ReleaseReadinessReport:
        """Evaluate a documented cross-lane bundle and stamp freeze metadata."""

        report = cls.evaluate_release_readiness(
            bundle.samples,
            thresholds=thresholds,
            stable_contracts=stable_contracts,
        )
        freeze_policy = {
            **report.freeze_policy,
            "policy_version": "eval-governance-freeze.v1",
            "bundle_id": bundle.bundle_id,
            "bundle_generated_at": bundle.generated_at,
            "sample_count": len(bundle.samples),
            "sample_count_by_lane": {
                lane: summary.sample_count for lane, summary in report.lane_summaries.items()
            },
            "source_documents": bundle.source_documents,
            "required_handoff_sections": [
                "bundle_id",
                "stable_contracts",
                "lane_summaries",
                "release_blockers",
                "freeze_policy.may_freeze",
            ],
        }
        return ReleaseReadinessReport(
            overall_status=report.overall_status,
            lane_summaries=report.lane_summaries,
            release_blockers=report.release_blockers,
            stable_contracts=report.stable_contracts,
            freeze_policy=freeze_policy,
            cross_lane_sample_bundle=report.cross_lane_sample_bundle,
            handoff_summary=report.handoff_summary,
        )

    @classmethod
    def evaluate_release_readiness(
        cls,
        samples: list[SampleEvaluation],
        *,
        thresholds: dict[str, dict[str, float]] | None = None,
        stable_contracts: dict[str, str] | None = None,
    ) -> ReleaseReadinessReport:
        effective_thresholds = thresholds or cls.DEFAULT_THRESHOLDS
        effective_contracts = stable_contracts or cls.DEFAULT_STABLE_CONTRACTS
        by_lane: dict[str, list[SampleEvaluation]] = {}
        for sample in samples:
            by_lane.setdefault(sample.lane, []).append(sample)

        lane_summaries: dict[str, LaneEvaluationSummary] = {}
        release_blockers: list[str] = []
        for lane, lane_thresholds in effective_thresholds.items():
            lane_samples = by_lane.get(lane, [])
            if not lane_samples:
                blocker = f"{lane}.samples missing"
                release_blockers.append(blocker)
                lane_summaries[lane] = LaneEvaluationSummary(
                    lane=lane,
                    sample_count=0,
                    passed=False,
                    metric_averages={},
                    latency_p95_ms=0.0,
                    blockers=[blocker],
                )
                continue
            summary = cls._summarize_lane(lane, lane_samples, lane_thresholds)
            lane_summaries[lane] = summary
            release_blockers.extend(summary.blockers)

        cross_lane_sample_bundle = cls.build_cross_lane_sample_bundle(
            samples,
            required_lanes=sorted(effective_thresholds),
        )
        freeze_policy = {
            "may_freeze": not release_blockers,
            "required_lanes": sorted(effective_thresholds),
            "contract_versions": effective_contracts,
            "handoff_required": bool(release_blockers),
            "sample_bundle_contract": cross_lane_sample_bundle["bundle_contract"],
            "freeze_requires_complete_sample_bundle": True,
        }
        handoff_summary = {
            "status": "ready_to_freeze" if not release_blockers else "blocked",
            "missing_lanes": cross_lane_sample_bundle["missing_lanes"],
            "release_blockers": release_blockers,
            "next_actions": [] if not release_blockers else [
                f"补齐/修复 {lane} lane sample"
                for lane in cross_lane_sample_bundle["missing_lanes"]
            ] + release_blockers[:4],
        }
        return ReleaseReadinessReport(
            overall_status="pass" if not release_blockers else "blocked",
            lane_summaries=lane_summaries,
            release_blockers=release_blockers,
            stable_contracts=effective_contracts,
            freeze_policy=freeze_policy,
            cross_lane_sample_bundle=cross_lane_sample_bundle,
            handoff_summary=handoff_summary,
        )
