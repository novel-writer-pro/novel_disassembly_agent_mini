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
from novel_analyzer.runtime.provider_health import record_provider_health
from novel_analyzer.services.analysis_service import AnalysisService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.retrieval_service import RetrievalService


class BranchQAService:
    """Answer detail questions using retrieval context from one branch."""

    QUESTION_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
        'relation': ('关系', '矛盾', '和谁', '联盟', '敌对', '师徒', '父母', '亲近', '疏远'),
        'world_rule': ('规则', '设定', '为什么不能', '相力', '世界', '血脉', '觉醒', '限制', '门槛'),
        'foreshadow': ('伏笔', '暗示', '预示', '暖流', '回收', '兑现'),
        'timeline': ('什么时候', '顺序', '先后', '主线', '前20章', '推进', '发展', '经过'),
        'character': ('人物', '谁', '动机', '态度', '想法', '决定', '为什么要'),
    }

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.retrieval_service = RetrievalService(session, self.settings)

    @classmethod
    def _classify_question(cls, question: str) -> str:
        text = question.strip()
        for question_type in ('relation', 'world_rule', 'foreshadow', 'timeline', 'character'):
            keywords = cls.QUESTION_TYPE_KEYWORDS[question_type]
            if any(keyword in text for keyword in keywords):
                return question_type
        return 'general'

    @staticmethod
    def _dedupe_strings(items: list[str], *, limit: int) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            deduped.append(text)
            if len(deduped) >= limit:
                break
        return deduped

    @staticmethod
    def _dedupe_chapters(items: list[int], *, limit: int) -> list[int]:
        deduped: list[int] = []
        seen: set[int] = set()
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
            if len(deduped) >= limit:
                break
        return deduped

    @classmethod
    def _question_overlap_terms(cls, question: str, question_type: str) -> list[str]:
        base_terms = list(cls.QUESTION_TYPE_KEYWORDS.get(question_type, ()))
        if question_type == 'general':
            base_terms = []
        return [term for term in base_terms if term in question]

    @classmethod
    def _rank_hits_for_question(
        cls,
        hits: list[RetrievalHit],
        *,
        question: str,
        question_type: str,
    ) -> list[RetrievalHit]:
        overlap_terms = cls._question_overlap_terms(question, question_type)
        if not overlap_terms:
            return hits

        def rank(hit: RetrievalHit) -> tuple[int, float, int]:
            haystack = ' '.join([hit.title, hit.summary_text] + hit.keyword_list)
            overlap = sum(1 for term in overlap_terms if term in haystack)
            return (-overlap, -hit.score, hit.chapter_index)

        return sorted(hits, key=rank)

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
        *,
        question_type: str = 'general',
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
        include_conflicts = question_type in {'general', 'character', 'relation', 'timeline'}
        include_foreshadowing = question_type in {'general', 'foreshadow', 'timeline'}
        include_world_rules = question_type in {'general', 'world_rule'}
        for item in cast(list[object], snapshot.get('active_conflicts', []))[:6]:
            label = str(item).strip()
            if label and include_conflicts:
                graph_signals.append(f"活跃冲突: {label}")
        for item in cast(list[object], snapshot.get('open_foreshadowing', []))[:6]:
            label = str(item).strip()
            if label and include_foreshadowing:
                graph_signals.append(f"未回收伏笔: {label}")
        for item in cast(list[object], snapshot.get('world_rules', []))[:6]:
            label = str(item).strip()
            if label and include_world_rules:
                graph_signals.append(f"世界规则: {label}")
        state_machine = cast(dict[str, object], snapshot.get('state_machine', {}))
        for item in cast(list[object], state_machine.get('foreshadow', []))[:3]:
            if (
                include_foreshadowing
                and isinstance(item, dict)
                and item.get('status') == 'open'
            ):
                graph_signals.append(f"伏笔状态: {item.get('label')} [open]")
        for item in cast(list[object], state_machine.get('conflict', []))[:3]:
            if (
                include_conflicts
                and isinstance(item, dict)
                and item.get('status') == 'escalated'
            ):
                graph_signals.append(f"冲突状态: {item.get('label')} [escalated]")
        return (
            self._dedupe_strings(reasoning_paths, limit=5),
            self._dedupe_strings(graph_signals, limit=6),
        )

    def _degraded_answer(
        self,
        question: str,
        used_chapters: list[int],
        evidence: list[str],
        chapter_evidence: list[str],
        window_evidence: list[str],
        graph_evidence: list[str],
        reasoning_paths: list[str],
        graph_signals: list[str],
        *,
        error_message: str,
    ) -> BranchQAResult:
        chapter_text = "、".join(f"第{chapter}章" for chapter in used_chapters[:4]) or "当前检索章节"
        evidence_text = evidence[0] if evidence else "当前只拿到了有限的章节摘要。"
        answer = (
            f"当前问答模型暂时不可用，所以我先基于已检索到的章节给出保守回答。"
            f"围绕“{question}”，目前最直接能确认的是：{evidence_text}"
            f" 如需更完整结论，可优先回看{chapter_text}，待模型服务恢复后再继续追问。"
        )
        return BranchQAResult(
            answer=answer,
            used_chapters=used_chapters,
            evidence=evidence[:5],
            chapter_evidence=chapter_evidence[:5],
            window_evidence=window_evidence[:3],
            graph_evidence=graph_evidence[:4],
            reasoning_paths=reasoning_paths[:5],
            graph_signals=graph_signals[:6] + [f"服务降级: {error_message[:80]}"],
            confidence=0.35,
            insufficient_context=True,
            answer_mode="degraded",
            degraded_reason=error_message[:240],
        )

    def answer_question(self, branch_id: str, question: str, limit: int = 5) -> BranchQAResult:
        """Answer a question from retrieval hits only."""

        question_type = self._classify_question(question)
        hits = self.retrieval_service.search_branch(branch_id, question, limit)
        hits = self._rank_hits_for_question(
            hits,
            question=question,
            question_type=question_type,
        )
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
        chapter_evidence: list[str] = []
        for hit in hits:
            used_chapters.append(hit.chapter_index)
            keywords = ', '.join(hit.keyword_list[:8])
            context_lines.append(
                f"[第{hit.chapter_index}章|{hit.title}|score={hit.score:.4f}]\n"
                f"摘要：{hit.summary_text}\n关键词：{keywords}"
            )
            chapter_line = f"第{hit.chapter_index}章：{hit.summary_text}"
            chapter_evidence.append(chapter_line)
            evidence.append(chapter_line)

        window_lines = self._window_context(branch_id, used_chapters)
        graph_lines = self._graph_context(branch_id, used_chapters)
        reasoning_paths, graph_signals = self._graph_reasoning_snapshot(
            branch_id,
            used_chapters,
            question_type=question_type,
        )
        window_evidence = [line for line in window_lines if line.strip()]
        graph_evidence = [line for line in graph_lines if line.strip()]
        evidence.extend(window_evidence[:2])
        evidence.extend(graph_evidence[:2])
        retrieval_context = '\n\n'.join(
            [f"[问题类型] {question_type}"] + context_lines + window_lines + graph_lines
        )
        prompt = build_branch_qa_prompt(
            question=question,
            retrieval_context=retrieval_context,
        )
        model = build_chat_model(
            self.settings,
            model_name=self.settings.llm_qa_model_name,
        )
        try:
            response = model.invoke(prompt)
            raw = AnalysisService._extract_json_payload(response)
            result = BranchQAResult.model_validate(raw)
            record_provider_health(ok=True, settings=self.settings)
        except Exception as exc:
            record_provider_health(ok=False, error_message=str(exc), settings=self.settings)
            return self._degraded_answer(
                question,
                used_chapters,
                evidence,
                chapter_evidence,
                window_evidence,
                graph_evidence,
                reasoning_paths,
                graph_signals,
                error_message=str(exc),
            )
        used_chapters = self._dedupe_chapters(used_chapters, limit=limit)
        evidence = self._dedupe_strings(evidence, limit=5)
        chapter_evidence = self._dedupe_strings(chapter_evidence, limit=5)
        window_evidence = self._dedupe_strings(window_evidence, limit=3)
        graph_evidence = self._dedupe_strings(graph_evidence, limit=4)
        if not result.used_chapters:
            result = result.model_copy(update={'used_chapters': used_chapters})
        else:
            result = result.model_copy(update={'used_chapters': self._dedupe_chapters(result.used_chapters, limit=5)})
        if not result.evidence:
            result = result.model_copy(update={'evidence': evidence})
        else:
            result = result.model_copy(update={'evidence': self._dedupe_strings(result.evidence, limit=5)})
        if not result.chapter_evidence:
            result = result.model_copy(update={'chapter_evidence': chapter_evidence})
        else:
            result = result.model_copy(update={'chapter_evidence': self._dedupe_strings(result.chapter_evidence, limit=5)})
        if not result.window_evidence:
            result = result.model_copy(update={'window_evidence': window_evidence})
        else:
            result = result.model_copy(update={'window_evidence': self._dedupe_strings(result.window_evidence, limit=3)})
        if not result.graph_evidence:
            result = result.model_copy(update={'graph_evidence': graph_evidence})
        else:
            result = result.model_copy(update={'graph_evidence': self._dedupe_strings(result.graph_evidence, limit=4)})
        if not result.reasoning_paths:
            result = result.model_copy(update={'reasoning_paths': reasoning_paths[:5]})
        else:
            result = result.model_copy(update={'reasoning_paths': self._dedupe_strings(result.reasoning_paths, limit=5)})
        if not result.graph_signals:
            result = result.model_copy(update={'graph_signals': graph_signals[:6]})
        else:
            result = result.model_copy(update={'graph_signals': self._dedupe_strings(result.graph_signals, limit=6)})
        if question_type in {'timeline', 'foreshadow', 'relation'} and len(result.used_chapters) < 2:
            result = result.model_copy(
                update={
                    'insufficient_context': True,
                    'confidence': min(result.confidence, 0.45),
                }
            )
        return result
