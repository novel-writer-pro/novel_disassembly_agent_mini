"""Composite novel-assistant capability pack assembly."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import RunBranch
from novel_analyzer.services.author_knowledge_service import AuthorKnowledgeService
from novel_analyzer.services.export_service import ExportService
from novel_analyzer.services.qa_service import BranchQAService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.run_service import RunService


class NovelAssistantService:
    """Build a unified assistant capability pack for one branch."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.run_service = RunService(session, self.settings)
        self.export_service = ExportService(session)
        self.retrieval_service = RetrievalService(session, self.settings)
        self.qa_service = BranchQAService(session, self.settings)
        self.author_knowledge = AuthorKnowledgeService(session)

    def build_branch_assistant_pack(
        self,
        branch_id: str,
        *,
        query: str = "",
        question: str = "",
        from_chapter_index: int | None = None,
        upto_chapter_index: int | None = None,
        focus_label: str = "",
        limit: int = 5,
    ) -> dict[str, object]:
        branch = self.session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        if branch is None:
            raise ValueError(f"Unknown branch_id: {branch_id}")

        branch_snapshot = self.run_service.branch_snapshot(branch_id)
        branch_bundle = self.export_service.export_branch_bundle(branch.run_id, branch_id)
        knowledge_pack = self.author_knowledge.build_branch_knowledge_pack(
            branch_id,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
        )
        retrieval_diagnostics: dict[str, object] | None = None
        if query.strip():
            try:
                diagnostics = self.retrieval_service.search_branch_with_diagnostics(
                    branch_id, query, limit
                )
            except RuntimeError:
                retrieval_diagnostics = {
                    "query": query,
                    "degraded": True,
                    "reason": "retrieval_diagnostics_unavailable_for_current_runtime",
                }
            else:
                retrieval_diagnostics = {
                    "query": diagnostics.query,
                    "fusion_applied": diagnostics.fusion_applied,
                    "rerank_applied": diagnostics.rerank_applied,
                    "route_counts": diagnostics.route_counts or {},
                    "raw_latency_ms": diagnostics.raw_latency_ms,
                    "rerank_latency_ms": diagnostics.rerank_latency_ms,
                    "raw_hits": [
                        {
                            "chapter_index": hit.chapter_index,
                            "title": hit.title,
                            "score": hit.score,
                        }
                        for hit in diagnostics.raw_hits[:limit]
                    ],
                    "reranked_hits": [
                        {
                            "chapter_index": hit.chapter_index,
                            "title": hit.title,
                            "score": hit.score,
                        }
                        for hit in diagnostics.reranked_hits[:limit]
                    ],
                }
        qa_answer: dict[str, object] | None = None
        if question.strip():
            answer = self.qa_service.answer_question(branch_id, question, limit)
            qa_answer = answer.model_dump()

        chapter_count = int(branch_snapshot.get("completed_chapters", 0) or 0)
        if chapter_count <= 0:
            chapter_count = int(knowledge_pack.get("chapter_span", {}).get("count", 0) or 0)
        review_summary = branch_bundle.get("review_summary", {})
        risk_summary = branch_bundle.get("risk_summary", {})
        top_entities = knowledge_pack.get("summary_layer", {}).get("top_entities", [])
        return {
            "contract_version": "novel-assistant.v1",
            "branch_id": branch_id,
            "run_id": branch.run_id,
            "branch_snapshot": branch_snapshot,
            "assistant_summary": {
                "chapter_count": chapter_count,
                "review_cluster_count": int(review_summary.get("cluster_count", 0) or 0),
                "review_needs_count": int(review_summary.get("needs_review_count", 0) or 0),
                "risk_card_count": int(risk_summary.get("risk_card_count", 0) or 0),
                "top_entities": top_entities[:5],
                "assistant_mode": "commercial-novel-assistant",
            },
            "supported_actions": [
                "split_novel",
                "retrieve_evidence",
                "answer_question",
                "author_knowledge",
                "risk_gate_review",
                "whole_book_preparation",
            ],
            "recommended_next_actions": [
                "先用 author knowledge 确认人物/规则/线程现状，再进入续写/仿写。",
                "需要问答或检索时，优先使用 retrieval diagnostics 确认召回质量。",
                "进入 whole-book 之前先看 review_summary 与 risk_summary，避免带病生成。",
            ],
            "audit_conclusion": branch_bundle.get("audit_conclusion", {}),
            "review_summary": review_summary,
            "risk_summary": risk_summary,
            "author_knowledge": knowledge_pack,
            "retrieval_diagnostics": retrieval_diagnostics,
            "qa_answer": qa_answer,
        }
