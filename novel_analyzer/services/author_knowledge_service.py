"""Author-facing knowledge pack assembly."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact, FactRecord
from novel_analyzer.services.context_service import ContextService


class AuthorKnowledgeService:
    """Build a structured branch knowledge pack from existing knowledge layers."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.context = ContextService(session)

    def build_branch_knowledge_pack(
        self,
        branch_id: str,
        *,
        upto_chapter_index: int | None = None,
        limit_per_section: int = 20,
    ) -> dict[str, object]:
        artifact_stmt = select(ChapterArtifact).where(
            ChapterArtifact.branch_id == branch_id,
            ChapterArtifact.artifact_type == "chapter_analysis",
            ChapterArtifact.visibility == "active",
        )
        if upto_chapter_index is not None:
            artifact_stmt = artifact_stmt.where(ChapterArtifact.chapter_index <= upto_chapter_index)
        artifacts = self.session.scalars(artifact_stmt.order_by(ChapterArtifact.chapter_index.asc())).all()
        facts_stmt = select(FactRecord).where(FactRecord.branch_id == branch_id)
        if upto_chapter_index is not None:
            facts_stmt = facts_stmt.where(FactRecord.chapter_index <= upto_chapter_index)
        facts = self.session.scalars(
            facts_stmt.order_by(FactRecord.chapter_index.asc(), FactRecord.fact_type.asc(), FactRecord.label.asc())
        ).all()

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in facts:
            grouped[row.fact_type].append(
                {
                    "label": row.label,
                    "chapter_index": row.chapter_index,
                    "confidence": row.confidence,
                    "evidence_list": row.evidence_list,
                }
            )

        latest_chapter = artifacts[-1].chapter_index if artifacts else 0
        state_summary = self.context.state_summary_json(branch_id, latest_chapter + 1) if latest_chapter else {}
        graph_context = self.context.graph_context_json(branch_id, latest_chapter + 1) if latest_chapter else {}

        chapter_cards = [
            {
                "chapter_index": artifact.chapter_index,
                "title": str(artifact.payload_json.get("normalized_title", "")),
                "summary": str(artifact.payload_json.get("chapter_summary", "")),
                "key_entities": list(artifact.payload_json.get("key_entities", []))[:5],
                "key_events": list(artifact.payload_json.get("key_events", []))[:5],
                "continuity_notes": list(artifact.payload_json.get("continuity_notes", []))[:3],
            }
            for artifact in artifacts[:limit_per_section]
        ]

        return {
            "contract_version": "author-knowledge.v1",
            "branch_id": branch_id,
            "chapter_span": {
                "min": artifacts[0].chapter_index if artifacts else None,
                "max": latest_chapter or None,
                "count": len(artifacts),
            },
            "chapter_cards": chapter_cards,
            "entities": grouped.get("entity", [])[:limit_per_section],
            "events": grouped.get("event", [])[:limit_per_section],
            "continuity": grouped.get("continuity", [])[:limit_per_section],
            "state_summary": state_summary,
            "graph_overview": graph_context.get("overview", {}),
            "central_nodes": graph_context.get("central_nodes", [])[:10],
            "recent_timeline": graph_context.get("recent_timeline", [])[:10],
            "recommended_questions": [
                "主角当前最重要的推进线是什么？",
                "当前有哪些关键关系与未解线程？",
                "规则/世界观约束最近有哪些变化？",
            ],
        }
