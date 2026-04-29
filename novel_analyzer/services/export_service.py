"""Export helpers for directly usable branch and chapter bundles."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    ClusterReviewRecord,
    ChapterRiskCardRecord,
    FactRecord,
    GateCheckerResultRecord,
    GraphEdge,
    GraphNode,
    RetrievalDocument,
    WindowArtifact,
)
from novel_analyzer.domain.schemas import BranchQAContextOutput, ChapterQAContextOutput
from novel_analyzer.runtime.cluster_review_state import read_cluster_review_state
from novel_analyzer.services.cluster_review_service import ClusterReviewService
from novel_analyzer.services.chapter_index_service import ChapterIndexService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.run_service import RunService
from novel_analyzer.services.status_service import StatusService


class ExportService:
    """Build directly consumable JSON bundles for branches and chapters."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.status_service = StatusService(session)
        self.chapter_index_service = ChapterIndexService(session)
        self.graph_service = GraphService(session)
        self.run_service = RunService(session)
        self.cluster_review_service = ClusterReviewService(session)

    @staticmethod
    def _is_missing_relation_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return "relation" in message and "does not exist" in message

    @staticmethod
    def _severity_rank(level: str | None) -> int:
        return {
            None: -1,
            "low": 0,
            "medium": 1,
            "high": 2,
            "critical": 3,
        }.get(level, -1)

    @staticmethod
    def _risk_specificity_rank(risk_type: str | None) -> int:
        normalized = str(risk_type or '').strip()
        if normalized in {'human_review_candidate', 'rule_review_candidate', 'logic_review_candidate', 'timeline_review_candidate', 'power_review_candidate'}:
            return 0
        if normalized in {'title_only_inference_candidate'}:
            return -1
        if normalized.endswith('_candidate'):
            return 1
        return 2

    @staticmethod
    def _dedupe_preview(items: list[object], limit: int) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
            if len(result) >= limit:
                break
        return result

    @classmethod
    def _suppress_generic_review_candidates(
        cls,
        risks: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        if not risks:
            return []
        has_specific = any(
            cls._risk_specificity_rank(cast(str | None, risk.get('risk_type'))) > 0
            for risk in risks
        )
        if not has_specific:
            return risks
        filtered = [
            risk for risk in risks
            if cls._risk_specificity_rank(cast(str | None, risk.get('risk_type'))) > 0
        ]
        return filtered or risks

    @staticmethod
    def _derive_cluster_status(
        *,
        chapter_count: int,
        max_confidence: float,
        review_priority_value: str,
    ) -> str:
        """Derive a minimal runtime status for one cluster.

        Current semantics are runtime-only heuristics:
        - needs_review: should be surfaced first to humans
        - open: candidate cluster exists but urgency is lower
        - resolved: reserved for future workflow write-back
        """
        if review_priority_value == 'P1':
            return 'needs_review'
        if chapter_count >= 3 or max_confidence >= 0.5:
            return 'needs_review'
        return 'open'

    @staticmethod
    def _cluster_pattern_rank(pattern_label: str | None) -> int:
        return {
            '持续型问题': 2,
            '集中爆发型问题': 1,
            '单点问题': 0,
        }.get(str(pattern_label or '').strip(), -1)

    @staticmethod
    def _review_result_label(review_result: str | None) -> str | None:
        return {
            'confirmed-issue': '确认有问题',
            'confirmed-benign': '确认无问题',
            'needs-escalation': '需要升级处理',
            'deferred': '暂缓判断',
            '': None,
        }.get(str(review_result or '').strip(), str(review_result or '').strip() or None)

    @classmethod
    def _chapter_continuity_preview(
        cls,
        chapter_index: int,
        chapter_output_summary: dict[str, object],
        state_summary: dict[str, object],
        reasoning_graph: dict[str, object],
    ) -> tuple[list[str], list[str]]:
        chapter_signals: list[str] = []
        branch_signals: list[str] = []

        for key, label in [
            ('state_transition_notes', '推进'),
            ('evidence_backed_resolutions', '解决'),
            ('unresolved_threads', '未解'),
        ]:
            rows = cast(list[object], chapter_output_summary.get(key, []))
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if int(row.get('chapter_index', 0) or 0) != chapter_index:
                    continue
                note = str(row.get('note') or '').strip()
                if note:
                    chapter_signals.append(f'{label}: {note}')

        branch_signals.extend(
            f'活跃冲突: {item}'
            for item in cast(list[object], reasoning_graph.get('active_conflicts', []))[:2]
            if str(item).strip()
        )
        branch_signals.extend(
            f'未回收伏笔: {item}'
            for item in cast(list[object], reasoning_graph.get('open_foreshadowing', []))[:2]
            if str(item).strip()
        )
        branch_signals.extend(
            f'近期时间线: {item}'
            for item in cast(list[object], reasoning_graph.get('recent_timeline', []))[-2:]
            if str(item).strip()
        )
        branch_signals.extend(
            f'规则约束: {item}'
            for item in cast(list[object], state_summary.get('constraining_world_rules', []))[:2]
            if str(item).strip()
        )

        return cls._dedupe_preview(chapter_signals, 3), cls._dedupe_preview(branch_signals, 4)

    @classmethod
    def _cluster_review_candidates(
        cls,
        review_candidates_summary: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        def cluster_title(checkers: list[str], risk_types: list[str]) -> str:
            checker = checkers[0] if checkers else 'unknown'
            risk_type = risk_types[0] if risk_types else 'review_candidate'
            if checker == 'character_ooc':
                return '人物连续性复核簇' if risk_type == 'human_review_candidate' else f'人物风险簇：{risk_type}'
            if checker == 'plot_logic_consistency':
                return '剧情因果复核簇' if 'candidate' in risk_type else f'剧情逻辑风险簇：{risk_type}'
            if checker == 'timeline_consistency':
                return '时间线复核簇' if 'candidate' in risk_type else f'时间线风险簇：{risk_type}'
            if checker == 'power_scaling_consistency':
                return '战力能力复核簇' if 'candidate' in risk_type else f'战力能力风险簇：{risk_type}'
            if checker == 'world_rule_consistency':
                return '规则一致性复核簇' if 'candidate' in risk_type else f'规则风险簇：{risk_type}'
            return f'风险问题簇：{risk_type}'

        def suggested_review_action(checkers: list[str], risk_types: list[str]) -> str:
            checker = checkers[0] if checkers else 'unknown'
            risk_type = risk_types[0] if risk_types else 'review_candidate'
            if checker == 'character_ooc':
                return '优先核对人物动机、关系与行为是否有前文支撑，避免只依据标题或摘要推断人物变化。'
            if checker == 'plot_logic_consistency':
                if 'resolution' in risk_type:
                    return '优先核对“已解决/已兑现”类表述是否真的有正文证据链闭合。'
                return '优先核对关键行动、结果与中间因果链是否缺少必要过渡或支撑。'
            if checker == 'timeline_consistency':
                return '优先核对事件先后顺序、恢复时长与同日多地切换是否存在时序冲突。'
            if checker == 'power_scaling_consistency':
                return '优先核对能力跃迁、越阶压制和新招式掌握是否有明确铺垫或限制条件。'
            if checker == 'world_rule_consistency':
                return '优先核对既有世界规则、约束条件和例外触发是否前后一致。'
            return '优先回看相关章节与证据预览，确认该候选是否仅为弱信号噪音。'

        def review_priority(chapter_count: int, max_confidence: float, checkers: list[str]) -> str:
            if max_confidence >= 0.75 or chapter_count >= 5:
                return 'P1'
            if max_confidence >= 0.5 or chapter_count >= 3:
                return 'P2'
            if 'character_ooc' in checkers and chapter_count >= 2:
                return 'P2'
            return 'P3'

        def cluster_pattern(chapters: list[int]) -> str:
            if len(chapters) <= 1:
                return '单点问题'
            span = max(chapters) - min(chapters)
            if span <= 3:
                return '集中爆发型问题'
            return '持续型问题'

        clusters: dict[str, dict[str, object]] = {}
        for item in review_candidates_summary:
            checker_names = cls._dedupe_preview(cast(list[object], item.get('checker_names', [])), 6)
            risk_types = cls._dedupe_preview(cast(list[object], item.get('risk_types', [])), 6)
            cluster_key = "|".join(checker_names + ["::"] + risk_types)
            cluster = clusters.setdefault(
                cluster_key,
                {
                    'cluster_key': cluster_key,
                    'checker_names': checker_names,
                    'risk_types': risk_types,
                    'cluster_title': cluster_title(checker_names, risk_types),
                    'suggested_review_action': suggested_review_action(checker_names, risk_types),
                    'review_priority': 'P3',
                    'cluster_status': 'open',
                    'chapter_count': 0,
                    'chapters': [],
                    'first_chapter': None,
                    'last_chapter': None,
                    'max_confidence': 0.0,
                    'titles': [],
                    'sample_summary': '',
                },
            )
            preferred_risk_type = next(
                iter(
                    sorted(
                        risk_types,
                        key=lambda risk_type: (
                            -cls._risk_specificity_rank(risk_type),
                            risk_type,
                        ),
                    )
                ),
                '',
            )
            if preferred_risk_type:
                cluster['cluster_title'] = cluster_title(checker_names, [preferred_risk_type])
                cluster['suggested_review_action'] = suggested_review_action(checker_names, [preferred_risk_type])
            chapter_index = int(item.get('chapter_index', 0))
            cluster['chapter_count'] = int(cluster.get('chapter_count', 0)) + 1
            cluster['chapters'] = sorted(set(cast(list[int], cluster.get('chapters', [])) + [chapter_index]))
            cluster['first_chapter'] = (
                chapter_index
                if cluster.get('first_chapter') is None
                else min(int(cluster.get('first_chapter', chapter_index)), chapter_index)
            )
            cluster['last_chapter'] = (
                chapter_index
                if cluster.get('last_chapter') is None
                else max(int(cluster.get('last_chapter', chapter_index)), chapter_index)
            )
            first_chapter = int(cluster.get('first_chapter', chapter_index) or chapter_index)
            last_chapter = int(cluster.get('last_chapter', chapter_index) or chapter_index)
            chapters = cast(list[int], cluster.get('chapters', []))
            cluster['chapter_span'] = (
                str(first_chapter)
                if first_chapter == last_chapter
                else f'{first_chapter}-{last_chapter}'
            )
            cluster['pattern_label'] = cluster_pattern(chapters)
            cluster['max_confidence'] = max(
                float(cluster.get('max_confidence', 0.0)),
                float(item.get('confidence') or 0.0),
            )
            cluster['review_priority'] = review_priority(
                int(cluster.get('chapter_count', 0)),
                float(cluster.get('max_confidence', 0.0)),
                checker_names,
            )
            cluster['cluster_status'] = cls._derive_cluster_status(
                chapter_count=int(cluster.get('chapter_count', 0)),
                max_confidence=float(cluster.get('max_confidence', 0.0)),
                review_priority_value=cast(str, cluster.get('review_priority', 'P3')),
            )
            cluster['titles'] = cls._dedupe_preview(
                cast(list[object], cluster.get('titles', [])) + [item.get('title')],
                4,
            )
            if item.get('summary'):
                current_summary = str(cluster.get('sample_summary') or '')
                next_summary = str(item.get('summary') or '')
                current_specificity = max(
                    (cls._risk_specificity_rank(risk_type) for risk_type in cast(list[str], cluster.get('risk_types', []))),
                    default=-1,
                )
                next_specificity = max(
                    (cls._risk_specificity_rank(risk_type) for risk_type in risk_types),
                    default=-1,
                )
                if (
                    not current_summary
                    or next_specificity > current_specificity
                    or (next_specificity == current_specificity and len(next_summary) > len(current_summary))
                ):
                    cluster['sample_summary'] = next_summary
        clustered = list(clusters.values())
        has_specific_cluster = any(
            max((cls._risk_specificity_rank(risk_type) for risk_type in cast(list[str], item.get('risk_types', []))), default=-1) > 0
            for item in clustered
        )
        if has_specific_cluster:
            filtered = [
                item for item in clustered
                if max((cls._risk_specificity_rank(risk_type) for risk_type in cast(list[str], item.get('risk_types', []))), default=-1) > 0
            ]
            clustered = filtered or clustered
        clustered.sort(
            key=lambda item: (
                {'needs_review': 0, 'reopened': 1, 'escalated': 2, 'reviewed': 3, 'open': 4, 'resolved': 5}.get(cast(str, item.get('cluster_status', 'open')), 6),
                {'P1': 0, 'P2': 1, 'P3': 2}.get(cast(str, item.get('review_priority', 'P3')), 3),
                -cls._cluster_pattern_rank(cast(str | None, item.get('pattern_label'))),
                -max((cls._risk_specificity_rank(risk_type) for risk_type in cast(list[str], item.get('risk_types', []))), default=-1),
                -int(item.get('chapter_count', 0)),
                -float(item.get('max_confidence', 0.0)),
                int(item.get('first_chapter', 0) or 0),
            )
        )
        return clustered[:20]

    @staticmethod
    def _build_audit_conclusion(
        *,
        completed_chapters: int,
        manifest_chapter_count: int,
        failed_summary: list[dict[str, object]],
        high_risk_chapters: list[int],
        review_candidate_count: int,
    ) -> dict[str, str]:
        completion_ratio = (
            (completed_chapters / manifest_chapter_count)
            if manifest_chapter_count > 0
            else 0.0
        )
        if failed_summary:
            content_judgement = (
                "当前分支已形成阶段性审查结果，但审查覆盖仍停留在已完成章节，"
                "尚不能覆盖后续未完成章节。"
            )
            risk_judgement = (
                "当前已完成章节未见明确高风险，但存在需人工复核的候选章节。"
                if review_candidate_count
                else "当前已完成章节未见明确高风险。"
            )
            blocking_judgement = "当前存在执行阻塞，阻塞主因是失败章节尚未恢复。"
            recommended_action = "先处理失败章节恢复执行，再结合风险候选章节做人工复核。"
        elif high_risk_chapters:
            content_judgement = (
                "当前分支已形成可用审查结果，且当前覆盖范围足以支撑阶段性内容判断。"
                if completion_ratio >= 0.8
                else "当前分支已形成可用的阶段性审查结果。"
            )
            risk_judgement = "当前分支存在高风险章节，后续使用结论前应优先人工复核。"
            blocking_judgement = "当前无执行阻塞。"
            recommended_action = "优先复核高风险章节，再决定是否继续使用下游结论。"
        elif review_candidate_count >= 5:
            content_judgement = (
                "当前分支已形成可用的阶段性审查结果，但候选风险分布较密集。"
            )
            risk_judgement = "当前未发现明确高风险，但人工复核候选较多，需谨慎使用整体稳定结论。"
            blocking_judgement = "当前无执行阻塞。"
            recommended_action = "按章节优先级批量复核候选章节，再决定是否给出整体稳定判断。"
        elif review_candidate_count > 0:
            content_judgement = (
                "当前分支已形成可用审查结果。"
                if completion_ratio >= 0.3
                else "当前分支已形成早期阶段审查结果。"
            )
            risk_judgement = "当前未发现明确高风险，但存在低/中风险人工复核候选。"
            blocking_judgement = "当前无执行阻塞。"
            recommended_action = "优先复核候选章节，再结合上下文决定是否继续推进。"
        else:
            content_judgement = (
                "当前分支已形成可用审查结果，章节连续性判断整体稳定。"
                if completion_ratio >= 0.3
                else "当前分支已形成早期阶段审查结果，目前未见明显风险候选。"
            )
            risk_judgement = "当前未发现明确风险候选，章节连续性结果整体稳定。"
            blocking_judgement = "当前无执行阻塞。"
            recommended_action = "可继续使用当前审查结果，并在新增章节后持续复查。"
        return {
            'content_judgement': content_judgement,
            'risk_judgement': risk_judgement,
            'blocking_judgement': blocking_judgement,
            'recommended_action': recommended_action,
        }

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
        chapter_rows = [
            {key: getattr(row, key) for key in row.__dataclass_fields__}
            for row in self.chapter_index_service.list_rows(branch_id)
        ]
        chapter_row_by_index = {
            int(row.get('chapter_index', 0)): row for row in chapter_rows
        }
        try:
            risk_cards = self.session.scalars(
                select(ChapterRiskCardRecord)
                .where(ChapterRiskCardRecord.branch_id == branch_id)
                .where(ChapterRiskCardRecord.visibility == 'active')
                .order_by(ChapterRiskCardRecord.chapter_index)
            ).all()
            checker_results = self.session.scalars(
                select(GateCheckerResultRecord)
                .where(GateCheckerResultRecord.branch_id == branch_id)
                .where(GateCheckerResultRecord.visibility == 'active')
                .order_by(GateCheckerResultRecord.chapter_index, GateCheckerResultRecord.checker_name)
            ).all()
        except ProgrammingError as exc:
            if not self._is_missing_relation_error(exc):
                raise
            self.session.rollback()
            risk_cards = []
            checker_results = []
        state_summary = self.graph_service.state_summary_from_snapshot(reasoning_graph)
        chapter_output_summary = self._aggregate_chapter_output_summaries(artifacts)
        risk_counts_by_domain: dict[str, int] = {}
        risk_counts_by_severity: dict[str, int] = {}
        high_risk_chapters: list[int] = []
        review_candidates_summary_by_chapter: dict[int, dict[str, object]] = {}
        for record in risk_cards:
            payload = cast(dict[str, object], record.payload_json)
            chapter_index = int(payload.get('chapter_index', 0))
            if str(payload.get('overall_risk_level', '')) == 'high':
                high_risk_chapters.append(chapter_index)
            for key, value in cast(dict[str, object], payload.get('risk_counts_by_domain', {})).items():
                risk_counts_by_domain[key] = risk_counts_by_domain.get(key, 0) + int(value)
            for key, value in cast(dict[str, object], payload.get('risk_counts_by_severity', {})).items():
                risk_counts_by_severity[key] = risk_counts_by_severity.get(key, 0) + int(value)
            top_risks = cast(list[dict[str, object]], payload.get('top_risks', []))
            top_risks = self._suppress_generic_review_candidates(top_risks)
            if top_risks:
                merged = review_candidates_summary_by_chapter.setdefault(
                    chapter_index,
                    {
                        'chapter_index': chapter_index,
                        'title': chapter_row_by_index.get(chapter_index, {}).get('title'),
                        'overall_risk_level': payload.get('overall_risk_level'),
                        'risk_count': 0,
                        'risk_types': [],
                        'checker_names': [],
                        'confidence': 0.0,
                        'summary': '',
                        'supporting_evidence_preview': [],
                        'counter_evidence_preview': [],
                        'needs_human_review': False,
                    },
                )
                merged['risk_count'] = max(int(merged.get('risk_count', 0)), len(top_risks))
                merged['overall_risk_level'] = (
                    payload.get('overall_risk_level')
                    if self._severity_rank(cast(str | None, payload.get('overall_risk_level')))
                    >= self._severity_rank(cast(str | None, merged.get('overall_risk_level')))
                    else merged.get('overall_risk_level')
                )
                merged['confidence'] = max(
                    float(merged.get('confidence', 0.0)),
                    max(float(risk.get('confidence') or 0.0) for risk in top_risks),
                )
                merged['needs_human_review'] = bool(merged.get('needs_human_review')) or any(
                    bool(risk.get('needs_human_review', True)) for risk in top_risks
                )
                merged['risk_types'] = self._dedupe_preview(
                    cast(list[object], merged.get('risk_types', []))
                    + [risk.get('risk_type') for risk in top_risks],
                    4,
                )
                merged['checker_names'] = self._dedupe_preview(
                    cast(list[object], merged.get('checker_names', []))
                    + [risk.get('checker_name') for risk in top_risks],
                    4,
                )
                top_risk = max(
                    top_risks,
                    key=lambda risk: (
                        self._risk_specificity_rank(cast(str | None, risk.get('risk_type'))),
                        self._severity_rank(cast(str | None, risk.get('severity'))),
                        float(risk.get('confidence') or 0.0),
                    ),
                )
                if not merged.get('summary') or len(str(top_risk.get('summary') or '')) > len(str(merged.get('summary') or '')):
                    merged['summary'] = top_risk.get('summary')
                merged['supporting_evidence_preview'] = self._dedupe_preview(
                    cast(list[object], merged.get('supporting_evidence_preview', []))
                    + [e for risk in top_risks for e in cast(list[object], risk.get('supporting_evidence', []))],
                    3,
                )
                merged['counter_evidence_preview'] = self._dedupe_preview(
                    cast(list[object], merged.get('counter_evidence_preview', []))
                    + [e for risk in top_risks for e in cast(list[object], risk.get('counter_evidence', []))],
                    2,
                )
                continuity_preview, branch_preview = self._chapter_continuity_preview(
                    chapter_index,
                    chapter_output_summary,
                    state_summary,
                    reasoning_graph,
                )
                merged['continuity_evidence_preview'] = continuity_preview
                merged['branch_signal_preview'] = branch_preview
        review_candidates_summary = list(review_candidates_summary_by_chapter.values())
        review_candidates_summary.sort(
            key=lambda item: (
                -self._severity_rank(cast(str | None, item.get('overall_risk_level'))),
                -max((self._risk_specificity_rank(risk_type) for risk_type in cast(list[str], item.get('risk_types', []))), default=-1),
                -int(item.get('risk_count', 0)),
                0 if bool(item.get('needs_human_review')) else 1,
                int(item.get('chapter_index', 0)),
            )
        )
        failed_summary = [
            {
                'chapter_index': item.chapter_index,
                'attempts': item.attempts,
                'error': item.last_error,
                'failure_class': item.failure_class,
                'failure_code': item.failure_code,
            }
            for item in self.run_service.list_failed_jobs(branch_id, limit=1000)
        ]
        audit_conclusion = self._build_audit_conclusion(
            completed_chapters=int(getattr(status, 'completed_chapters', 0)),
            manifest_chapter_count=int(getattr(status, 'manifest_chapter_count', 0)),
            failed_summary=failed_summary,
            high_risk_chapters=high_risk_chapters,
            review_candidate_count=len(review_candidates_summary),
        )
        review_candidate_clusters = self._cluster_review_candidates(review_candidates_summary)
        review_storage_mode = "db"
        try:
            persisted_cluster_states = self.cluster_review_service.read_branch(branch_id)
            history_by_cluster = {
                str(cluster.get('cluster_key') or ''): self.cluster_review_service.read_history(branch_id, str(cluster.get('cluster_key') or ''))
                for cluster in review_candidate_clusters
            }
        except ProgrammingError as exc:
            if not self._is_missing_relation_error(exc):
                raise
            self.session.rollback()
            persisted_cluster_states = read_cluster_review_state(branch_id)
            history_by_cluster = {}
            review_storage_mode = "file-fallback"
        for cluster in review_candidate_clusters:
            cluster_key = str(cluster.get('cluster_key') or '')
            override = persisted_cluster_states.get(str(cluster.get('cluster_key') or ''))
            if not override:
                override = {}
            if override.get('cluster_status'):
                cluster['cluster_status'] = override['cluster_status']
            if override.get('review_notes'):
                cluster['review_notes'] = override['review_notes']
            if override.get('review_owner'):
                cluster['review_owner'] = override['review_owner']
            if override.get('resolved_at'):
                cluster['resolved_at'] = override['resolved_at']
            if override.get('review_result'):
                cluster['review_result'] = override['review_result']
                cluster['review_result_label'] = self._review_result_label(override['review_result'])
            history = history_by_cluster.get(cluster_key, [])
            if history:
                cluster['review_history_count'] = len(history)
                cluster['review_history'] = history
                cluster['latest_review_event'] = history[-1]
        resolved_cluster_count = sum(
            1 for cluster in review_candidate_clusters
            if str(cluster.get('cluster_status') or '') == 'resolved'
        )
        needs_review_cluster_count = sum(
            1 for cluster in review_candidate_clusters
            if str(cluster.get('cluster_status') or '') == 'needs_review'
        )
        review_result_counts: dict[str, int] = {}
        review_owner_counts: dict[str, int] = {}
        latest_review_event_overall: dict[str, object] | None = None
        for cluster in review_candidate_clusters:
            result = str(cluster.get('review_result') or '').strip()
            if result:
                review_result_counts[result] = review_result_counts.get(result, 0) + 1
            owner = str(cluster.get('review_owner') or '').strip()
            if owner:
                review_owner_counts[owner] = review_owner_counts.get(owner, 0) + 1
            latest_event = cluster.get('latest_review_event')
            if isinstance(latest_event, dict) and latest_event:
                if latest_review_event_overall is None:
                    latest_review_event_overall = latest_event
                elif str(latest_event.get('review_owner') or '') and not str(latest_review_event_overall.get('review_owner') or ''):
                    latest_review_event_overall = latest_event
        effective_unresolved_cluster_count = sum(
            1
            for cluster in review_candidate_clusters
            if str(cluster.get('cluster_status') or '') != 'resolved'
            and str(cluster.get('review_result') or '') != 'confirmed-benign'
        )
        if resolved_cluster_count or needs_review_cluster_count:
            note_parts: list[str] = []
            if resolved_cluster_count:
                note_parts.append(f'已人工处理问题簇 {resolved_cluster_count} 个')
            if needs_review_cluster_count:
                note_parts.append(f'仍待人工复核问题簇 {needs_review_cluster_count} 个')
            audit_conclusion['review_progress_note'] = '；'.join(note_parts) + '。'
        if review_result_counts:
            result_note_parts: list[str] = []
            labels = {
                'confirmed-issue': '已确认有问题',
                'confirmed-benign': '已确认无问题',
                'needs-escalation': '需升级处理',
                'deferred': '暂缓判断',
            }
            for key in ['confirmed-issue', 'confirmed-benign', 'needs-escalation', 'deferred']:
                count = review_result_counts.get(key, 0)
                if count:
                    result_note_parts.append(f"{labels[key]} {count} 个")
            if result_note_parts:
                audit_conclusion['review_result_note'] = '；'.join(result_note_parts) + '。'
        audit_conclusion['review_storage_note'] = (
            '当前 review 数据来自数据库主路径。'
            if review_storage_mode == 'db'
            else '当前 review 数据来自兼容 fallback 路径。'
        )
        if review_owner_counts:
            owner, count = sorted(review_owner_counts.items(), key=lambda item: (-item[1], item[0]))[0]
            audit_conclusion['review_owner_note'] = f'当前已记录复核人中，{owner} 处理了 {count} 个问题簇。'
        if latest_review_event_overall:
            audit_conclusion['latest_review_note'] = (
                f"最近一次复核记录：状态={latest_review_event_overall.get('cluster_status')}，"
                f"结果={latest_review_event_overall.get('review_result')}，"
                f"处理人={latest_review_event_overall.get('review_owner') or 'unknown'}。"
            )
        if (
            not failed_summary
            and not high_risk_chapters
            and review_candidate_clusters
            and effective_unresolved_cluster_count == 0
        ):
            audit_conclusion['risk_judgement'] = '当前候选问题簇已完成人工复核，未见需继续升级的明确风险。'
            audit_conclusion['recommended_action'] = '可保留复核记录并继续后续章节审查。'
        return {
            'status': {
                key: getattr(status, key) for key in status.__dataclass_fields__
            },
            'chapter_index': chapter_rows,
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
            'state_summary': state_summary,
            'chapter_output_summary': chapter_output_summary,
            'failed_summary': failed_summary,
            'audit_conclusion': audit_conclusion,
            'review_storage_mode': review_storage_mode,
            'risk_summary': {
                'risk_card_count': len(risk_cards),
                'checker_result_count': len(checker_results),
                'review_candidate_count': len(review_candidates_summary),
                'high_risk_chapters': high_risk_chapters,
                'risk_counts_by_domain': risk_counts_by_domain,
                'risk_counts_by_severity': risk_counts_by_severity,
                'review_candidates_summary': review_candidates_summary[:20],
                'review_candidate_clusters': review_candidate_clusters,
            },
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
        try:
            risk_card = self.session.scalar(
                select(ChapterRiskCardRecord)
                .where(ChapterRiskCardRecord.branch_id == branch_id)
                .where(ChapterRiskCardRecord.chapter_index == chapter_index)
                .where(ChapterRiskCardRecord.visibility == 'active')
                .order_by(ChapterRiskCardRecord.created_at.desc())
            )
        except ProgrammingError as exc:
            if not self._is_missing_relation_error(exc):
                raise
            self.session.rollback()
            risk_card = None
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
            'risk_card': risk_card.payload_json if risk_card is not None else None,
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
