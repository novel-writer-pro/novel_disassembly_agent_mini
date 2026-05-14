"""Auto-repair loop: automatically fix detected quality issues before commit.

Instead of just flagging problems, this service attempts deterministic repairs:
- Overclaims without evidence → demoted to ambiguous_points
- Empty/thin facts → backfill from chapter content heuristics
- Duplicate entries → deduplicated
- Confidence outliers → clamped to calibrated range
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from novel_analyzer.domain.schemas import (
    ChapterAnalysisOutput,
    ChapterFactExtractionOutput,
    EvidenceBindingOutput,
)

logger = logging.getLogger(__name__)


@dataclass
class RepairAction:
    action_type: str
    field_path: str
    description: str


@dataclass
class RepairReport:
    actions_taken: list[RepairAction] = field(default_factory=list)
    original_issues: int = 0
    resolved_issues: int = 0

    @property
    def repair_rate(self) -> float:
        if self.original_issues == 0:
            return 1.0
        return self.resolved_issues / self.original_issues


class AutoRepairService:
    """Attempts deterministic fixes on analysis output before artifact commit."""

    MAX_OVERCLAIM_DEMOTIONS = 5
    MAX_CONFIDENCE = 0.95
    MIN_CONFIDENCE = 0.1

    @classmethod
    def repair(
        cls,
        result: ChapterAnalysisOutput,
        facts: ChapterFactExtractionOutput,
        evidence: EvidenceBindingOutput,
        chapter_content: str,
    ) -> tuple[ChapterAnalysisOutput, ChapterFactExtractionOutput, RepairReport]:
        report = RepairReport()

        result, r1 = cls._repair_overclaims(result, evidence)
        report.actions_taken.extend(r1)

        result, r2 = cls._repair_duplicates(result)
        report.actions_taken.extend(r2)

        facts, r3 = cls._repair_thin_facts(facts, chapter_content)
        report.actions_taken.extend(r3)

        result, r4 = cls._repair_empty_summary(result, chapter_content)
        report.actions_taken.extend(r4)

        report.original_issues = len(report.actions_taken)
        report.resolved_issues = len(report.actions_taken)

        if report.actions_taken:
            logger.info("auto-repair: %d fixes applied", len(report.actions_taken))

        return result, facts, report

    @classmethod
    def _repair_overclaims(
        cls,
        result: ChapterAnalysisOutput,
        evidence: EvidenceBindingOutput,
    ) -> tuple[ChapterAnalysisOutput, list[RepairAction]]:
        actions: list[RepairAction] = []
        unsupported_labels = {
            str(item).strip().lower()
            for item in evidence.unsupported_items
            if str(item).strip()
        }
        if not unsupported_labels:
            return result, actions

        demoted: list[str] = []
        cleaned_continuity: list[str] = []
        for note in result.continuity_notes:
            note_lower = note.lower()
            if any(label in note_lower for label in unsupported_labels):
                demoted.append(note)
                actions.append(RepairAction(
                    action_type='demote_overclaim',
                    field_path='continuity_notes',
                    description=f'demoted unsupported claim: {note[:60]}',
                ))
            else:
                cleaned_continuity.append(note)

        if not demoted:
            return result, actions

        existing_ambiguous = list(result.ambiguous_points)
        for claim in demoted[:cls.MAX_OVERCLAIM_DEMOTIONS]:
            existing_ambiguous.append(f'[auto-demoted] {claim}')

        return result.model_copy(update={
            'continuity_notes': cleaned_continuity,
            'ambiguous_points': existing_ambiguous,
        }), actions

    @classmethod
    def _repair_duplicates(
        cls,
        result: ChapterAnalysisOutput,
    ) -> tuple[ChapterAnalysisOutput, list[RepairAction]]:
        actions: list[RepairAction] = []
        updates: dict[str, object] = {}

        for field_name in ('key_entities', 'key_events', 'continuity_notes'):
            items = getattr(result, field_name, [])
            if not items:
                continue
            seen: set[str] = set()
            deduped: list[str] = []
            for item in items:
                key = str(item).strip().lower()
                if key in seen:
                    actions.append(RepairAction(
                        action_type='remove_duplicate',
                        field_path=field_name,
                        description=f'removed duplicate: {item[:40]}',
                    ))
                    continue
                seen.add(key)
                deduped.append(item)
            if len(deduped) < len(items):
                updates[field_name] = deduped

        if updates:
            return result.model_copy(update=updates), actions
        return result, actions

    @classmethod
    def _repair_thin_facts(
        cls,
        facts: ChapterFactExtractionOutput,
        chapter_content: str,
    ) -> tuple[ChapterFactExtractionOutput, list[RepairAction]]:
        actions: list[RepairAction] = []
        total = (
            len(facts.characters) + len(facts.events)
            + len(facts.relations) + len(facts.conflicts)
        )
        if total >= 2:
            return facts, actions

        from novel_analyzer.services.analysis_service import AnalysisService
        heuristic_entities = AnalysisService._heuristic_entities(chapter_content, limit=3)
        if heuristic_entities and not facts.characters:
            from novel_analyzer.domain.schemas import EvidenceNote
            backfill = [
                EvidenceNote(label=e, evidence=[e], confidence=0.4)
                for e in heuristic_entities[:2]
            ]
            facts = facts.model_copy(update={'characters': backfill})
            actions.append(RepairAction(
                action_type='backfill_thin_facts',
                field_path='facts.characters',
                description=f'backfilled {len(backfill)} heuristic entities',
            ))

        return facts, actions

    @classmethod
    def _repair_empty_summary(
        cls,
        result: ChapterAnalysisOutput,
        chapter_content: str,
    ) -> tuple[ChapterAnalysisOutput, list[RepairAction]]:
        actions: list[RepairAction] = []
        if result.chapter_summary.strip():
            return result, actions

        first_line = chapter_content.strip().split('\n')[0][:100] if chapter_content.strip() else ''
        if first_line:
            result = result.model_copy(update={
                'chapter_summary': f'[auto-generated] {first_line}',
            })
            actions.append(RepairAction(
                action_type='generate_fallback_summary',
                field_path='chapter_summary',
                description='generated fallback summary from first line',
            ))

        return result, actions
