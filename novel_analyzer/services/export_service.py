"""Export helpers for directly usable branch and chapter bundles."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    FactRecord,
    GraphEdge,
    GraphNode,
    RetrievalDocument,
    WindowArtifact,
)
from novel_analyzer.domain.schemas import BranchQAContextOutput, ChapterQAContextOutput
from novel_analyzer.services.chapter_index_service import ChapterIndexService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.status_service import StatusService


class ExportService:
    """Build directly consumable JSON bundles for branches and chapters."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.status_service = StatusService(session)
        self.chapter_index_service = ChapterIndexService(session)
        self.graph_service = GraphService(session)

    @staticmethod
    def _recommended_questions_for_chapter(
        artifact: dict[str, object],
        retrieval: dict[str, object],
    ) -> list[str]:
        """Build guided follow-up questions for one chapter QA context."""

        title = str(artifact.get('normalized_title', '')).strip()
        chapter_summary = str(artifact.get('chapter_summary', '')).strip()
        key_events_raw = cast(list[object], artifact.get('key_events', []))
        unresolved_raw = cast(list[object], artifact.get('unresolved_threads', []))
        transitions_raw = cast(list[object], artifact.get('state_transition_notes', []))
        query_hints_raw = cast(list[object], retrieval.get('query_hints', []))
        key_events = [
            str(item).strip()
            for item in key_events_raw
            if isinstance(item, str) and str(item).strip()
        ]
        unresolved = [
            str(item).strip()
            for item in unresolved_raw
            if isinstance(item, str) and str(item).strip()
        ]
        transitions = [
            str(item).strip()
            for item in transitions_raw
            if isinstance(item, str) and str(item).strip()
        ]
        query_hints = [
            str(item).strip()
            for item in query_hints_raw
            if isinstance(item, str) and str(item).strip()
        ]
        questions: list[str] = []
        if title:
            questions.append(
                f'第{artifact.get("chapter_index", "?")}章《{title}》的核心推进是什么？'
            )
        if chapter_summary:
            questions.append('这一章里最关键的剧情兑现点是什么？')
        for item in key_events[:2]:
            questions.append(f'事件“{item}”对后续章节会产生什么影响？')
        for item in unresolved[:2]:
            questions.append(f'未解线程“{item}”后续最可能如何推进？')
        for item in transitions[:2]:
            questions.append(f'状态推进“{item}”是如何通过文本建立出来的？')
        questions.extend(query_hints[:3])
        return list(dict.fromkeys(item for item in questions if item))

    @staticmethod
    def _recommended_questions_for_branch(
        bundle: dict[str, object],
    ) -> list[str]:
        """Build guided follow-up questions for a branch QA context."""

        state_summary = cast(dict[str, object], bundle.get('state_summary', {}))
        chapter_output_summary = cast(dict[str, object], bundle.get('chapter_output_summary', {}))
        questions: list[str] = []
        for item in cast(list[object], state_summary.get('escalated_conflicts', []))[:3]:
            label = str(item).strip()
            if label:
                questions.append(f'冲突“{label}”是如何逐章升级的？')
        for item in cast(list[object], state_summary.get('paid_off_foreshadowing', []))[:3]:
            label = str(item).strip()
            if label:
                questions.append(f'伏笔“{label}”是在哪些章节逐步兑现的？')
        for item in cast(list[object], state_summary.get('constraining_world_rules', []))[:3]:
            label = str(item).strip()
            if label:
                questions.append(f'规则“{label}”如何持续影响这条故事线？')
        unresolved = cast(list[object], chapter_output_summary.get('unresolved_threads', []))
        for item in unresolved[:3]:
            if isinstance(item, dict):
                note = str(item.get('note', '')).strip()
                chapter_index = item.get('chapter_index')
                if note:
                    questions.append(f'第{chapter_index}章留下的未解线程“{note}”后续怎么承接？')
        return list(dict.fromkeys(item for item in questions if item))

    @staticmethod
    def _thematic_contexts_for_branch(bundle: dict[str, object]) -> dict[str, object]:
        """Build thematic QA entry points for downstream tools."""

        state_summary = cast(dict[str, object], bundle.get('state_summary', {}))
        chapter_output_summary = cast(dict[str, object], bundle.get('chapter_output_summary', {}))
        reasoning_graph = cast(dict[str, object], bundle.get('reasoning_graph', {}))
        central_nodes = cast(list[object], reasoning_graph.get('central_nodes', []))
        retrieval_documents = cast(list[object], bundle.get('retrieval_documents', []))

        character_focus = []
        for item in central_nodes:
            if isinstance(item, dict) and item.get('node_type') == 'entity':
                label = str(item.get('label', '')).strip()
                if label:
                    character_focus.append(label)

        def notes_from_summary(key: str, limit: int = 6) -> list[str]:
            items = cast(list[object], state_summary.get(key, []))
            return [str(item).strip() for item in items[:limit] if str(item).strip()]

        def rows_from_chapter_output(key: str, limit: int = 6) -> list[dict[str, object]]:
            rows = cast(list[object], chapter_output_summary.get(key, []))
            result: list[dict[str, object]] = []
            for row in rows[:limit]:
                if isinstance(row, dict):
                    result.append(
                        {
                            'chapter_index': row.get('chapter_index'),
                            'note': row.get('note'),
                        }
                    )
            return result

        doc_summaries = []
        for item in retrieval_documents[:6]:
            if isinstance(item, dict):
                doc_summaries.append(
                    {
                        'chapter_index': item.get('chapter_index'),
                        'title': item.get('title'),
                        'summary_text': item.get('summary_text'),
                    }
                )

        def score_text(text: str, keywords: list[str]) -> int:
            normalized = text.strip()
            if not normalized:
                return 0
            return sum(
                1
                for keyword in keywords
                if keyword and keyword in normalized
            )

        def related_chapters_from_threads(
            key: str,
            keywords: list[str],
            limit: int = 6,
        ) -> list[int]:
            rows = rows_from_chapter_output(key, limit)
            scored: list[tuple[int, int]] = []
            for row in rows:
                chapter_index = row.get('chapter_index')
                note = str(row.get('note', '')).strip()
                if isinstance(chapter_index, int):
                    score = score_text(note, keywords)
                    scored.append((chapter_index, score))
            scored.sort(key=lambda item: (-item[1], item[0]))
            return [chapter for chapter, _ in scored[:limit]]

        def evidence_summaries_for_chapters(
            chapters: list[int],
            keywords: list[str],
            limit: int = 4,
        ) -> list[str]:
            lines: list[tuple[str, int]] = []
            for item in doc_summaries:
                chapter_index = item.get('chapter_index')
                if chapter_index in chapters:
                    title = item.get('title')
                    summary_text = item.get('summary_text')
                    line = f"第{chapter_index}章《{title}》：{summary_text}"
                    lines.append((line, score_text(line, keywords)))
            lines.sort(key=lambda item: -item[1])
            return [line for line, _ in lines[:limit]]

        def question_sequence(questions: list[str]) -> list[dict[str, object]]:
            return [
                {'step': index, 'question': question}
                for index, question in enumerate(questions[:4], start=1)
            ]

        def thematic_reasoning_paths(keywords: list[str], limit: int = 6) -> list[str]:
            paths = cast(list[object], reasoning_graph.get('reasoning_paths', []))
            matched: list[str] = []
            for item in paths:
                text = str(item).strip()
                if text and any(keyword in text for keyword in keywords if keyword):
                    matched.append(text)
            return matched[:limit]

        def thematic_state_signals(keywords: list[str], limit: int = 6) -> list[str]:
            signals: list[str] = []
            for bucket, prefix in [
                ('new_conflicts', '活跃冲突'),
                ('escalated_conflicts', '升级冲突'),
                ('paid_off_foreshadowing', '已兑现伏笔'),
                ('new_foreshadowing', '待回收伏笔'),
                ('constraining_world_rules', '规则约束'),
                ('evolved_relations', '关系变化'),
            ]:
                for item in notes_from_summary(bucket, limit):
                    if any(keyword in item for keyword in keywords if keyword):
                        signals.append(f'{prefix}: {item}')
            return signals[:limit]

        def thematic_supporting_facts(keywords: list[str], limit: int = 8) -> list[str]:
            facts = cast(list[object], bundle.get('graph_nodes', []))
            rows: list[str] = []
            for item in facts:
                if not isinstance(item, dict):
                    continue
                label = str(item.get('label', '')).strip()
                node_type = str(item.get('node_type', '')).strip()
                if label and any(keyword in label for keyword in keywords if keyword):
                    rows.append(f'{node_type}:{label}')
            return rows[:limit]

        def thematic_node_refs(keywords: list[str], limit: int = 8) -> list[dict[str, object]]:
            nodes = cast(list[object], bundle.get('graph_nodes', []))
            refs: list[dict[str, object]] = []
            for item in nodes:
                if not isinstance(item, dict):
                    continue
                label = str(item.get('label', '')).strip()
                if label and any(keyword in label for keyword in keywords if keyword):
                    refs.append(
                        {
                            'node_type': item.get('node_type'),
                            'label': label,
                            'chapter_first_seen': item.get('chapter_first_seen'),
                            'chapter_last_seen': item.get('chapter_last_seen'),
                        }
                    )
            return refs[:limit]

        def thematic_edge_refs(keywords: list[str], limit: int = 8) -> list[dict[str, object]]:
            edges = cast(list[object], reasoning_graph.get('edges', []))
            refs: list[dict[str, object]] = []
            for item in edges:
                if not isinstance(item, dict):
                    continue
                source = str(item.get('source', '')).strip()
                target = str(item.get('target', '')).strip()
                if any(
                    keyword in source or keyword in target
                    for keyword in keywords
                    if keyword
                ):
                    refs.append(
                        {
                            'edge_type': item.get('edge_type'),
                            'source': source,
                            'target': target,
                            'chapter_first_seen': item.get('chapter_first_seen'),
                            'chapter_last_seen': item.get('chapter_last_seen'),
                        }
                    )
            return refs[:limit]

        def timeline_points(
            chapters: list[int],
            facts: list[str],
            limit: int = 8,
        ) -> list[dict[str, object]]:
            points: list[dict[str, object]] = []
            for chapter, fact in zip(chapters[:limit], facts[:limit], strict=False):
                points.append({'chapter_index': chapter, 'summary': fact})
            return points

        character_questions = [
            f'角色“{label}”在当前分支的成长线如何推进？'
            for label in character_focus[:4]
        ]
        conflict_questions = [
            f'冲突“{label}”是如何升级并影响人物选择的？'
            for label in notes_from_summary('escalated_conflicts', 4)
        ]
        foreshadow_questions = [
            f'伏笔“{label}”的铺垫与兑现节奏是怎样的？'
            for label in notes_from_summary('paid_off_foreshadowing', 4)
        ]
        rule_questions = [
            f'规则“{label}”如何塑造故事推进与人物处境？'
            for label in notes_from_summary('constraining_world_rules', 4)
        ]

        conflict_keywords = notes_from_summary('escalated_conflicts', 4)
        foreshadow_keywords = (
            notes_from_summary('new_foreshadowing', 4)
            + notes_from_summary('paid_off_foreshadowing', 4)
        )[:4]
        rule_keywords = notes_from_summary('constraining_world_rules', 4)
        conflict_chapters = related_chapters_from_threads(
            'unresolved_threads',
            conflict_keywords,
        )
        foreshadow_chapters = related_chapters_from_threads(
            'state_transition_notes',
            foreshadow_keywords,
        )
        rule_chapters = related_chapters_from_threads(
            'evidence_backed_resolutions',
            rule_keywords,
        )
        character_matches: list[tuple[int, int]] = []
        for item in doc_summaries:
            chapter_index = item.get('chapter_index')
            if not isinstance(chapter_index, int):
                continue
            summary_text = str(item.get('summary_text', ''))
            score = score_text(summary_text, character_focus[:2])
            if score > 0:
                character_matches.append((chapter_index, score))
        character_matches.sort(key=lambda item: (-item[1], item[0]))
        character_chapters = [chapter for chapter, _ in character_matches[:6]]

        return {
            'character_arc': {
                'focus_entities': character_focus[:8],
                'recommended_questions': character_questions,
                'question_sequence': question_sequence(character_questions),
                'related_chapters': character_chapters,
                'evidence_summaries': evidence_summaries_for_chapters(
                    character_chapters,
                    character_focus[:4],
                ),
                'reasoning_paths': thematic_reasoning_paths(character_focus[:4]),
                'state_signals': thematic_state_signals(character_focus[:4]),
                'supporting_facts': thematic_supporting_facts(character_focus[:4]),
                'node_refs': thematic_node_refs(character_focus[:4]),
                'edge_refs': thematic_edge_refs(character_focus[:4]),
                'timeline_points': timeline_points(
                    character_chapters,
                    evidence_summaries_for_chapters(character_chapters, character_focus[:4]),
                ),
                'document_summaries': doc_summaries,
            },
            'conflict_arc': {
                'active_conflicts': notes_from_summary('new_conflicts'),
                'escalated_conflicts': notes_from_summary('escalated_conflicts'),
                'recommended_questions': conflict_questions,
                'question_sequence': question_sequence(conflict_questions),
                'related_chapters': conflict_chapters,
                'evidence_summaries': evidence_summaries_for_chapters(
                    conflict_chapters,
                    conflict_keywords,
                ),
                'reasoning_paths': thematic_reasoning_paths(
                    notes_from_summary('escalated_conflicts', 4)
                ),
                'state_signals': thematic_state_signals(
                    notes_from_summary('escalated_conflicts', 4)
                ),
                'supporting_facts': thematic_supporting_facts(
                    notes_from_summary('escalated_conflicts', 4)
                ),
                'node_refs': thematic_node_refs(notes_from_summary('escalated_conflicts', 4)),
                'edge_refs': thematic_edge_refs(notes_from_summary('escalated_conflicts', 4)),
                'timeline_points': timeline_points(
                    conflict_chapters,
                    evidence_summaries_for_chapters(conflict_chapters, conflict_keywords),
                ),
                'chapter_threads': rows_from_chapter_output('unresolved_threads'),
            },
            'foreshadow_arc': {
                'open_or_paid_off': (
                    notes_from_summary('new_foreshadowing')
                    + notes_from_summary('paid_off_foreshadowing')
                )[:8],
                'recommended_questions': foreshadow_questions,
                'question_sequence': question_sequence(foreshadow_questions),
                'related_chapters': foreshadow_chapters,
                'evidence_summaries': evidence_summaries_for_chapters(
                    foreshadow_chapters,
                    foreshadow_keywords,
                ),
                'reasoning_paths': thematic_reasoning_paths(
                    notes_from_summary('paid_off_foreshadowing', 4)
                ),
                'state_signals': thematic_state_signals(
                    (
                        notes_from_summary('new_foreshadowing', 4)
                        + notes_from_summary('paid_off_foreshadowing', 4)
                    )[:4]
                ),
                'supporting_facts': thematic_supporting_facts(
                    (
                        notes_from_summary('new_foreshadowing', 4)
                        + notes_from_summary('paid_off_foreshadowing', 4)
                    )[:4]
                ),
                'node_refs': thematic_node_refs(
                    (
                        notes_from_summary('new_foreshadowing', 4)
                        + notes_from_summary('paid_off_foreshadowing', 4)
                    )[:4]
                ),
                'edge_refs': thematic_edge_refs(
                    (
                        notes_from_summary('new_foreshadowing', 4)
                        + notes_from_summary('paid_off_foreshadowing', 4)
                    )[:4]
                ),
                'timeline_points': timeline_points(
                    foreshadow_chapters,
                    evidence_summaries_for_chapters(foreshadow_chapters, foreshadow_keywords),
                ),
                'chapter_threads': rows_from_chapter_output('state_transition_notes'),
            },
            'world_rule_arc': {
                'rules': (
                    notes_from_summary('observed_world_rules')
                    + notes_from_summary('constraining_world_rules')
                )[:8],
                'recommended_questions': rule_questions,
                'question_sequence': question_sequence(rule_questions),
                'related_chapters': rule_chapters,
                'evidence_summaries': evidence_summaries_for_chapters(
                    rule_chapters,
                    rule_keywords,
                ),
                'reasoning_paths': thematic_reasoning_paths(
                    notes_from_summary('constraining_world_rules', 4)
                ),
                'state_signals': thematic_state_signals(
                    notes_from_summary('constraining_world_rules', 4)
                ),
                'supporting_facts': thematic_supporting_facts(
                    notes_from_summary('constraining_world_rules', 4)
                ),
                'node_refs': thematic_node_refs(notes_from_summary('constraining_world_rules', 4)),
                'edge_refs': thematic_edge_refs(notes_from_summary('constraining_world_rules', 4)),
                'timeline_points': timeline_points(
                    rule_chapters,
                    evidence_summaries_for_chapters(rule_chapters, rule_keywords),
                ),
                'chapter_threads': rows_from_chapter_output('evidence_backed_resolutions'),
            },
        }

    @staticmethod
    def _aggregate_chapter_output_summaries(
        artifacts: Sequence[ChapterArtifact],
    ) -> dict[str, object]:
        """Aggregate chapter-level transition/resolution/thread notes for branch outputs."""

        def collect(key: str) -> list[dict[str, object]]:
            rows: list[dict[str, object]] = []
            for artifact in artifacts:
                payload = artifact.payload_json
                raw_items = payload.get(key, [])
                if not isinstance(raw_items, list):
                    continue
                for item in raw_items:
                    text = str(item).strip()
                    if text:
                        rows.append(
                            {
                                'chapter_index': artifact.chapter_index,
                                'note': text,
                            }
                        )
            return rows

        return {
            'state_transition_notes': collect('state_transition_notes'),
            'evidence_backed_resolutions': collect('evidence_backed_resolutions'),
            'unresolved_threads': collect('unresolved_threads'),
        }

    def export_branch_bundle(self, run_id: str, branch_id: str) -> dict[str, object]:
        """Return a JSON-serializable bundle for one branch."""

        status = self.status_service.get_run_status(run_id, branch_id)
        artifacts = self.session.scalars(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.visibility == 'active')
            .order_by(ChapterArtifact.chapter_index)
        ).all()
        windows = self.session.scalars(
            select(WindowArtifact)
            .where(WindowArtifact.branch_id == branch_id)
            .order_by(WindowArtifact.window_start_chapter)
        ).all()
        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .order_by(GraphNode.node_type, GraphNode.label)
        ).all()
        edges = self.session.scalars(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .order_by(GraphEdge.edge_type)
        ).all()
        reasoning_graph = self.graph_service.reasoning_snapshot(branch_id)
        return {
            'status': {
                key: getattr(status, key) for key in status.__dataclass_fields__
            },
            'chapter_index': [
                {key: getattr(row, key) for key in row.__dataclass_fields__}
                for row in self.chapter_index_service.list_rows(branch_id)
            ],
            'windows': [window.payload_json for window in windows],
            'graph_nodes': [
                {
                    'node_type': node.node_type,
                    'label': node.label,
                    'chapter_first_seen': node.chapter_first_seen,
                    'chapter_last_seen': node.chapter_last_seen,
                    'occurrence_count': node.occurrence_count,
                    'metadata': node.metadata_json,
                }
                for node in nodes
            ],
            'graph_edges': [
                {
                    'edge_type': edge.edge_type,
                    'source_node_id': edge.source_node_id,
                    'target_node_id': edge.target_node_id,
                    'weight': edge.weight,
                    'chapter_first_seen': edge.chapter_first_seen,
                    'chapter_last_seen': edge.chapter_last_seen,
                    'metadata': edge.metadata_json,
                }
                for edge in edges
            ],
            'reasoning_graph': reasoning_graph,
            'state_summary': self.graph_service.state_summary_from_snapshot(reasoning_graph),
            'chapter_output_summary': self._aggregate_chapter_output_summaries(artifacts),
        }

    def export_chapter_bundle(self, branch_id: str, chapter_index: int) -> dict[str, object]:
        """Return a chapter-level bundle with artifact, facts, retrieval, and graph slices."""

        artifact = self.session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index == chapter_index)
            .where(ChapterArtifact.visibility == 'active')
            .order_by(ChapterArtifact.created_at.desc())
        )
        if artifact is None:
            raise ValueError('chapter artifact not found')

        facts = self.session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index == chapter_index)
            .order_by(FactRecord.fact_type, FactRecord.label)
        ).all()
        retrieval = self.session.scalar(
            select(RetrievalDocument)
            .where(RetrievalDocument.branch_id == branch_id)
            .where(RetrievalDocument.chapter_index == chapter_index)
        )
        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.chapter_first_seen <= chapter_index)
            .where(GraphNode.chapter_last_seen >= chapter_index)
            .order_by(GraphNode.node_type, GraphNode.label)
        ).all()
        node_by_id = {node.id: node for node in nodes}
        edges = self.session.scalars(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.chapter_first_seen <= chapter_index)
            .where(GraphEdge.chapter_last_seen >= chapter_index)
            .order_by(GraphEdge.edge_type)
        ).all()

        reasoning_graph = self.graph_service.reasoning_snapshot(
            branch_id,
            upto_chapter=chapter_index,
        )
        state_summary = self.graph_service.state_summary_from_snapshot(
            reasoning_graph,
            chapter_index=chapter_index,
        )
        artifact_payload = {
            **artifact.payload_json,
            'state_summary': state_summary,
        }

        return {
            'chapter_index': chapter_index,
            'artifact': artifact_payload,
            'facts': [
                {
                    'fact_type': fact.fact_type,
                    'label': fact.label,
                    'confidence': fact.confidence,
                    'evidence_list': fact.evidence_list,
                }
                for fact in facts
            ],
            'retrieval': {
                'title': retrieval.title if retrieval else None,
                'summary_text': retrieval.summary_text if retrieval else None,
                'keyword_list': retrieval.keyword_list if retrieval else [],
                'query_hints': retrieval.query_hints if retrieval else [],
            },
            'graph_nodes': [
                {
                    'node_type': node.node_type,
                    'label': node.label,
                    'occurrence_count': node.occurrence_count,
                    'metadata': node.metadata_json,
                }
                for node in nodes
            ],
            'graph_edges': [
                {
                    'edge_type': edge.edge_type,
                    'source': (
                        node_by_id[edge.source_node_id].label
                        if edge.source_node_id in node_by_id
                        else edge.source_node_id
                    ),
                    'target': (
                        node_by_id[edge.target_node_id].label
                        if edge.target_node_id in node_by_id
                        else edge.target_node_id
                    ),
                    'weight': edge.weight,
                    'metadata': edge.metadata_json,
                }
                for edge in edges
            ],
            'reasoning_graph': reasoning_graph,
            'state_summary': state_summary,
        }

    def export_chapter_qa_context(self, branch_id: str, chapter_index: int) -> dict[str, object]:
        """Return a question-answering context package for one chapter."""

        bundle = self.export_chapter_bundle(branch_id, chapter_index)
        artifact = cast(dict[str, object], bundle['artifact'])
        retrieval = cast(dict[str, object], bundle['retrieval'])
        payload = {
            'chapter_index': chapter_index,
            'title': artifact.get('normalized_title'),
            'chapter_summary': artifact.get('chapter_summary'),
            'key_events': artifact.get('key_events', []),
            'state_transition_notes': artifact.get('state_transition_notes', []),
            'evidence_backed_resolutions': artifact.get('evidence_backed_resolutions', []),
            'unresolved_threads': artifact.get('unresolved_threads', []),
            'facts': bundle['facts'],
            'retrieval': retrieval,
            'query_hints': retrieval.get('query_hints', []),
            'recommended_questions': self._recommended_questions_for_chapter(
                artifact,
                retrieval,
            ),
            'reasoning_graph': bundle['reasoning_graph'],
            'state_summary': bundle['state_summary'],
        }
        return ChapterQAContextOutput.model_validate(payload).model_dump(mode='json')

    def export_branch_qa_context(self, run_id: str, branch_id: str) -> dict[str, object]:
        """Return a branch-level QA context package for downstream tools."""

        bundle = self.export_branch_bundle(run_id, branch_id)
        docs = self.session.scalars(
            select(RetrievalDocument)
            .where(RetrievalDocument.branch_id == branch_id)
            .order_by(RetrievalDocument.chapter_index)
        ).all()
        payload = {
            'status': bundle['status'],
            'chapter_index': bundle['chapter_index'],
            'windows': bundle['windows'],
            'state_summary': bundle['state_summary'],
            'chapter_output_summary': bundle['chapter_output_summary'],
            'reasoning_graph': bundle['reasoning_graph'],
            'retrieval_documents': [
                {
                    'chapter_index': doc.chapter_index,
                    'title': doc.title,
                    'summary_text': doc.summary_text,
                    'keyword_list': doc.keyword_list,
                    'query_hints': doc.query_hints,
                }
                for doc in docs
            ],
        }
        payload['recommended_questions'] = self._recommended_questions_for_branch(payload)
        payload['thematic_contexts'] = self._thematic_contexts_for_branch(payload)
        return BranchQAContextOutput.model_validate(payload).model_dump(mode='json')
