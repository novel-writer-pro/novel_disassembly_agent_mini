"""Fallback artifact detection used by retrieval/risk/QA consumers.

Phase 1 of fallback isolation tags new chapter_artifacts at write time
(see run_service.record_chapter_artifact). Phase 2 (this file) provides
the read-side utility consumers call to skip heuristic-fallback rows.

For legacy rows written before Phase 1, falls back to detecting the
continuity_notes marker. The Phase-2 backfill SQL retroactively tags
them so this fallback check stops being needed over time.
"""

from __future__ import annotations

from typing import Any

_HEURISTIC_NOTE_MARKER = "本地启发式分析保底生成"


def is_heuristic_artifact(payload: dict[str, Any] | None) -> bool:
    """True if the chapter_artifact was written by the heuristic fallback path."""
    if not isinstance(payload, dict):
        return False
    tag = payload.get("extraction_source")
    if tag == "heuristic":
        return True
    if tag == "llm":
        return False
    notes = payload.get("continuity_notes") or []
    if not isinstance(notes, list) or not notes:
        return False
    first = notes[0]
    return isinstance(first, str) and _HEURISTIC_NOTE_MARKER in first
