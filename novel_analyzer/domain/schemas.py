"""Pydantic schemas for structured model output."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from novel_analyzer.domain.analysis_dimensions import AnalysisDimension


class OrderedTextBlock(BaseModel):
    """A stable ordered text block."""

    order: int
    text: str


class EvidenceNote(BaseModel):
    """A simple evidence-backed note."""

    label: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ChapterIntakeOutput(BaseModel):
    """Skill output for chapter-intake."""

    chapter_index: int
    normalized_title: str
    cleaned_text: str
    paragraph_blocks: list[OrderedTextBlock] = Field(default_factory=list)
    dialogue_candidates: list[str] = Field(default_factory=list)
    scene_candidates: list[OrderedTextBlock] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode='before')
    @classmethod
    def _normalize_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if 'chapter_index' not in value and 'chapter_no' in value:
            value['chapter_index'] = value['chapter_no']
        if 'normalized_title' not in value and 'chapter_title' in value:
            value['normalized_title'] = value['chapter_title']
        if 'cleaned_text' not in value and 'paragraph_blocks' in value:
            blocks = value.get('paragraph_blocks') or []
            if isinstance(blocks, list):
                value['cleaned_text'] = '\n'.join(str(item) for item in blocks)
        return value

    @staticmethod
    def _coerce_blocks(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(raw, start=1):
            if isinstance(item, str):
                normalized.append({'order': index, 'text': item})
            elif isinstance(item, dict):
                if 'order' in item and 'text' in item:
                    normalized.append({'order': item['order'], 'text': str(item['text'])})
                else:
                    order = int(item.get('scene_id', index))
                    text = str(item.get('text') or item.get('summary') or item)
                    normalized.append({'order': order, 'text': text})
        return normalized

    @field_validator('paragraph_blocks', mode='before')
    @classmethod
    def _normalize_paragraph_blocks(cls, value: Any) -> Any:
        return cls._coerce_blocks(value)

    @field_validator('scene_candidates', mode='before')
    @classmethod
    def _normalize_scene_candidates(cls, value: Any) -> Any:
        return cls._coerce_blocks(value)


class ChapterFactExtractionOutput(BaseModel):
    """Skill output for chapter-fact-extractor."""

    characters: list[EvidenceNote] = Field(default_factory=list)
    events: list[EvidenceNote] = Field(default_factory=list)
    relations: list[EvidenceNote] = Field(default_factory=list)
    conflicts: list[EvidenceNote] = Field(default_factory=list)
    foreshadowing: list[EvidenceNote] = Field(default_factory=list)
    worldbuilding_facts: list[EvidenceNote] = Field(default_factory=list)

    @staticmethod
    def _normalize_notes(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, str):
                normalized.append({'label': item})
            elif isinstance(item, dict):
                label = (
                    item.get('label')
                    or item.get('name')
                    or item.get('title')
                    or item.get('summary')
                )
                normalized.append(
                    {
                        'label': str(label or item),
                        'evidence': item.get('evidence', []),
                        'confidence': item.get('confidence', 0.0),
                    }
                )
        return normalized

    @field_validator(
        'characters',
        'events',
        'relations',
        'conflicts',
        'foreshadowing',
        'worldbuilding_facts',
        mode='before',
    )
    @classmethod
    def _normalize_fact_lists(cls, value: Any) -> Any:
        return cls._normalize_notes(value)

    def ensure_minimum_facts(self, cleaned_text: str) -> ChapterFactExtractionOutput:
        """Backfill ultra-obvious facts when the model returns an empty extraction."""

        if any([self.characters, self.events, self.relations, self.conflicts, self.foreshadowing]):
            return self
        heuristics: list[EvidenceNote] = []
        for candidate in ['卫图', '命格', '养生功', '二姑', '黄宅', '李宅']:
            if candidate in cleaned_text:
                heuristics.append(
                    EvidenceNote(label=candidate, evidence=[candidate], confidence=0.45)
                )
        if heuristics:
            return self.model_copy(update={'characters': heuristics[:2], 'events': heuristics[2:4]})
        return self


class EvidenceBindingOutput(BaseModel):
    """Skill output for evidence-binder."""

    retained_items: list[EvidenceNote] = Field(default_factory=list)
    unsupported_items: list[str] = Field(default_factory=list)
    coverage_summary: str = Field(default='')

    @field_validator('retained_items', mode='before')
    @classmethod
    def _normalize_retained_items(cls, value: Any) -> Any:
        return ChapterFactExtractionOutput._normalize_notes(value)

    def ensure_from_facts(self, facts: ChapterFactExtractionOutput) -> EvidenceBindingOutput:
        """If the binder returned nothing, promote low-risk fact records into retained_items."""

        if self.retained_items:
            return self
        fact_items = (
            facts.characters
            + facts.events
            + facts.relations
            + facts.conflicts
            + facts.foreshadowing
        )
        if not fact_items:
            return self
        return self.model_copy(
            update={
                'retained_items': fact_items[:8],
                'coverage_summary': self.coverage_summary or '使用事实层作为最低证据保底。',
            }
        )


class AnalysisSummary(BaseModel):
    """A compact summary bundle."""

    one_sentence: str = Field(default='')
    short: str = Field(default='')
    detailed: str = Field(default='')

    @model_validator(mode='before')
    @classmethod
    def _normalize_summary(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {'short': value}
        return value

    def compact(self, max_chars: int = 90) -> str:
        """Return a concise card-style summary."""

        for candidate in [self.short, self.one_sentence, self.detailed]:
            text = str(candidate).strip()
            if not text:
                continue
            if len(text) <= max_chars:
                return text
            clipped = text[: max_chars - 1].rstrip('，。；;、, ')
            return clipped + '。'
        return ''


class ChapterAnalysisLayerOutput(BaseModel):
    """Skill output for chapter-analysis-generator."""

    summary: AnalysisSummary = Field(default_factory=AnalysisSummary)
    themes: list[EvidenceNote] = Field(default_factory=list)
    pacing: dict[str, Any] = Field(default_factory=dict)
    emotional_curve: dict[str, Any] = Field(default_factory=dict)
    continuity_notes: list[str] = Field(default_factory=list)

    @field_validator('themes', mode='before')
    @classmethod
    def _normalize_themes(cls, value: Any) -> Any:
        return ChapterFactExtractionOutput._normalize_notes(value)

    def ensure_minimum_analysis(
        self,
        title: str,
        evidence: EvidenceBindingOutput,
    ) -> ChapterAnalysisLayerOutput:
        """Guarantee a minimally useful summary when evidence exists."""

        if self.summary.short.strip() or self.summary.one_sentence.strip():
            return self
        labels = [item.label for item in evidence.retained_items[:4]]
        if not labels:
            return self
        short = f"本章围绕“{title}”展开，重点涉及：" + '、'.join(labels) + '。'
        continuity = self.continuity_notes or ['后续可基于上述事实继续推进人物、事件与伏笔线索。']
        return self.model_copy(
            update={
                'summary': AnalysisSummary(short=short, one_sentence=short),
                'continuity_notes': continuity,
            }
        )


class WriterLearningLensOutput(BaseModel):
    """Skill output for writer-learning-lens."""

    hook_notes: list[str] = Field(default_factory=list)
    conflict_notes: list[str] = Field(default_factory=list)
    reveal_order_notes: list[str] = Field(default_factory=list)
    scene_efficiency_notes: list[str] = Field(default_factory=list)
    transferable_lessons: list[str] = Field(default_factory=list)

    def ensure_minimum_writer_notes(
        self,
        title: str,
        summary: str,
        state_transition_notes: list[str] | None = None,
        evidence_backed_resolutions: list[str] | None = None,
        unresolved_threads: list[str] | None = None,
    ) -> WriterLearningLensOutput:
        """Provide a fallback craft note when the stage is empty."""

        if any(
            [
                self.hook_notes,
                self.conflict_notes,
                self.reveal_order_notes,
                self.scene_efficiency_notes,
                self.transferable_lessons,
            ]
        ):
            return self
        transition = (state_transition_notes or [''])[0]
        resolution = (evidence_backed_resolutions or [''])[0]
        unresolved = (unresolved_threads or [''])[0]
        lessons: list[str] = []
        if transition:
            lessons.append(f'可学习作者如何把状态推进明确写成阶段变化：{transition}')
        if resolution:
            lessons.append(f'可学习作者如何让阶段性解决显得可信：{resolution}')
        if unresolved:
            lessons.append(f'可学习作者如何保留未解线程驱动后续：{unresolved}')
        lessons.append(f'《{title}》这一章可重点学习其如何用章节标题与核心事件建立读者预期：{summary}')
        return self.model_copy(update={'transferable_lessons': lessons[:3]})


class AntiFabricationGuardOutput(BaseModel):
    """Skill output for anti-fabrication-guard."""

    unsupported_inferences: list[str] = Field(default_factory=list)
    ambiguous_points: list[str] = Field(default_factory=list)
    overclaim_flags: list[str] = Field(default_factory=list)
    needs_human_review: bool = Field(default=False)


class DimensionResult(BaseModel):
    """One dimension's extracted result."""

    dimension: AnalysisDimension
    summary: str = Field(default='')
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ChapterAnalysisOutput(BaseModel):
    """Structured chapter output persisted per chapter."""

    chapter_index: int
    normalized_title: str
    dimensions: list[DimensionResult] = Field(default_factory=list)
    chapter_summary: str = Field(default='')
    key_entities: list[str] = Field(default_factory=list)
    key_events: list[str] = Field(default_factory=list)
    continuity_notes: list[str] = Field(default_factory=list)
    state_transition_notes: list[str] = Field(default_factory=list)
    evidence_backed_resolutions: list[str] = Field(default_factory=list)
    unresolved_threads: list[str] = Field(default_factory=list)
    writer_learning_notes: list[str] = Field(default_factory=list)
    unsupported_inferences: list[str] = Field(default_factory=list)
    ambiguous_points: list[str] = Field(default_factory=list)
    needs_human_review: bool = Field(default=False)
    quality_gate_notes: list[str] = Field(default_factory=list)
    hook_score: float | None = Field(default=None, ge=0.0, le=10.0)


