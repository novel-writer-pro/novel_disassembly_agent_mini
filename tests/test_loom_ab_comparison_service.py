from __future__ import annotations

from novel_analyzer.services.loom_ab_comparison_service import (
    LoomCarryOverComparison,
    LoomCarryOverMetrics,
    compare_carry_over_modes,
)


def _payload(
    *,
    overall_score: int = 80,
    blocking: int = 0,
    risk: str = "low",
    verdict: str = "pass",
    families: list[str] | None = None,
) -> dict:
    return {
        "final_verdict": verdict,
        "policy_summary": {
            "overall_score": overall_score,
            "blocking_issue_count": blocking,
            "risk_overall_level": risk,
            "issue_families": families or [],
        },
    }


def test_empty_payloads_returns_zeroed_metrics() -> None:
    result = compare_carry_over_modes([], [])
    assert isinstance(result, LoomCarryOverComparison)
    assert result.side_a.chapter_count == 0
    assert result.side_b.chapter_count == 0
    assert all(v == 0 for v in result.delta.values())


def test_perfect_match_zero_delta() -> None:
    pa = [_payload() for _ in range(10)]
    pb = [_payload() for _ in range(10)]
    result = compare_carry_over_modes(pa, pb)
    assert all(abs(v) < 0.01 for v in result.delta.values())
    assert "No statistically meaningful delta" in result.interpretation[0]


def test_enabled_reduces_ooc_caught() -> None:
    pa = [_payload(families=["character"]) for _ in range(8)] + [
        _payload() for _ in range(2)
    ]
    pb = [_payload(families=["character"]) for _ in range(2)] + [
        _payload() for _ in range(8)
    ]
    result = compare_carry_over_modes(pa, pb)
    assert result.side_a.character_ooc_trigger_rate == 0.8
    assert result.side_b.character_ooc_trigger_rate == 0.2
    assert result.delta["character_ooc_trigger_rate"] == -0.6
    assert any("reduces character_ooc" in note for note in result.interpretation)


def test_enabled_lowers_score_warning() -> None:
    pa = [_payload(overall_score=85) for _ in range(10)]
    pb = [_payload(overall_score=70) for _ in range(10)]
    result = compare_carry_over_modes(pa, pb)
    assert result.delta["avg_overall_score"] == -15.0
    assert any("WARNING" in note and "LOWERS" in note for note in result.interpretation)


def test_enabled_improves_pass_rate() -> None:
    pa = [_payload(verdict="pass") for _ in range(5)] + [
        _payload(verdict="needs_revision") for _ in range(5)
    ]
    pb = [_payload(verdict="pass") for _ in range(9)] + [
        _payload(verdict="needs_revision") for _ in range(1)
    ]
    result = compare_carry_over_modes(pa, pb)
    assert result.side_a.pass_verdict_rate == 0.5
    assert result.side_b.pass_verdict_rate == 0.9
    assert any("improves pass_verdict_rate" in note for note in result.interpretation)


def test_high_risk_chapter_rate() -> None:
    pa = [_payload(risk="high") for _ in range(3)] + [_payload() for _ in range(7)]
    pb = [_payload() for _ in range(10)]
    result = compare_carry_over_modes(pa, pb)
    assert result.side_a.high_risk_chapter_rate == 0.3
    assert result.side_b.high_risk_chapter_rate == 0.0


def test_blocking_issue_average() -> None:
    pa = [_payload(blocking=2) for _ in range(10)]
    pb = [_payload(blocking=0) for _ in range(10)]
    result = compare_carry_over_modes(pa, pb)
    assert result.side_a.avg_blocking_issues == 2.0
    assert result.side_b.avg_blocking_issues == 0.0
    assert result.delta["avg_blocking_issues"] == -2.0


def test_handles_malformed_policy_summary() -> None:
    pa = [{"final_verdict": "pass"}, {"final_verdict": "pass", "policy_summary": "not a dict"}]
    pb = [_payload() for _ in range(2)]
    result = compare_carry_over_modes(pa, pb)
    assert result.side_a.chapter_count == 2
    assert result.side_a.pass_verdict_rate == 1.0
    assert result.side_a.avg_overall_score == 0.0


def test_custom_labels_propagate() -> None:
    pa = [_payload()]
    pb = [_payload()]
    result = compare_carry_over_modes(pa, pb, side_a_label="legacy", side_b_label="phase1")
    assert result.side_a.label == "legacy"
    assert result.side_b.label == "phase1"


def test_comparison_immutable() -> None:
    result = compare_carry_over_modes([_payload()], [_payload()])
    try:
        result.delta = {}  # type: ignore[misc]
    except Exception as exc:
        assert "frozen" in str(exc).lower() or "cannot" in str(exc).lower()
        return
    raise AssertionError("LoomCarryOverComparison should be frozen")
