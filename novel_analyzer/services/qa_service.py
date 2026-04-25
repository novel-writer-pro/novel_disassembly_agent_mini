"""Retrieval-grounded Q&A over one branch."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import GraphEdge, GraphNode, WindowArtifact
from novel_analyzer.domain.schemas import BranchQAResult
from novel_analyzer.llm.client import build_chat_model
from novel_analyzer.llm.prompts import build_branch_qa_prompt
from novel_analyzer.services.analysis_service import AnalysisService
from novel_analyzer.services.retrieval_service import RetrievalService


class BranchQAService:
    """Answer detail questions using retrieval context from one branch."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.retrieval_service = RetrievalService(session, self.settings)

    def _window_context(self, branch_id: str, chapter_numbers: list[int]) -> list[str]:
        if not chapter_numbers:
            return []
        windows = self.session.scalars(
            select(WindowArtifact)
            .where(WindowArtifact.branch_id == branch_id)
            .order_by(WindowArtifact.window_start_chapter)
        ).all()
        lines: list[str] = []
        for window in windows:
            if any(
                window.window_start_chapter <= chapter <= window.window_end_chapter
                for chapter in chapter_numbers
            ):
                summary = str(window.payload_json.get('window_summary', ''))
                lines.append(
                    f"[窗口 {window.window_start_chapter}-{window.window_end_chapter}] {summary}"
                )
        return lines

    def _graph_context(self, branch_id: str, chapter_numbers: list[int]) -> list[str]:
        if not chapter_numbers:
            return []
        low = min(chapter_numbers)
        high = max(chapter_numbers)
        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.chapter_first_seen <= high)
            .where(GraphNode.chapter_last_seen >= low)
            .order_by(GraphNode.node_type, GraphNode.label)
        ).all()
        edges = self.session.scalars(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.chapter_first_seen <= high)
            .where(GraphEdge.chapter_last_seen >= low)
            .order_by(GraphEdge.edge_type)
        ).all()
        node_by_id = {node.id: node for node in nodes}
        node_lines = [
            f"[图节点] {node.node_type}:{node.label} (出现 {node.occurrence_count} 次)"
            for node in nodes[:20]
        ]
        edge_lines = []
        for edge in edges[:20]:
            source = node_by_id.get(edge.source_node_id)
            target = node_by_id.get(edge.target_node_id)
            if source is None or target is None:
                continue
            edge_lines.append(
                f"[图边] {source.label} -[{edge.edge_type}/{edge.weight:.1f}]-> {target.label}"
            )
        return node_lines + edge_lines

    def answer_question(self, branch_id: str, question: str, limit: int = 5) -> BranchQAResult:
        """Answer a question from retrieval hits only."""

        hits = self.retrieval_service.search_branch(branch_id, question, limit)
        if not hits:
            return BranchQAResult(
                answer='当前证据不足，未检索到可以支持回答的章节内容。',
                used_chapters=[],
                evidence=[],
                confidence=0.0,
                insufficient_context=True,
            )

        context_lines: list[str] = []
        evidence: list[str] = []
        used_chapters: list[int] = []
        for hit in hits:
            used_chapters.append(hit.chapter_index)
            keywords = ', '.join(hit.keyword_list[:8])
            context_lines.append(
                f"[第{hit.chapter_index}章|{hit.title}|score={hit.score:.4f}]\n"
                f"摘要：{hit.summary_text}\n关键词：{keywords}"
            )
            evidence.append(f"第{hit.chapter_index}章：{hit.summary_text}")

        window_lines = self._window_context(branch_id, used_chapters)
        graph_lines = self._graph_context(branch_id, used_chapters)
        retrieval_context = '\n\n'.join(context_lines + window_lines + graph_lines)
        prompt = build_branch_qa_prompt(
            question=question,
            retrieval_context=retrieval_context,
        )
        model = build_chat_model(
            self.settings,
            model_name=self.settings.llm_qa_model_name,
        )
        response = model.invoke(prompt)
        raw = AnalysisService._extract_json_payload(response)
        result = BranchQAResult.model_validate(raw)
        if not result.used_chapters:
            result = result.model_copy(update={'used_chapters': used_chapters})
        if not result.evidence:
            result = result.model_copy(update={'evidence': evidence[:5]})
        return result
