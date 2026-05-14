"""Self-evaluation loop: output self-critique before artifact commit.

After analysis stages complete but before persisting the artifact, runs a
lightweight deterministic self-check that flags potential issues:
- Claims without sufficient evidence backing
- Contradictions with prior chapter context
- Suspiciously high confidence on thin evidence
- Missing expected continuity from prior state
"""

from __future__ import annotations

from dataclasses import dataclass, field

from novel_analyzer.domain.schemas import (
    ChapterAnalysisOutput,
    ChapterFactExtractionOutput,
    EvidenceBindingOutput,
)


@dataclass(frozen=True, slots=True)
class SelfEvalIssue:
    category: str
    severity: str
    description: str
    field_path: str


@dataclass
class SelfEvalResult:
    issues: list[SelfEvalIssue] = field(default_factory=list)
    passed: bool = True
    score: float = 1.0

    def add(self, category: str, severity: str, description: str, field_path: str) -> None:
        self.issues.append(SelfEvalIssue(
            category=category,
            severity=severity,
            description=description,
            field_path=field_path,
        ))
        if severity == 'error':
            self.passed = False
            self.score -= 0.2
        elif severity == 'warning':
            self.score -= 0.1
        self.score = max(0.0, self.score)


class SelfEvaluationService:
    """Deterministic self-critique of analysis output before commit."""

    THIN_EVIDENCE_THRESHOLD = 0.8
    MIN_FACTS_FOR_CHAPTER = 2
    MIN_SUMMARY_LENGTH = 10

    def evaluate(
        self,
        result: ChapterAnalysisOutput,
        facts: ChapterFactExtractionOutput,
        evidence: EvidenceBindingOutput,
        prior_context: dict[str, object],
    ) -> SelfEvalResult:
        """Run all self-evaluation checks and return aggregated result."""
        eval_result = SelfEvalResult()

        self._check_summary_quality(result, eval_result)
        self._check_evidence_coverage(facts, evidence, eval_result)
        self._check_confidence_calibration(facts, eval_result)
        self._check_continuity_coherence(result, prior_context, eval_result)
        self._check_entity_consistency(result, facts, eval_result)

        return eval_result

    def _check_summary_quality(
        self,
        result: ChapterAnalysisOutput,
        eval_result: SelfEvalResult,
    ) -> None:
        if len(result.chapter_summary.strip()) < self.MIN_SUMMARY_LENGTH:
            eval_result.add(
                'summary', 'error',
                'chapter_summary 过短或为空',
                'chapter_summary',
            )
        if not result.key_entities and not result.key_events:
            eval_result.add(
                'completeness', 'warning',
                '缺少 key_entities 和 key_events',
                'key_entities',
            )

    def _check_evidence_coverage(
        self,
        facts: ChapterFactExtractionOutput,
        evidence: EvidenceBindingOutput,
        eval_result: SelfEvalResult,
    ) -> None:
        total_facts = (
            len(facts.characters) + len(facts.events)
            + len(facts.relations) + len(facts.conflicts)
            + len(facts.foreshadowing)
        )
        if total_facts < self.MIN_FACTS_FOR_CHAPTER:
            eval_result.add(
                'coverage', 'warning',
                f'事实提取数量过少 ({total_facts})',
                'facts',
            )
        unsupported_count = len(evidence.unsupported_items)
        if total_facts > 0 and unsupported_count / max(total_facts, 1) > 0.5:
            eval_result.add(
                'evidence', 'warning',
                f'超过50%的事实缺少证据支撑 ({unsupported_count}/{total_facts})',
                'evidence.unsupported_items',
            )

    def _check_confidence_calibration(
        self,
        facts: ChapterFactExtractionOutput,
        eval_result: SelfEvalResult,
    ) -> None:
        high_confidence_thin_evidence = 0
        all_notes = (
            facts.characters + facts.events + facts.relations
            + facts.conflicts + facts.foreshadowing
        )
        for note in all_notes:
            if note.confidence >= self.THIN_EVIDENCE_THRESHOLD and len(note.evidence) < 2:
                high_confidence_thin_evidence += 1

        if high_confidence_thin_evidence > 3:
            eval_result.add(
                'calibration', 'warning',
                f'{high_confidence_thin_evidence} 条事实置信度>=0.8但证据不足2条',
                'facts.*.confidence',
            )

    def _check_continuity_coherence(
        self,
        result: ChapterAnalysisOutput,
        prior_context: dict[str, object],
        eval_result: SelfEvalResult,
    ) -> None:
        open_threads = prior_context.get('open_foreshadowing_threads', [])
        if not isinstance(open_threads, list):
            return
        if len(open_threads) > 5 and not result.continuity_notes:
            eval_result.add(
                'continuity', 'warning',
                f'前情有{len(open_threads)}条未回收伏笔但本章无 continuity_notes',
                'continuity_notes',
            )

    def _check_entity_consistency(
        self,
        result: ChapterAnalysisOutput,
        facts: ChapterFactExtractionOutput,
        eval_result: SelfEvalResult,
    ) -> None:
        fact_entities = {note.label for note in facts.characters}
        result_entities = set(result.key_entities)
        if fact_entities and not result_entities:
            eval_result.add(
                'consistency', 'warning',
                '事实层有角色但 key_entities 为空',
                'key_entities',
            )
        if result_entities and not fact_entities:
            eval_result.add(
                'consistency', 'warning',
                'key_entities 有值但事实层角色为空',
                'facts.characters',
            )
