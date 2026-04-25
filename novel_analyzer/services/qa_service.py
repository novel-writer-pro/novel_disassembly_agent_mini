"""Retrieval-grounded Q&A over one branch."""

from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import WindowArtifact
from novel_analyzer.domain.schemas import BranchQAResult
from novel_analyzer.llm.client import build_chat_model
from novel_analyzer.llm.prompts import build_branch_qa_prompt
from novel_analyzer.services.analysis_service import AnalysisService
from novel_analyzer.services.graph_service import GraphService
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
        snapshot = GraphService(self.session).reasoning_snapshot(
            branch_id,
            upto_chapter=max(chapter_numbers),
            node_limit=10,
            edge_limit=12,
        )
        overview = cast(dict[str, object], snapshot.get('overview', {}))
        overview_text = (
            f"[图谱概览] nodes={overview.get('node_count', 0)} "
            f"edges={overview.get('edge_count', 0)}"
        )
        lines = [
            overview_text,
        ]
        central_nodes = cast(list[object], snapshot.get('central_nodes', []))
        for item in central_nodes[:6]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"[图核心] {item.get('node_type')}:{item.get('label')} degree={item.get('degree')}"
            )
        reasoning_paths = cast(list[object], snapshot.get('reasoning_paths', []))
        for path in reasoning_paths[:8]:
            lines.append(f"[图推理] {path}")
        open_foreshadowing = cast(list[object], snapshot.get('open_foreshadowing', []))
        for label in open_foreshadowing[:6]:
            lines.append(f"[未回收伏笔] {label}")
        active_conflicts = cast(list[object], snapshot.get('active_conflicts', []))
        for label in active_conflicts[:6]:
            lines.append(f"[活跃冲突] {label}")
        return lines

    def _graph_reasoning_snapshot(
        self,
        branch_id: str,
        chapter_numbers: list[int],
    ) -> tuple[list[str], list[str]]:
        """Return structured graph signals for answer post-processing."""

        if not chapter_numbers:
            return [], []
        snapshot = GraphService(self.session).reasoning_snapshot(
            branch_id,
            upto_chapter=max(chapter_numbers),
            node_limit=10,
            edge_limit=12,
        )
        reasoning_paths = [
            str(item)
            for item in cast(list[object], snapshot.get('reasoning_paths', []))[:8]
            if str(item).strip()
        ]
        graph_signals: list[str] = []
        for item in cast(list[object], snapshot.get('active_conflicts', []))[:6]:
            label = str(item).strip()
            if label:
                graph_signals.append(f"活跃冲突: {label}")
        for item in cast(list[object], snapshot.get('open_foreshadowing', []))[:6]:
            label = str(item).strip()
            if label:
                graph_signals.append(f"未回收伏笔: {label}")
        for item in cast(list[object], snapshot.get('world_rules', []))[:6]:
            label = str(item).strip()
            if label:
                graph_signals.append(f"世界规则: {label}")
        state_machine = cast(dict[str, object], snapshot.get('state_machine', {}))
        for item in cast(list[object], state_machine.get('foreshadow', []))[:3]:
            if isinstance(item, dict) and item.get('status') == 'open':
                graph_signals.append(f"伏笔状态: {item.get('label')} [open]")
        for item in cast(list[object], state_machine.get('conflict', []))[:3]:
            if isinstance(item, dict) and item.get('status') == 'escalated':
                graph_signals.append(f"冲突状态: {item.get('label')} [escalated]")
        return reasoning_paths, graph_signals

    def answer_question(self, branch_id: str, question: str, limit: int = 5) -> BranchQAResult:
        """Answer a question from retrieval hits only."""

        hits = self.retrieval_service.search_branch(branch_id, question, limit)
        if not hits:
            return BranchQAResult(
                answer='当前证据不足，未检索到可以支持回答的章节内容。',
                used_chapters=[],
                evidence=[],
                reasoning_paths=[],
                graph_signals=[],
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
        reasoning_paths, graph_signals = self._graph_reasoning_snapshot(
            branch_id,
            used_chapters,
        )
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
        if not result.reasoning_paths:
            result = result.model_copy(update={'reasoning_paths': reasoning_paths[:5]})
        if not result.graph_signals:
            result = result.model_copy(update={'graph_signals': graph_signals[:6]})
        return result
