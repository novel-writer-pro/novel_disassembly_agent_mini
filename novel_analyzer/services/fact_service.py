"""Fact and window materialization from chapter artifacts."""

from __future__ import annotations

from collections import Counter
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact, FactRecord, WindowArtifact
from novel_analyzer.services.run_service import default_readable_artifact_clause


class FactService:
    """Materialize facts and 5-chapter windows from validated chapter artifacts."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def materialize_for_artifact(self, artifact_id: str) -> list[FactRecord]:
        """Persist fact rows derived from one chapter artifact."""

        artifact = self.session.scalar(
            select(ChapterArtifact).where(ChapterArtifact.id == artifact_id)
        )
        if artifact is None:
            raise ValueError(f"Unknown artifact_id: {artifact_id}")
        payload = artifact.payload_json
        self.session.execute(
            delete(FactRecord)
            .where(FactRecord.branch_id == artifact.branch_id)
            .where(FactRecord.chapter_index == artifact.chapter_index)
        )

        rows: list[FactRecord] = []
        key_entities = cast(list[Any], payload.get('key_entities', []))
        key_events = cast(list[Any], payload.get('key_events', []))
        continuity_notes = cast(list[Any], payload.get('continuity_notes', []))

        for label in key_entities:
            if isinstance(label, str) and label.strip():
                rows.append(
                    FactRecord(
                        branch_id=artifact.branch_id,
                        chapter_index=artifact.chapter_index,
                        fact_type='entity',
                        label=label.strip(),
                        evidence_list=[label.strip()],
                        confidence=0.6,
                    )
                )
        for label in key_events:
            if isinstance(label, str) and label.strip():
                rows.append(
                    FactRecord(
                        branch_id=artifact.branch_id,
                        chapter_index=artifact.chapter_index,
                        fact_type='event',
                        label=label.strip(),
                        evidence_list=[label.strip()],
                        confidence=0.7,
                    )
                )
        for note in continuity_notes:
            if isinstance(note, str) and note.strip():
                rows.append(
                    FactRecord(
                        branch_id=artifact.branch_id,
                        chapter_index=artifact.chapter_index,
                        fact_type='continuity',
                        label=note.strip(),
                        evidence_list=[note.strip()],
                        confidence=0.55,
                    )
                )
        self.session.add_all(rows)
        self.session.commit()
        return rows

    def list_facts(
        self,
        branch_id: str,
        chapter_index: int | None = None,
        limit: int = 50,
    ) -> list[FactRecord]:
        """Return fact rows for one branch, optionally filtered by chapter."""

        stmt = (
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .order_by(FactRecord.chapter_index, FactRecord.fact_type, FactRecord.label)
            .limit(limit)
        )
        if chapter_index is not None:
            stmt = stmt.where(FactRecord.chapter_index == chapter_index)
        return list(self.session.scalars(stmt).all())


    def search_facts(
        self,
        branch_id: str,
        query: str,
        limit: int = 20,
    ) -> list[FactRecord]:
        """Search fact labels/evidence text for a branch."""

        like_query = f"%{query}%"
        stmt = (
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(
                (FactRecord.label.like(like_query))
                | (FactRecord.fact_type.like(like_query))
            )
            .order_by(FactRecord.chapter_index, FactRecord.fact_type, FactRecord.label)
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def materialize_window_if_ready(
        self,
        branch_id: str,
        chapter_index: int,
        window_size: int = 5,
    ) -> WindowArtifact | None:
        """Create/update a deterministic fixed-size window summary when the boundary is reached."""

        if chapter_index < window_size or chapter_index % window_size != 0:
            return None
        start = chapter_index - window_size + 1
        artifacts = self.session.scalars(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index >= start)
            .where(ChapterArtifact.chapter_index <= chapter_index)
            .where(default_readable_artifact_clause())
            .order_by(ChapterArtifact.chapter_index)
        ).all()
        if len(artifacts) < window_size:
            return None

        entity_counter: Counter[str] = Counter()
        event_counter: Counter[str] = Counter()
        summaries: list[str] = []
        for artifact in artifacts:
            payload = artifact.payload_json
            summaries.append(f"第{artifact.chapter_index}章：{payload.get('chapter_summary', '')}")
            key_entities = cast(list[Any], payload.get('key_entities', []))
            key_events = cast(list[Any], payload.get('key_events', []))
            entity_counter.update(
                item.strip()
                for item in key_entities
                if isinstance(item, str) and item.strip()
            )
            event_counter.update(
                item.strip()
                for item in key_events
                if isinstance(item, str) and item.strip()
            )

        payload_json: dict[str, Any] = {
            'window_start_chapter': start,
            'window_end_chapter': chapter_index,
            'chapter_summaries': summaries,
            'top_entities': entity_counter.most_common(10),
            'top_events': event_counter.most_common(10),
            'window_summary': ' '.join(summaries),
        }
        existing = self.session.scalar(
            select(WindowArtifact)
            .where(WindowArtifact.branch_id == branch_id)
            .where(WindowArtifact.window_start_chapter == start)
            .where(WindowArtifact.window_end_chapter == chapter_index)
        )
        if existing is None:
            existing = WindowArtifact(
                branch_id=branch_id,
                window_start_chapter=start,
                window_end_chapter=chapter_index,
                payload_json=payload_json,
            )
            self.session.add(existing)
        else:
            existing.payload_json = payload_json
            existing.status = 'ready'
        self.session.commit()
        self.session.refresh(existing)
        return existing
