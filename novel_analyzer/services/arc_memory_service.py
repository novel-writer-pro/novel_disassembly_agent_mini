"""Arc-level memory: multi-resolution summary with progressive compression.

Maintains three tiers of memory:
- Recent (last 5 chapters): full chapter summaries
- Mid-range (6-20 chapters back): compressed arc summaries
- Distant (21+ chapters back): highly compressed key-facts-only

This ensures chapter 100+ still has access to chapter 1-5 critical information
without blowing context budgets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact, WindowArtifact
from novel_analyzer.services.run_service import default_readable_artifact_clause


RECENT_WINDOW = 5
MIDRANGE_WINDOW = 20
ARC_COMPRESSION_RATIO = 3


@dataclass(frozen=True, slots=True)
class MemoryTier:
    tier: str
    chapter_range: tuple[int, int]
    content: str
    fact_count: int


class ArcMemoryService:
    """Builds multi-resolution memory context for long-range chapter analysis."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def build_tiered_context(
        self,
        branch_id: str,
        chapter_index: int,
        max_recent_chars: int = 1200,
        max_midrange_chars: int = 600,
        max_distant_chars: int = 300,
    ) -> dict[str, object]:
        """Build a tiered memory context for the given chapter position."""
        if chapter_index <= 1:
            return {'tiers': [], 'total_chapters_covered': 0}

        tiers: list[dict[str, object]] = []

        recent = self._build_recent_tier(
            branch_id, chapter_index, max_recent_chars,
        )
        if recent:
            tiers.append(recent)

        midrange = self._build_midrange_tier(
            branch_id, chapter_index, max_midrange_chars,
        )
        if midrange:
            tiers.append(midrange)

        distant = self._build_distant_tier(
            branch_id, chapter_index, max_distant_chars,
        )
        if distant:
            tiers.append(distant)

        total_covered = sum(
            t.get('chapter_count', 0) for t in tiers
        )
        return {
            'tiers': tiers,
            'total_chapters_covered': total_covered,
            'current_chapter': chapter_index,
        }

    def _build_recent_tier(
        self,
        branch_id: str,
        chapter_index: int,
        max_chars: int,
    ) -> dict[str, object] | None:
        start = max(1, chapter_index - RECENT_WINDOW)
        end = chapter_index - 1
        if start > end:
            return None

        summaries = self._get_chapter_summaries(branch_id, start, end)
        if not summaries:
            return None

        combined = '\n'.join(
            f'[Ch{ch}] {s}' for ch, s in summaries
        )
        if len(combined) > max_chars:
            combined = combined[:max_chars - 1] + '…'

        return {
            'tier': 'recent',
            'chapter_range': [start, end],
            'chapter_count': end - start + 1,
            'content': combined,
        }

    def _build_midrange_tier(
        self,
        branch_id: str,
        chapter_index: int,
        max_chars: int,
    ) -> dict[str, object] | None:
        end = max(0, chapter_index - RECENT_WINDOW - 1)
        start = max(1, chapter_index - MIDRANGE_WINDOW)
        if start > end:
            return None

        summaries = self._get_chapter_summaries(branch_id, start, end)
        if not summaries:
            return None

        compressed = self._compress_summaries(summaries, max_chars)
        return {
            'tier': 'midrange',
            'chapter_range': [start, end],
            'chapter_count': end - start + 1,
            'content': compressed,
        }

    def _build_distant_tier(
        self,
        branch_id: str,
        chapter_index: int,
        max_chars: int,
    ) -> dict[str, object] | None:
        end = max(0, chapter_index - MIDRANGE_WINDOW - 1)
        if end < 1:
            return None

        window_summaries = self.session.scalars(
            select(WindowArtifact)
            .where(WindowArtifact.branch_id == branch_id)
            .where(WindowArtifact.window_end_chapter <= end)
            .order_by(WindowArtifact.window_end_chapter.desc())
            .limit(5)
        ).all()

        if window_summaries:
            parts = []
            for w in reversed(window_summaries):
                text = str(w.payload_json.get('window_summary', '')).strip()
                if text:
                    parts.append(f'[W{w.window_end_chapter}] {text}')
            combined = '\n'.join(parts)
        else:
            summaries = self._get_chapter_summaries(branch_id, 1, end)
            if not summaries:
                return None
            combined = self._compress_summaries(summaries, max_chars)

        if len(combined) > max_chars:
            combined = combined[:max_chars - 1] + '…'

        if not combined.strip():
            return None

        return {
            'tier': 'distant',
            'chapter_range': [1, end],
            'chapter_count': end,
            'content': combined,
        }

    def _get_chapter_summaries(
        self,
        branch_id: str,
        start: int,
        end: int,
    ) -> list[tuple[int, str]]:
        artifacts = self.session.scalars(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index >= start)
            .where(ChapterArtifact.chapter_index <= end)
            .where(default_readable_artifact_clause())
            .order_by(ChapterArtifact.chapter_index)
        ).all()

        results: list[tuple[int, str]] = []
        for artifact in artifacts:
            summary = str(artifact.payload_json.get('chapter_summary', '')).strip()
            if summary:
                results.append((artifact.chapter_index, summary))
        return results

    @staticmethod
    def _compress_summaries(
        summaries: list[tuple[int, str]],
        max_chars: int,
    ) -> str:
        """Progressively compress summaries to fit within budget.

        Strategy: group by ARC_COMPRESSION_RATIO chapters, take first sentence of each.
        """
        if not summaries:
            return ''

        groups: list[list[tuple[int, str]]] = []
        current_group: list[tuple[int, str]] = []
        for item in summaries:
            current_group.append(item)
            if len(current_group) >= ARC_COMPRESSION_RATIO:
                groups.append(current_group)
                current_group = []
        if current_group:
            groups.append(current_group)

        compressed_parts: list[str] = []
        for group in groups:
            ch_start = group[0][0]
            ch_end = group[-1][0]
            key_points = []
            for _, summary in group:
                first_sentence = summary.split('。')[0].split('，')[0]
                if first_sentence.strip():
                    key_points.append(first_sentence.strip())
            if key_points:
                label = f'[Ch{ch_start}-{ch_end}]' if ch_start != ch_end else f'[Ch{ch_start}]'
                compressed_parts.append(f'{label} {"; ".join(key_points[:2])}')

        result = '\n'.join(compressed_parts)
        if len(result) > max_chars:
            result = result[:max_chars - 1] + '…'
        return result
