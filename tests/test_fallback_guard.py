from __future__ import annotations

from novel_analyzer.services._fallback_guard import is_heuristic_artifact


def test_returns_false_for_none() -> None:
    assert is_heuristic_artifact(None) is False


def test_returns_false_for_empty_dict() -> None:
    assert is_heuristic_artifact({}) is False


def test_returns_true_with_explicit_tag() -> None:
    assert is_heuristic_artifact({"extraction_source": "heuristic"}) is True


def test_returns_false_with_explicit_llm_tag_even_with_marker() -> None:
    payload = {
        "extraction_source": "llm",
        "continuity_notes": ["本地启发式分析保底生成 -- legacy text"],
    }
    assert is_heuristic_artifact(payload) is False


def test_returns_true_with_legacy_marker_only() -> None:
    payload = {"continuity_notes": ["本地启发式分析保底生成 -- ch12 fallback"]}
    assert is_heuristic_artifact(payload) is True


def test_returns_false_with_unrelated_notes() -> None:
    payload = {"continuity_notes": ["普通的连续性说明"]}
    assert is_heuristic_artifact(payload) is False


def test_returns_false_with_marker_not_in_first() -> None:
    payload = {
        "continuity_notes": [
            "普通的连续性说明",
            "本地启发式分析保底生成 -- second slot, must be ignored",
        ]
    }
    assert is_heuristic_artifact(payload) is False
