"""Cluster helpers for persisted semantic risk signals."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import RiskSemanticSignalRecord, RiskSignalClusterRecord


@dataclass(frozen=True, slots=True)
class StoredRiskSignalCluster:
    id: str
    cluster_key: str
    signal_type: str
    summary_text: str
    signal_ids: list[str]


class RiskSignalClusterService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_branch_chapter_clusters(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        clusters: list[dict[str, object]],
    ) -> list[StoredRiskSignalCluster]:
        self.session.execute(
            delete(RiskSignalClusterRecord)
            .where(RiskSignalClusterRecord.branch_id == branch_id)
            .where(RiskSignalClusterRecord.metadata_json['chapter_index'].as_integer() == chapter_index)
        )
        records: list[RiskSignalClusterRecord] = []
        for item in clusters:
            record = RiskSignalClusterRecord(
                branch_id=branch_id,
                cluster_key=str(item.get('cluster_key') or ''),
                signal_type=str(item.get('signal_type') or ''),
                summary_text=str(item.get('summary_text') or ''),
                signal_ids_json=[str(x) for x in item.get('signal_ids_json', [])],
                metadata_json=dict(item.get('metadata_json') or {}),
            )
            self.session.add(record)
            records.append(record)
        self.session.flush()
        return [
            StoredRiskSignalCluster(
                id=row.id,
                cluster_key=row.cluster_key,
                signal_type=row.signal_type,
                summary_text=row.summary_text,
                signal_ids=row.signal_ids_json,
            )
            for row in records
        ]

    def build_clusters_from_signals(
        self,
        *,
        branch_id: str,
        chapter_index: int,
    ) -> list[dict[str, object]]:
        rows = self.session.scalars(
            select(RiskSemanticSignalRecord)
            .where(RiskSemanticSignalRecord.branch_id == branch_id)
            .where(RiskSemanticSignalRecord.chapter_index == chapter_index)
            .order_by(RiskSemanticSignalRecord.signal_type, RiskSemanticSignalRecord.canonical_group, RiskSemanticSignalRecord.raw_text)
        ).all()
        grouped: dict[tuple[str, str], list[RiskSemanticSignalRecord]] = {}
        for row in rows:
            key = (row.signal_type, row.canonical_group or row.signal_type)
            grouped.setdefault(key, []).append(row)
        clusters: list[dict[str, object]] = []
        for (signal_type, canonical_group), items in grouped.items():
            cluster_key = f'{signal_type}:{canonical_group}'
            clusters.append(
                {
                    'cluster_key': cluster_key,
                    'signal_type': signal_type,
                    'summary_text': items[0].raw_text,
                    'signal_ids_json': [item.id for item in items],
                    'metadata_json': {'chapter_index': chapter_index, 'canonical_group': canonical_group},
                }
            )
        return clusters

    def list_branch_chapter_clusters(self, branch_id: str, chapter_index: int) -> list[StoredRiskSignalCluster]:
        rows = self.session.scalars(
            select(RiskSignalClusterRecord)
            .where(RiskSignalClusterRecord.branch_id == branch_id)
            .where(RiskSignalClusterRecord.metadata_json['chapter_index'].as_integer() == chapter_index)
            .order_by(RiskSignalClusterRecord.signal_type, RiskSignalClusterRecord.cluster_key)
        ).all()
        return [
            StoredRiskSignalCluster(
                id=row.id,
                cluster_key=row.cluster_key,
                signal_type=row.signal_type,
                summary_text=row.summary_text,
                signal_ids=row.signal_ids_json,
            )
            for row in rows
        ]

    def list_latest_clusters(
        self,
        *,
        branch_id: str,
        signal_type: str,
        before_chapter_index: int,
        limit: int = 5,
    ) -> list[StoredRiskSignalCluster]:
        rows = self.session.scalars(
            select(RiskSignalClusterRecord)
            .where(RiskSignalClusterRecord.branch_id == branch_id)
            .where(RiskSignalClusterRecord.signal_type == signal_type)
            .where(RiskSignalClusterRecord.metadata_json['chapter_index'].as_integer() < before_chapter_index)
            .order_by(RiskSignalClusterRecord.metadata_json['chapter_index'].as_integer().desc(), RiskSignalClusterRecord.cluster_key)
            .limit(limit)
        ).all()
        return [
            StoredRiskSignalCluster(
                id=row.id,
                cluster_key=row.cluster_key,
                signal_type=row.signal_type,
                summary_text=row.summary_text,
                signal_ids=row.signal_ids_json,
            )
            for row in rows
        ]
