"""Risk-audit orchestration: persist checker results and aggregate chapter risk cards.

Checker implementations live in :mod:`novel_analyzer.services.risk_audit_checkers`
and are re-exported here for backward compatibility.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from time import perf_counter
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    ChapterRiskCardRecord,
    FactRecord,
    GateCheckerResultRecord,
)
from novel_analyzer.domain.schemas import ChapterRiskCard, CheckerResult, GateRiskItem
from novel_analyzer.services.confidence_gated_activation_service import (
    ConfidenceGatedActivationService,
)
from novel_analyzer.services.export_service import ExportService
from novel_analyzer.services.risk_audit_checkers import (
    CharacterOOCChecker,
    ForeshadowPayoffChecker,
    GateChecker,
    PlotLogicChecker,
    PowerScalingChecker,
    RelationshipConsistencyChecker,
    SettingScopeConsistencyChecker,
    ThreadClosureConsistencyChecker,
    TimelineConsistencyChecker,
    WorldRuleConsistencyChecker,
    _dedupe_texts,
    _risk_key,
)
from novel_analyzer.services.risk_evidence_pack_service import RiskEvidencePackService
from novel_analyzer.services.risk_semantic_signal_service import RiskSemanticSignalService
from novel_analyzer.services.risk_signal_cluster_service import RiskSignalClusterService
from novel_analyzer.services.risk_signal_link_service import RiskSignalLinkService
from novel_analyzer.services.risk_signal_store_service import RiskSignalStoreService

__all__ = [
    "CharacterOOCChecker",
    "ForeshadowPayoffChecker",
    "GateChecker",
    "PlotLogicChecker",
    "PowerScalingChecker",
    "RelationshipConsistencyChecker",
    "RiskAuditService",
    "SettingScopeConsistencyChecker",
    "ThreadClosureConsistencyChecker",
    "TimelineConsistencyChecker",
    "WorldRuleConsistencyChecker",
]




class RiskAuditService:
    """Persist checker results and aggregate a unified chapter risk card."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.risk_signal_store = RiskSignalStoreService(session)
        self.risk_signal_link = RiskSignalLinkService(session)
        self.risk_signal_cluster = RiskSignalClusterService(session)
        self.risk_evidence_pack = RiskEvidencePackService(
            session,
            self.risk_signal_store,
            self.risk_signal_link,
            self.risk_signal_cluster,
        )
        self.semantic_signal_lookup: dict[tuple[str, int], list[object]] = {}
        self.checkers: list[GateChecker] = [
            CharacterOOCChecker(),
            WorldRuleConsistencyChecker(),
            RelationshipConsistencyChecker(),
            ForeshadowPayoffChecker(),
            SettingScopeConsistencyChecker(),
            ThreadClosureConsistencyChecker(),
            PlotLogicChecker(),
            TimelineConsistencyChecker(),
            PowerScalingChecker(),
        ]
        for checker in self.checkers:
            if getattr(checker, "name", "") == "foreshadow_payoff_consistency":
                checker.retrieval_search = self.risk_evidence_pack.build_pack  # type: ignore[attr-defined]
            if getattr(checker, "name", "") == "relationship_consistency":
                checker.retrieval_search = self.risk_evidence_pack.build_pack  # type: ignore[attr-defined]
            if getattr(checker, "name", "") == "setting_scope_consistency":
                checker.retrieval_search = self.risk_evidence_pack.build_pack  # type: ignore[attr-defined]
            if getattr(checker, "name", "") == "thread_closure_consistency":
                checker.retrieval_search = self.risk_evidence_pack.build_pack  # type: ignore[attr-defined]
            if getattr(checker, "name", "") == "timeline_consistency":
                checker.retrieval_search = self.risk_evidence_pack.build_pack  # type: ignore[attr-defined]
            if getattr(checker, "name", "") == "power_scaling_consistency":
                checker.retrieval_search = self.risk_evidence_pack.build_pack  # type: ignore[attr-defined]

    @staticmethod
    def _is_missing_relation_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return "relation" in message and "does not exist" in message

    def _artifact_payload(self, branch_id: str, chapter_index: int) -> dict[str, object]:
        artifact = self.session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index == chapter_index)
            .where(ChapterArtifact.visibility == "active")
            .order_by(ChapterArtifact.created_at.desc())
        )
        if artifact is None:
            raise ValueError("chapter artifact not found")
        return cast(dict[str, object], artifact.payload_json)

    def _facts(self, branch_id: str, chapter_index: int) -> list[FactRecord]:
        return list(
            self.session.scalars(
                select(FactRecord)
                .where(FactRecord.branch_id == branch_id)
                .where(FactRecord.chapter_index == chapter_index)
                .order_by(FactRecord.fact_type, FactRecord.label)
            ).all()
        )

    def _replace_checker_result(self, branch_id: str, chapter_index: int, result: CheckerResult) -> GateCheckerResultRecord:
        self.session.execute(
            update(GateCheckerResultRecord)
            .where(GateCheckerResultRecord.branch_id == branch_id)
            .where(GateCheckerResultRecord.chapter_index == chapter_index)
            .where(GateCheckerResultRecord.checker_name == result.checker_name)
            .where(GateCheckerResultRecord.visibility == "active")
            .values(visibility="hidden")
        )
        record = GateCheckerResultRecord(
            branch_id=branch_id,
            chapter_index=chapter_index,
            checker_name=result.checker_name,
            payload_json=result.model_dump(mode="json"),
            status=result.status,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def _replace_risk_card(self, card: ChapterRiskCard) -> ChapterRiskCardRecord:
        self.session.execute(
            update(ChapterRiskCardRecord)
            .where(ChapterRiskCardRecord.branch_id == card.branch_id)
            .where(ChapterRiskCardRecord.chapter_index == card.chapter_index)
            .where(ChapterRiskCardRecord.visibility == "active")
            .values(visibility="hidden")
        )
        record = ChapterRiskCardRecord(
            branch_id=card.branch_id,
            chapter_index=card.chapter_index,
            payload_json=card.model_dump(mode="json"),
            status="ready" if not card.coverage_gaps else "partial",
        )
        self.session.add(record)
        self.session.flush()
        return record

    @staticmethod
    def aggregate(
        *,
        branch_id: str,
        chapter_index: int,
        checker_results: Sequence[CheckerResult],
    ) -> ChapterRiskCard:
        deduped: dict[str, GateRiskItem] = {}
        checker_statuses: dict[str, str] = {}
        coverage_gaps: list[str] = []
        for result in checker_results:
            checker_statuses[result.checker_name] = result.status
            if result.status in {"partial", "failed", "skipped"}:
                coverage_gaps.append(f"{result.checker_name}:{result.status}")
            for risk in result.risks:
                existing = deduped.get(risk.risk_key)
                if existing is None:
                    deduped[risk.risk_key] = risk
                    continue
                existing.supporting_evidence = _dedupe_texts(
                    existing.supporting_evidence + risk.supporting_evidence
                )
                existing.counter_evidence = _dedupe_texts(
                    existing.counter_evidence + risk.counter_evidence
                )
                existing.related_entities = _dedupe_texts(
                    existing.related_entities + risk.related_entities
                )
                existing.related_chapters = sorted(set(existing.related_chapters + risk.related_chapters))
                existing.confidence = max(existing.confidence, risk.confidence)
                severity_rank = {"low": 0, "medium": 1, "high": 2}
                if severity_rank.get(risk.severity, 0) > severity_rank.get(existing.severity, 0):
                    existing.severity = risk.severity
                if len(risk.summary) > len(existing.summary):
                    existing.summary = risk.summary
        all_risks = list(deduped.values())

        severity_counts = Counter(risk.severity for risk in all_risks)
        domain_counts = Counter(risk.risk_domain for risk in all_risks)
        top_risks = sorted(
            all_risks,
            key=lambda item: (
                {"high": 0, "medium": 1, "low": 2}.get(item.severity, 3),
                -item.confidence,
                item.risk_key,
            ),
        )[:8]
        overall = "low"
        if severity_counts.get("high"):
            overall = "high"
        elif severity_counts.get("medium"):
            overall = "medium"
        elif coverage_gaps and not all_risks:
            overall = "low"

        return ChapterRiskCard(
            branch_id=branch_id,
            chapter_index=chapter_index,
            overall_risk_level=overall,
            top_risks=top_risks,
            risk_counts_by_domain=dict(domain_counts),
            risk_counts_by_severity=dict(severity_counts),
            review_status="pending",
            generated_at=datetime.now(UTC).isoformat(),
            checker_statuses=checker_statuses,
            coverage_gaps=coverage_gaps,
        )

    def generate_for_chapter(self, branch_id: str, chapter_index: int) -> ChapterRiskCard:
        artifact_payload = self._artifact_payload(branch_id, chapter_index)
        facts = self._facts(branch_id, chapter_index)
        gate_decisions = ConfidenceGatedActivationService.gate_checkers(
            facts, [checker.name for checker in self.checkers],
        )
        results: list[CheckerResult] = []
        for checker in self.checkers:
            decision = gate_decisions.get(checker.name)
            if decision and not decision.should_run:
                results.append(CheckerResult(
                    checker_name=checker.name,
                    chapter_index=chapter_index,
                    status="skipped",
                    risks=[],
                    notes=[f"skipped by confidence gate: {decision.reason}"],
                    latency_ms=0,
                ))
                continue
            try:
                result = checker.evaluate(
                    branch_id=branch_id,
                    chapter_index=chapter_index,
                    artifact_payload=artifact_payload,
                    facts=facts,
                )
            except Exception as exc:  # noqa: BLE001
                result = CheckerResult(
                    checker_name=checker.name,
                    chapter_index=chapter_index,
                    status="failed",
                    risks=[],
                    notes=[f"{checker.name} failed: {exc}"],
                    latency_ms=None,
                )
            self._replace_checker_result(branch_id, chapter_index, result)
            results.append(result)
        stored_signals = self.risk_signal_store.replace_branch_chapter_signals(
            branch_id=branch_id,
            chapter_index=chapter_index,
            items=RiskSignalStoreService.build_signal_items(
                artifact_payload=artifact_payload,
                checker_results=[result.model_dump(mode="json") for result in results],
            ),
        )
        self.semantic_signal_lookup[(branch_id, chapter_index)] = stored_signals
        self.risk_signal_link.replace_branch_links(
            branch_id=branch_id,
            chapter_index=chapter_index,
            items=self.risk_signal_link.build_minimal_link_proposals(
                branch_id=branch_id,
                chapter_index=chapter_index,
                signals=[
                    {
                        "id": signal.id,
                        "signal_type": signal.signal_type,
                        "raw_text": signal.raw_text,
                        "canonical_label": signal.canonical_label,
                        "confidence": signal.confidence,
                    }
                    for signal in stored_signals
                ],
            ),
        )
        self.risk_signal_cluster.replace_branch_chapter_clusters(
            branch_id=branch_id,
            chapter_index=chapter_index,
            clusters=self.risk_signal_cluster.build_clusters_from_signals(
                branch_id=branch_id,
                chapter_index=chapter_index,
            ),
        )
        card = self.aggregate(branch_id=branch_id, chapter_index=chapter_index, checker_results=results)
        self._replace_risk_card(card)
        self.session.commit()
        return card

    def load_risk_card(self, branch_id: str, chapter_index: int) -> dict[str, object] | None:
        record = self.session.scalar(
            select(ChapterRiskCardRecord)
            .where(ChapterRiskCardRecord.branch_id == branch_id)
            .where(ChapterRiskCardRecord.chapter_index == chapter_index)
            .where(ChapterRiskCardRecord.visibility == "active")
            .order_by(ChapterRiskCardRecord.created_at.desc())
        )
        return cast(dict[str, object], record.payload_json) if record is not None else None

    def load_risk_summary(self, run_id: str, branch_id: str) -> dict[str, object]:
        export_bundle = ExportService(self.session).export_branch_bundle(run_id, branch_id)
        chapter_rows = cast(list[dict[str, object]], export_bundle.get("chapter_index", []))
        try:
            cards = list(
                self.session.scalars(
                    select(ChapterRiskCardRecord)
                    .where(ChapterRiskCardRecord.branch_id == branch_id)
                    .where(ChapterRiskCardRecord.visibility == "active")
                    .order_by(ChapterRiskCardRecord.chapter_index)
                ).all()
            )
        except ProgrammingError as exc:
            if not self._is_missing_relation_error(exc):
                raise
            self.session.rollback()
            return {
                "chapter_count": len(chapter_rows),
                "risk_card_count": 0,
                "checker_result_count": 0,
                "high_risk_chapters": [],
                "risk_counts_by_severity": {},
                "risk_counts_by_domain": {},
            }
        risk_cards = [cast(dict[str, object], record.payload_json) for record in cards]
        severity_counts: Counter[str] = Counter()
        domain_counts: Counter[str] = Counter()
        high_risk_chapters: list[int] = []
        for card in risk_cards:
            severity_counts.update(cast(dict[str, int], card.get("risk_counts_by_severity", {})))
            domain_counts.update(cast(dict[str, int], card.get("risk_counts_by_domain", {})))
            if str(card.get("overall_risk_level")) == "high":
                high_risk_chapters.append(int(card.get("chapter_index", 0)))
        return {
            "chapter_count": len(chapter_rows),
            "risk_card_count": len(risk_cards),
            "high_risk_chapters": high_risk_chapters,
            "risk_counts_by_severity": dict(severity_counts),
            "risk_counts_by_domain": dict(domain_counts),
        }
