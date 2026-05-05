"""Composite novel-assistant capability pack assembly."""

from __future__ import annotations

from typing import Any

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import ChapterArtifact, FactRecord, RunBranch
from novel_analyzer.runtime.provider_health import read_provider_health
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

    def _sample_evidence_summary(self) -> dict[str, object]:
        sample_paths = [
            "docs/examples/sample-branch-search-diagnostics-20260505.sample.json",
            "docs/examples/sample-branch-author-knowledge-20260505.sample.json",
            "docs/examples/sample-branch-novel-assistant-20260505.sample.json",
            "docs/examples/whole-book-imitation-run.provider-success-20260504.sample.json",
            "docs/examples/whole-book-imitation-run.provider-success-20260505.deepseek.sample.json",
        ]
        available = [path for path in sample_paths if Path(path).exists()]
        return {
            "available_samples": available,
            "sample_count": len(available),
        }

    def _whole_book_readiness_summary(self, branch_id: str) -> dict[str, object]:
        chapter_analysis_count = self.session.scalar(
            select(func.count())
            .select_from(ChapterArtifact)
            .where(
                ChapterArtifact.branch_id == branch_id,
                ChapterArtifact.artifact_type == "chapter_analysis",
            )
        ) or 0
        fact_count = self.session.scalar(
            select(func.count()).select_from(FactRecord).where(FactRecord.branch_id == branch_id)
        ) or 0
        provider_health = read_provider_health(self.settings)
        return {
            "whole_book_contract_version": "whole-book-imitation.v1",
            "whole_book_stable_contract_version": "whole-book-imitation-pre-v1",
            "provider_name": self.settings.llm_provider_name,
            "base_url": self.settings.resolved_llm_base_url,
            "model_name": self.settings.llm_model_name,
            "provider_last_status": provider_health.last_status,
            "chapter_analysis_count": int(chapter_analysis_count),
            "fact_record_count": int(fact_count),
            "ready_for_whole_book": bool(chapter_analysis_count >= 2 and fact_count > 0),
        }

    @staticmethod
    def _preparation_guidance(
        *,
        top_entities: list[str],
        review_needs_count: int,
        risk_card_count: int,
    ) -> dict[str, list[str]]:
        next_chapter = [
            "先确认主角当前目标、关系推进与未解线程，再进行续写规划。",
            "如果存在待复核问题簇，优先阅读 review summary 后再定续写方向。",
        ]
        imitation = [
            "先使用 author knowledge 确认人物/规则/线程现状，再进入仿写。",
            "whole-book 前先确认 retrieval diagnostics 是否能稳定召回关键章节。",
        ]
        risk_gate = [
            "进入生成前先看 risk summary 与 review summary，避免带病生成。",
        ]
        if top_entities:
            next_chapter.append(f"当前最重要的人物/实体：{'、'.join(top_entities[:3])}")
            imitation.append(f"仿写时优先保留这些实体线：{'、'.join(top_entities[:3])}")
        if review_needs_count > 0:
            risk_gate.append(f"当前仍有 {review_needs_count} 个 needs_review 问题簇，建议先复核。")
        if risk_card_count <= 0:
            risk_gate.append("当前 branch 尚无稳定 risk card，生成前应先确认审查链是否完整。")
        return {
            "next_chapter_preparation": next_chapter,
            "imitation_preparation": imitation,
            "risk_gate_preflight": risk_gate,
        }

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
        readiness_summary = self._whole_book_readiness_summary(branch_id)
        sample_evidence_summary = self._sample_evidence_summary()
        preparation_guidance = self._preparation_guidance(
            top_entities=top_entities,
            review_needs_count=int(review_summary.get("needs_review_count", 0) or 0),
            risk_card_count=int(risk_summary.get("risk_card_count", 0) or 0),
        )
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
                "continue_writing_preparation",
                "imitation_preparation",
                "whole_book_preparation",
            ],
            "recommended_next_actions": [
                "先用 author knowledge 确认人物/规则/线程现状，再进入续写/仿写。",
                "需要问答或检索时，优先使用 retrieval diagnostics 确认召回质量。",
                "进入 whole-book 之前先看 review_summary 与 risk_summary，避免带病生成。",
            ],
            "whole_book_readiness_summary": readiness_summary,
            "sample_evidence_summary": sample_evidence_summary,
            "preparation_guidance": preparation_guidance,
            "audit_conclusion": branch_bundle.get("audit_conclusion", {}),
            "review_summary": review_summary,
            "risk_summary": risk_summary,
            "author_knowledge": knowledge_pack,
            "retrieval_diagnostics": retrieval_diagnostics,
            "qa_answer": qa_answer,
        }
