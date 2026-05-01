"""Multi-source evidence pack assembly for risk-audit checkers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import FactRecord
from novel_analyzer.services.risk_exact_context_service import ExactContextHit, RiskExactContextService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.risk_latest_object_service import LatestObjectSnapshot, RiskLatestObjectService
from novel_analyzer.services.risk_signal_cluster_service import RiskSignalClusterService, StoredRiskSignalCluster
from novel_analyzer.services.risk_signal_link_service import RiskSignalLinkService
from novel_analyzer.services.risk_signal_store_service import RiskSignalStoreService, StoredRiskSignal


@dataclass(frozen=True, slots=True)
class RiskEvidencePack:
    semantic_hits: list[StoredRiskSignal]
    latest_signals: list[StoredRiskSignal]
    clusters: list[StoredRiskSignalCluster]
    link_types: list[str]
    support_texts: list[str]
    graph_paths: list[str]
    state_summaries: list[str]
    exact_hints: list[str]
    exact_contexts: list[ExactContextHit]
    latest_objects: list[LatestObjectSnapshot]


class RiskEvidencePackService:
    def __init__(
        self,
        session: Session,
        signal_store: RiskSignalStoreService,
        link_service: RiskSignalLinkService,
        cluster_service: RiskSignalClusterService,
    ) -> None:
        self.session = session
        self.signal_store = signal_store
        self.link_service = link_service
        self.cluster_service = cluster_service
        self.graph_service = GraphService(session)
        self.exact_context_service = RiskExactContextService(session)
        self.latest_object_service = RiskLatestObjectService(session)

    def _exact_fact_hints(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        query_text: str,
    ) -> list[str]:
        like_query = f"%{query_text.strip()}%"
        if like_query == "%%":
            return []
        rows = self.session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index < chapter_index)
            .where(FactRecord.label.like(like_query))
            .order_by(FactRecord.chapter_index.desc(), FactRecord.label)
            .limit(5)
        ).all()
        hints: list[str] = []
        for row in rows:
            label = row.label.strip()
            if label:
                hints.append(f"fact:{row.fact_type}:{label}")
        return hints

    def build_pack(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        query_text: str,
        signal_type: str,
        limit: int = 3,
    ) -> RiskEvidencePack:
        hits = self.signal_store.semantic_search(
            branch_id=branch_id,
            query_text=query_text,
            signal_type=signal_type,
            before_chapter_index=chapter_index,
            limit=limit,
        )
        latest_signals = self.signal_store.list_latest_signals(
            branch_id=branch_id,
            signal_type=signal_type,
            before_chapter_index=chapter_index,
            limit=limit,
        )
        clusters = self.cluster_service.list_latest_clusters(
            branch_id=branch_id,
            signal_type=signal_type,
            before_chapter_index=chapter_index,
            limit=limit,
        )
        links = self.link_service.list_branch_links(branch_id)
        link_types = sorted({item.link_type for item in links})
        support_texts = [
            f"第{hit.chapter_index}章 signal:{hit.signal_type}:{hit.raw_text}"
            for hit in hits
        ]
        support_texts.extend(
            f"第{signal.chapter_index}章 latest:{signal.signal_type}:{signal.raw_text}"
            for signal in latest_signals
            if f"第{signal.chapter_index}章 latest:{signal.signal_type}:{signal.raw_text}" not in support_texts
        )
        support_texts.extend(
            f"cluster:{cluster.signal_type}:{cluster.summary_text}"
            for cluster in clusters
            if f"cluster:{cluster.signal_type}:{cluster.summary_text}" not in support_texts
        )
        snapshot = self.graph_service.reasoning_snapshot(branch_id, upto_chapter=max(chapter_index - 1, 0), node_limit=10, edge_limit=12)
        graph_paths = [str(item) for item in snapshot.get('reasoning_paths', [])[:6] if str(item).strip()]
        state_summary = self.graph_service.state_summary_from_snapshot(snapshot)
        state_summaries: list[str] = []
        for key in (
            'stable_relations',
            'evolved_relations',
            'new_foreshadowing',
            'paid_off_foreshadowing',
            'constraining_world_rules',
            'escalated_conflicts',
        ):
            values = state_summary.get(key, [])
            if isinstance(values, list):
                for value in values[:3]:
                    text = str(value).strip()
                    if text:
                        state_summaries.append(text)
        if not state_summaries:
            state_summaries = support_texts[:]
        if not support_texts:
            support_texts = state_summaries[:]
        exact_hints = self._exact_fact_hints(
            branch_id=branch_id,
            chapter_index=chapter_index,
            query_text=query_text,
        )
        exact_contexts = self.exact_context_service.latest_fact_hits(
            branch_id=branch_id,
            query_text=query_text,
            before_chapter_index=chapter_index,
            limit=limit,
        )
        latest_objects = self.latest_object_service.latest_snapshots(
            branch_id=branch_id,
            chapter_index=chapter_index,
        )
        support_texts.extend(
            f"exact:{hit.fact_type}:第{hit.chapter_index}章:{hit.label}"
            for hit in exact_contexts
            if f"exact:{hit.fact_type}:第{hit.chapter_index}章:{hit.label}" not in support_texts
        )
        support_texts.extend(
            f"object:{item.object_type}:{item.label}"
            for item in latest_objects
            if f"object:{item.object_type}:{item.label}" not in support_texts
        )
        return RiskEvidencePack(
            semantic_hits=hits,
            latest_signals=latest_signals,
            clusters=clusters,
            link_types=link_types,
            support_texts=support_texts,
            graph_paths=graph_paths,
            state_summaries=state_summaries,
            exact_hints=exact_hints,
            exact_contexts=exact_contexts,
            latest_objects=latest_objects,
        )
