"""Persistence helpers for risk semantic signals."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import cast

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import RiskSemanticSignalRecord
from novel_analyzer.embedding.service import get_embedding_provider


@dataclass(frozen=True, slots=True)
class StoredRiskSignal:
    id: str
    signal_type: str
    raw_text: str
    canonical_label: str
    canonical_group: str
    canonical_key: str
    confidence: float
    chapter_index: int
    evidence_reasons: list[str]


class RiskSignalStoreService:
    """Write/read semantic signal records for later embedding-backed retrieval."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.embedding_provider = get_embedding_provider(self.settings)

    @staticmethod
    def canonical_key(signal_type: str, label: str, group: str = "") -> str:
        """Return a stable, checker-contract-safe canonical key for semantic signals."""

        base = group.strip() or label.strip() or signal_type.strip() or "signal"
        normalized = re.sub(r"\s+", "-", base.lower())
        normalized = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff_.:-]+", "-", normalized)
        normalized = normalized.strip("-._:") or "signal"
        return f"{signal_type.strip() or 'signal'}:{normalized}"

    @staticmethod
    def _evidence_reasons(item: dict[str, object], source_field: str, raw_text: str) -> list[str]:
        raw_reasons = item.get("evidence_reasons", [])
        if isinstance(raw_reasons, list):
            reasons = [str(reason).strip() for reason in raw_reasons if str(reason).strip()]
        else:
            reasons = [str(raw_reasons).strip()] if str(raw_reasons).strip() else []
        if not reasons and source_field:
            reasons.append(f"extracted_from:{source_field}")
        if raw_text and not any(reason.startswith("raw_text:") for reason in reasons):
            reasons.append(f"raw_text:{raw_text[:80]}")
        return reasons[:5]

    def replace_branch_chapter_signals(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        items: list[dict[str, object]],
    ) -> list[StoredRiskSignal]:
        self.session.execute(
            delete(RiskSemanticSignalRecord)
            .where(RiskSemanticSignalRecord.branch_id == branch_id)
            .where(RiskSemanticSignalRecord.chapter_index == chapter_index)
        )
        records: list[RiskSemanticSignalRecord] = []
        texts_needing_vectors: list[str] = []
        text_indices: list[int] = []
        for item in items:
            vector = [
                float(x) for x in item.get("vector_payload", []) if isinstance(x, (int, float))
            ]
            raw_text = str(item.get("raw_text") or "")
            if not vector and raw_text.strip():
                text_indices.append(len(records))
                texts_needing_vectors.append(raw_text)
            signal_type = str(item.get('signal_type') or '')
            source_field = str(item.get('source_field') or '')
            canonical_label = str(item.get('canonical_label') or raw_text)
            canonical_group = str(item.get('canonical_group') or signal_type)
            canonical_key = str(item.get('canonical_key') or self.canonical_key(signal_type, canonical_label, canonical_group))
            metadata = dict(item.get('metadata_json') or {})
            evidence_reasons = self._evidence_reasons(item, source_field, raw_text)
            metadata.setdefault('canonical_key', canonical_key)
            metadata.setdefault('evidence_reasons', evidence_reasons)
            record = RiskSemanticSignalRecord(
                branch_id=branch_id,
                chapter_index=chapter_index,
                signal_type=str(item.get("signal_type") or ""),
                source_field=str(item.get("source_field") or ""),
                raw_text=raw_text,
                canonical_label=str(item.get("canonical_label") or ""),
                canonical_group=str(item.get("canonical_group") or ""),
                confidence=float(item.get("confidence") or 0.0),
                metadata_json=dict(item.get("metadata_json") or {}),
                vector_payload=vector,
                vector_text=("[" + ",".join(str(float(x)) for x in vector) + "]") if vector else "",
                vector_dim=len(vector),
                status=str(item.get("status") or "ready"),
            )
            self.session.add(record)
            records.append(record)
        if texts_needing_vectors:
            try:
                embedded = self.embedding_provider.embed_texts(texts_needing_vectors)
                for record_index, vector in zip(text_indices, embedded, strict=True):
                    records[record_index].vector_payload = [float(x) for x in vector]
                    records[record_index].vector_text = (
                        "[" + ",".join(str(float(x)) for x in vector) + "]"
                    )
                    records[record_index].vector_dim = len(vector)
            except Exception:
                pass
        self.session.flush()
        return [
            StoredRiskSignal(
                id=record.id,
                signal_type=record.signal_type,
                raw_text=record.raw_text,
                canonical_label=record.canonical_label,
                canonical_group=record.canonical_group,
                canonical_key=str(record.metadata_json.get("canonical_key") or self.canonical_key(record.signal_type, record.canonical_label, record.canonical_group)),
                confidence=record.confidence,
                chapter_index=record.chapter_index,
                evidence_reasons=[str(item) for item in record.metadata_json.get("evidence_reasons", [])],
            )
            for record in records
        ]

    def list_branch_chapter_signals(
        self, branch_id: str, chapter_index: int
    ) -> list[StoredRiskSignal]:
        rows = self.session.scalars(
            select(RiskSemanticSignalRecord)
            .where(RiskSemanticSignalRecord.branch_id == branch_id)
            .where(RiskSemanticSignalRecord.chapter_index == chapter_index)
            .order_by(RiskSemanticSignalRecord.signal_type, RiskSemanticSignalRecord.raw_text)
        ).all()
        return [
            StoredRiskSignal(
                id=row.id,
                signal_type=row.signal_type,
                raw_text=row.raw_text,
                canonical_label=row.canonical_label,
                canonical_group=row.canonical_group,
                canonical_key=str(row.metadata_json.get("canonical_key") or self.canonical_key(row.signal_type, row.canonical_label, row.canonical_group)),
                confidence=row.confidence,
                chapter_index=row.chapter_index,
                evidence_reasons=[str(item) for item in row.metadata_json.get("evidence_reasons", [])],
            )
            for row in rows
        ]

    def list_latest_signals(
        self,
        *,
        branch_id: str,
        signal_type: str,
        before_chapter_index: int,
        limit: int = 5,
    ) -> list[StoredRiskSignal]:
        rows = self.session.scalars(
            select(RiskSemanticSignalRecord)
            .where(RiskSemanticSignalRecord.branch_id == branch_id)
            .where(RiskSemanticSignalRecord.signal_type == signal_type)
            .where(RiskSemanticSignalRecord.chapter_index < before_chapter_index)
            .order_by(
                RiskSemanticSignalRecord.chapter_index.desc(), RiskSemanticSignalRecord.raw_text
            )
            .limit(limit)
        ).all()
        return [
            StoredRiskSignal(
                id=row.id,
                signal_type=row.signal_type,
                raw_text=row.raw_text,
                canonical_label=row.canonical_label,
                canonical_group=row.canonical_group,
                canonical_key=str(row.metadata_json.get("canonical_key") or self.canonical_key(row.signal_type, row.canonical_label, row.canonical_group)),
                confidence=row.confidence,
                chapter_index=row.chapter_index,
                evidence_reasons=[str(item) for item in row.metadata_json.get("evidence_reasons", [])],
            )
            for row in rows
        ]

    @staticmethod
    def _canonical_key(signal_type: str, text: str) -> str:
        normalized = "".join(ch.lower() for ch in text.strip() if not ch.isspace())
        return f"{signal_type}:{normalized[:80]}" if normalized else signal_type

    @classmethod
    def build_signal_items(
        cls,
        *,
        artifact_payload: dict[str, object],
        checker_results: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Build minimal semantic-signal rows from artifact/state/checker outputs."""

        items: list[dict[str, object]] = []

        def add_many(signal_type: str, source_field: str, values: list[str]) -> None:
            for value in values:
                text = str(value).strip()
                if not text:
                    continue
                canonical_group = signal_type
                canonical_key = RiskSignalStoreService.canonical_key(signal_type, text, canonical_group)
                items.append(
                    {
                        "signal_type": signal_type,
                        "source_field": source_field,
                        "raw_text": text,
                        "canonical_label": text,
                        "canonical_group": canonical_group,
                        "canonical_key": canonical_key,
                        "confidence": 0.5,
                        "metadata_json": {
                            "canonical_key": RiskSignalStoreService._canonical_key(
                                signal_type, text
                            ),
                            "evidence_reason": f"artifact:{source_field}",
                        },
                        "vector_payload": [],
                        "status": "ready",
                    }
                )

        state_summary = artifact_payload.get("state_summary", {})
        if isinstance(state_summary, dict):
            add_many(
                "relationship",
                "state_summary.stable_relations",
                [str(x) for x in state_summary.get("stable_relations", [])],
            )
            add_many(
                "relationship",
                "state_summary.evolved_relations",
                [str(x) for x in state_summary.get("evolved_relations", [])],
            )
            add_many(
                "foreshadow",
                "state_summary.new_foreshadowing",
                [str(x) for x in state_summary.get("new_foreshadowing", [])],
            )
            add_many(
                "foreshadow",
                "state_summary.paid_off_foreshadowing",
                [str(x) for x in state_summary.get("paid_off_foreshadowing", [])],
            )
            add_many(
                "rule_scope",
                "state_summary.observed_world_rules",
                [str(x) for x in state_summary.get("observed_world_rules", [])],
            )
            add_many(
                "rule_scope",
                "state_summary.constraining_world_rules",
                [str(x) for x in state_summary.get("constraining_world_rules", [])],
            )
            add_many(
                "conflict_thread",
                "state_summary.new_conflicts",
                [str(x) for x in state_summary.get("new_conflicts", [])],
            )
            add_many(
                "conflict_thread",
                "state_summary.escalated_conflicts",
                [str(x) for x in state_summary.get("escalated_conflicts", [])],
            )

        add_many(
            "unsupported",
            "unsupported_inferences",
            [str(x) for x in artifact_payload.get("unsupported_inferences", [])],
        )
        add_many(
            "ambiguous",
            "ambiguous_points",
            [str(x) for x in artifact_payload.get("ambiguous_points", [])],
        )
        add_many(
            "transition",
            "state_transition_notes",
            [str(x) for x in artifact_payload.get("state_transition_notes", [])],
        )
        add_many(
            "resolution",
            "evidence_backed_resolutions",
            [str(x) for x in artifact_payload.get("evidence_backed_resolutions", [])],
        )
        add_many(
            "thread",
            "unresolved_threads",
            [str(x) for x in artifact_payload.get("unresolved_threads", [])],
        )
        add_many(
            "timeline_anchor",
            "timeline_signals",
            [str(x) for x in artifact_payload.get("timeline_signals", [])],
        )
        add_many(
            "power_state",
            "power_signals",
            [str(x) for x in artifact_payload.get("power_signals", [])],
        )

        for result in checker_results:
            checker_name = str(result.get("checker_name") or "")
            risks = result.get("risks", [])
            if not isinstance(risks, list):
                continue
            for risk in risks:
                if not isinstance(risk, dict):
                    continue
                summary = str(risk.get("summary") or "").strip()
                if not summary:
                    continue
                items.append(
                    {
                        "signal_type": f"checker:{checker_name}",
                        "source_field": "checker_result.risks.summary",
                        "raw_text": summary,
                        "canonical_label": summary,
                        "canonical_group": str(risk.get("risk_type") or checker_name),
                        "confidence": float(risk.get("confidence") or 0.0),
                        "metadata_json": {
                            "risk_type": str(risk.get("risk_type") or ""),
                            "canonical_key": cls._canonical_key(f"checker:{checker_name}", summary),
                            "evidence_reason": f"checker:{checker_name}:risk_summary",
                        },
                        "vector_payload": [],
                        "status": "ready",
                    }
                )

        return items

    def semantic_search(
        self,
        *,
        branch_id: str,
        query_text: str,
        signal_type: str = "",
        before_chapter_index: int | None = None,
        limit: int = 5,
    ) -> list[StoredRiskSignal]:
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            pg_hits = self._semantic_search_postgres(
                branch_id=branch_id,
                query_text=query_text,
                signal_type=signal_type,
                before_chapter_index=before_chapter_index,
                limit=limit,
            )
            if pg_hits:
                return pg_hits
        stmt = select(RiskSemanticSignalRecord).where(
            RiskSemanticSignalRecord.branch_id == branch_id
        )
        if signal_type:
            stmt = stmt.where(RiskSemanticSignalRecord.signal_type == signal_type)
        if before_chapter_index is not None:
            stmt = stmt.where(RiskSemanticSignalRecord.chapter_index < before_chapter_index)
        rows = self.session.scalars(stmt).all()
        query = query_text.strip()
        if not query:
            return []
        if not rows:
            return []
        try:
            query_vector = self.embedding_provider.embed_texts([query])[0]
        except Exception:
            return []
        scored: list[tuple[float, RiskSemanticSignalRecord]] = []
        for row in rows:
            vector = cast(list[float], row.vector_payload or [])
            if not vector or len(vector) != len(query_vector):
                continue
            score = sum(float(a) * float(b) for a, b in zip(query_vector, vector, strict=True))
            scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], item[1].signal_type, item[1].raw_text))
        return [
            StoredRiskSignal(
                id=row.id,
                signal_type=row.signal_type,
                raw_text=row.raw_text,
                canonical_label=row.canonical_label,
                canonical_group=row.canonical_group,
                canonical_key=str(row.metadata_json.get("canonical_key") or self.canonical_key(row.signal_type, row.canonical_label, row.canonical_group)),
                confidence=row.confidence,
                chapter_index=row.chapter_index,
                evidence_reasons=[str(item) for item in row.metadata_json.get("evidence_reasons", [])],
            )
            for _, row in scored[:limit]
        ]

    def _semantic_search_postgres(
        self,
        *,
        branch_id: str,
        query_text: str,
        signal_type: str,
        before_chapter_index: int | None,
        limit: int,
    ) -> list[StoredRiskSignal]:
        query = query_text.strip()
        if not query:
            return []
        try:
            query_vector = self.embedding_provider.embed_texts([query])[0]
        except Exception:
            return []
        if not query_vector:
            return []
        vector_literal = "[" + ",".join(f"{float(value):.8f}" for value in query_vector) + "]"
        sql = """
            SELECT id, signal_type, raw_text, canonical_label, canonical_group, confidence, chapter_index
            FROM risk_semantic_signals
            WHERE branch_id = :branch_id
              AND (:signal_type = '' OR signal_type = :signal_type)
              AND (:before_chapter_index IS NULL OR chapter_index < :before_chapter_index)
              AND vector_dim > 0
            ORDER BY vector_text::vector <=> CAST(:query_vector AS vector), chapter_index ASC
            LIMIT :limit
        """
        try:
            rows = (
                self.session.execute(
                    text(sql),
                    {
                        "branch_id": branch_id,
                        "signal_type": signal_type,
                        "before_chapter_index": before_chapter_index,
                        "query_vector": vector_literal,
                        "limit": limit,
                    },
                )
                .mappings()
                .all()
            )
        except Exception:
            return []
        return [
            StoredRiskSignal(
                id=str(row["id"]),
                signal_type=str(row["signal_type"]),
                raw_text=str(row["raw_text"]),
                canonical_label=str(row["canonical_label"]),
                canonical_group=str(row["canonical_group"]),
                canonical_key=self.canonical_key(str(row["signal_type"]), str(row["canonical_label"]), str(row["canonical_group"])),
                confidence=float(row["confidence"]),
                chapter_index=int(row["chapter_index"]),
                evidence_reasons=[],
            )
            for row in rows
        ]