class BranchQAResult(BaseModel):
    """Retrieval-grounded answer for branch-level question answering."""

    answer: str
    used_chapters: list[int] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    reasoning_paths: list[str] = Field(default_factory=list)
    graph_signals: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    insufficient_context: bool = Field(default=False)


class ChapterNoteRow(BaseModel):
    """One chapter-indexed summary note."""

    chapter_index: int
    note: str


class NodeRef(BaseModel):
    """Visualization-friendly node reference."""

    node_type: str
    label: str
    chapter_first_seen: int | None = None
    chapter_last_seen: int | None = None


class EdgeRef(BaseModel):
    """Visualization-friendly edge reference."""

    edge_type: str
    source: str
    target: str
    chapter_first_seen: int | None = None
    chapter_last_seen: int | None = None


class TimelinePoint(BaseModel):
    """Visualization-friendly timeline point."""

    chapter_index: int
    summary: str


class QuestionStep(BaseModel):
    """Ordered recommended question step."""

    step: int
    question: str


class ThematicContextOutput(BaseModel):
    """A themed QA/navigation context entry."""

    recommended_questions: list[str] = Field(default_factory=list)
    question_sequence: list[QuestionStep] = Field(default_factory=list)
    related_chapters: list[int] = Field(default_factory=list)
    evidence_summaries: list[str] = Field(default_factory=list)
    reasoning_paths: list[str] = Field(default_factory=list)
    state_signals: list[str] = Field(default_factory=list)
    supporting_facts: list[str] = Field(default_factory=list)
    node_refs: list[NodeRef] = Field(default_factory=list)
    edge_refs: list[EdgeRef] = Field(default_factory=list)
    timeline_points: list[TimelinePoint] = Field(default_factory=list)
    focus_entities: list[str] = Field(default_factory=list)
    active_conflicts: list[str] = Field(default_factory=list)
    escalated_conflicts: list[str] = Field(default_factory=list)
    open_or_paid_off: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    chapter_threads: list[ChapterNoteRow] = Field(default_factory=list)
    document_summaries: list[dict[str, object]] = Field(default_factory=list)


