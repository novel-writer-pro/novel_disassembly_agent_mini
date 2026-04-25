"""Deterministic Markdown rendering from chapter-analysis JSON."""

from __future__ import annotations

from typing import Any


def render_chapter_markdown(payload: dict[str, Any]) -> str:
    """Render one chapter JSON payload into markdown."""

    lines = [
        f"# 第{payload.get('chapter_index', '?')}章 {payload.get('normalized_title', '')}",
        "",
        "## Summary",
        payload.get("chapter_summary", ""),
        "",
        "## Key Events",
    ]
    for item in payload.get("key_events", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Continuity Notes"])
    for item in payload.get("continuity_notes", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Writer Learning Notes"])
    for item in payload.get("writer_learning_notes", []):
        lines.append(f"- {item}")
    if payload.get("hook_score") is not None:
        lines.append("")
        lines.append(f"Hook Score: {payload.get('hook_score')}")
    for item in payload.get("quality_gate_notes", []):
        lines.append(f"- 质量门控: {item}")
    lines.extend(["", "## Dimensions"])
    for dimension in payload.get("dimensions", []):
        if isinstance(dimension, str):
            name = dimension
            summary = ""
            evidence = []
        else:
            name = dimension.get("dimension", "unknown")
            summary = dimension.get("summary", "")
            evidence = dimension.get("evidence", [])
        lines.append(f"### {name}")
        lines.append(summary)
        if evidence:
            lines.append("")
            lines.append("Evidence:")
            for item in evidence:
                lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
