"""Deterministic quality gate for chapter analysis outputs."""

from __future__ import annotations

from dataclasses import dataclass

from novel_analyzer.domain.schemas import ChapterAnalysisOutput


@dataclass(frozen=True, slots=True)
class QualityGateReport:
    """Quality gate outcome for one chapter artifact."""

    notes: list[str]
    needs_human_review: bool
    hook_score: float


class QualityGateService:
    """Apply lightweight deterministic quality checks before accepting output."""

    @staticmethod
    def evaluate(chapter_content: str, result: ChapterAnalysisOutput) -> QualityGateReport:
        notes: list[str] = []
        if not result.chapter_summary.strip():
            notes.append('chapter_summary 为空')
        if result.chapter_summary and result.chapter_summary in chapter_content:
            notes.append('summary 与原文高度重合，可能缺少抽象压缩')
        if len(set(result.key_events)) != len(result.key_events):
            notes.append('key_events 存在重复')
        if len(set(result.key_entities)) != len(result.key_entities):
            notes.append('key_entities 存在重复')
        if '作为AI' in result.chapter_summary or '作为模型' in result.chapter_summary:
            notes.append('检测到元叙述泄露')
        if (
            any('第2章' in note for note in result.continuity_notes)
            and '第2章' not in chapter_content
        ):
            notes.append('continuity_notes 引用了缺失证据的章节号')

        hook_score = 4.0
        trigger_words = ['明天', '接下来', '计划', '伏笔', '线索', '决定', '准备']
        for word in trigger_words:
            if word in chapter_content:
                hook_score += 0.5
        hook_score = min(hook_score, 10.0)
        if hook_score >= 7.0:
            notes.append(f'章尾驱动力较强（hook_score={hook_score:.1f}）')
        elif hook_score >= 4.5:
            notes.append(f'章尾存在基础驱动力（hook_score={hook_score:.1f}）')
        needs_human_review = bool(
            result.unsupported_inferences or (notes[:1] and '元叙述' in notes[0])
        )
        return QualityGateReport(
            notes=notes,
            needs_human_review=needs_human_review,
            hook_score=hook_score,
        )
