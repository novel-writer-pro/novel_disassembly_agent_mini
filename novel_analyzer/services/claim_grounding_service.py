"""Claim-level grounding: anchor every analytical claim to source text.

Validates that continuity_notes, state_transition_notes, and other analytical
claims can be traced back to specific text spans in the chapter content.
Claims without grounding are automatically demoted to low confidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from novel_analyzer.domain.schemas import ChapterAnalysisOutput


@dataclass(frozen=True, slots=True)
class GroundingResult:
    claim: str
    grounded: bool
    matched_span: str
    confidence_adjustment: float


@dataclass(frozen=True, slots=True)
class ClaimGroundingReport:
    total_claims: int
    grounded_claims: int
    ungrounded_claims: int
    grounding_ratio: float
    demoted_claims: list[str]
    results: list[GroundingResult]


class ClaimGroundingService:
    """Validates analytical claims against source chapter text."""

    MIN_MATCH_LENGTH = 2
    GROUNDING_CONFIDENCE_BOOST = 0.1
    UNGROUNDED_CONFIDENCE_PENALTY = 0.3

    @classmethod
    def ground_claims(
        cls,
        chapter_content: str,
        result: ChapterAnalysisOutput,
    ) -> ClaimGroundingReport:
        """Check all analytical claims for source text grounding."""
        claims_to_check: list[tuple[str, str]] = []

        for note in result.continuity_notes:
            claims_to_check.append(('continuity_note', note))
        for note in result.state_transition_notes:
            claims_to_check.append(('state_transition', note))
        for note in result.evidence_backed_resolutions:
            claims_to_check.append(('resolution', note))
        for note in result.unresolved_threads:
            claims_to_check.append(('unresolved_thread', note))

        content_lower = chapter_content.lower()
        results: list[GroundingResult] = []
        demoted: list[str] = []

        for claim_type, claim in claims_to_check:
            grounded, span = cls._find_grounding(claim, content_lower, chapter_content)
            adjustment = (
                cls.GROUNDING_CONFIDENCE_BOOST if grounded
                else -cls.UNGROUNDED_CONFIDENCE_PENALTY
            )
            results.append(GroundingResult(
                claim=claim,
                grounded=grounded,
                matched_span=span,
                confidence_adjustment=adjustment,
            ))
            if not grounded:
                demoted.append(f'[{claim_type}] {claim}')

        grounded_count = sum(1 for r in results if r.grounded)
        total = len(results)
        return ClaimGroundingReport(
            total_claims=total,
            grounded_claims=grounded_count,
            ungrounded_claims=total - grounded_count,
            grounding_ratio=grounded_count / total if total > 0 else 1.0,
            demoted_claims=demoted,
            results=results,
        )

    @classmethod
    def apply_grounding_to_result(
        cls,
        chapter_content: str,
        result: ChapterAnalysisOutput,
    ) -> ChapterAnalysisOutput:
        """Apply grounding check and demote ungrounded claims to ambiguous_points."""
        report = cls.ground_claims(chapter_content, result)

        if not report.demoted_claims:
            return result

        existing_ambiguous = list(result.ambiguous_points)
        existing_quality_notes = list(result.quality_gate_notes or [])

        for claim in report.demoted_claims[:5]:
            existing_ambiguous.append(f'[ungrounded] {claim}')

        if report.grounding_ratio < 0.5:
            existing_quality_notes.append(
                f'[grounding] 仅 {report.grounding_ratio:.0%} 的分析声称有原文支撑'
            )

        return result.model_copy(update={
            'ambiguous_points': existing_ambiguous,
            'quality_gate_notes': existing_quality_notes,
            'needs_human_review': result.needs_human_review or report.grounding_ratio < 0.3,
        })

    @classmethod
    def _find_grounding(
        cls,
        claim: str,
        content_lower: str,
        content_original: str,
    ) -> tuple[bool, str]:
        """Find source text evidence for a claim using multi-strategy matching."""
        claim_stripped = claim.strip()
        if not claim_stripped:
            return True, ''

        keywords = cls._extract_claim_keywords(claim_stripped)
        if not keywords:
            return True, ''

        for keyword in keywords:
            if len(keyword) < cls.MIN_MATCH_LENGTH:
                continue
            pos = content_lower.find(keyword.lower())
            if pos >= 0:
                start = max(0, pos - 10)
                end = min(len(content_original), pos + len(keyword) + 10)
                return True, content_original[start:end]

        bigrams = cls._claim_bigrams(claim_stripped)
        matched_bigrams = sum(1 for bg in bigrams if bg in content_lower)
        if bigrams and matched_bigrams / len(bigrams) >= 0.4:
            return True, f'[bigram match: {matched_bigrams}/{len(bigrams)}]'

        return False, ''

    @staticmethod
    def _extract_claim_keywords(claim: str) -> list[str]:
        """Extract meaningful keywords from a claim for grounding search."""
        stop_words = {
            '的', '了', '是', '在', '和', '与', '或', '但', '而', '也',
            '都', '就', '会', '能', '可以', '这', '那', '有', '没有',
            '不', '很', '更', '最', '已', '将', '被', '把', '让', '给',
            '从', '到', '对', '为', '以', '及', '等', '中', '上', '下',
            '本章', '下一章', '前情', '后续', '可能', '暗示', '表明',
        }
        tokens: list[str] = []
        current = ''
        for char in claim:
            if '\u4e00' <= char <= '\u9fff':
                current += char
            else:
                if len(current) >= 2:
                    tokens.append(current)
                current = ''
        if len(current) >= 2:
            tokens.append(current)

        return [t for t in tokens if t not in stop_words and len(t) >= 2][:8]

    @staticmethod
    def _claim_bigrams(claim: str) -> list[str]:
        chars = [c for c in claim if '\u4e00' <= c <= '\u9fff']
        if len(chars) < 2:
            return []
        return [chars[i] + chars[i+1] for i in range(len(chars) - 1)]
