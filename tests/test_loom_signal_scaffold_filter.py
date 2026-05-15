from __future__ import annotations

from novel_analyzer.cli.app import _extract_writer_output_loom_signal


def _payload_with_loom(*, scaffold: bool) -> dict[str, object]:
    return {
        "branch_id": "test-branch",
        "source_chapter_index": 49,
        "final_draft": {
            "is_scaffold_only": scaffold,
            "draft_text": "x" * 500,
            "draft_title": "看相",
        },
        "rounds": [
            {
                "skill_outputs": {
                    "_loom_tension": {"tension_score": 7.5, "alerts": []},
                },
            }
        ],
        "chapter_quality_signal": {"quality_score": 0.82, "confidence": 0.7},
    }


def test_loom_signal_skips_scaffold_only_drafts() -> None:
    payload = _payload_with_loom(scaffold=True)
    result = _extract_writer_output_loom_signal(payload, artifact_name="writer-imitate-ch49.json")
    assert result is None, (
        "scaffold-only drafts must not contribute to loom signal aggregation; "
        "their quality scores reflect outline scaffolding, not actual prose"
    )


def test_loom_signal_includes_normal_drafts() -> None:
    payload = _payload_with_loom(scaffold=False)
    result = _extract_writer_output_loom_signal(payload, artifact_name="writer-imitate-ch49.json")
    assert result is not None
    assert result["chapter_index"] == 49
    assert result["has_tension_signal"] is True
    assert result["has_quality_signal"] is True


def test_loom_signal_handles_missing_final_draft() -> None:
    payload = {
        "branch_id": "test-branch",
        "source_chapter_index": 1,
        "rounds": [{"skill_outputs": {"_loom_tension": {"tension_score": 5.0, "alerts": []}}}],
    }
    result = _extract_writer_output_loom_signal(payload, artifact_name="writer-imitate-ch1.json")
    assert result is not None