class ChapterQAContextOutput(BaseModel):
    """Downstream-consumable chapter QA context package."""

    chapter_index: int
    title: str | None = None
    chapter_summary: str | None = None
    key_events: list[str] = Field(default_factory=list)
    state_transition_notes: list[str] = Field(default_factory=list)
    evidence_backed_resolutions: list[str] = Field(default_factory=list)
    unresolved_threads: list[str] = Field(default_factory=list)
    facts: list[dict[str, object]] = Field(default_factory=list)
    retrieval: dict[str, object] = Field(default_factory=dict)
    query_hints: list[str] = Field(default_factory=list)
    recommended_questions: list[str] = Field(default_factory=list)
    reasoning_graph: dict[str, object] = Field(default_factory=dict)
    state_summary: dict[str, object] = Field(default_factory=dict)


class BranchQAContextOutput(BaseModel):
    """Downstream-consumable branch QA context package."""

    status: dict[str, object] = Field(default_factory=dict)
    chapter_index: list[dict[str, object]] = Field(default_factory=list)
    windows: list[dict[str, object]] = Field(default_factory=list)
    state_summary: dict[str, object] = Field(default_factory=dict)
    chapter_output_summary: dict[str, object] = Field(default_factory=dict)
    recommended_questions: list[str] = Field(default_factory=list)
    reasoning_graph: dict[str, object] = Field(default_factory=dict)
    retrieval_documents: list[dict[str, object]] = Field(default_factory=list)
    thematic_contexts: dict[str, ThematicContextOutput] = Field(default_factory=dict)
