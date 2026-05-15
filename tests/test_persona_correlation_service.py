from __future__ import annotations

from novel_analyzer.services.persona_correlation_service import (
    CorrelationPanel,
    PersonaCorrelationReport,
    correlate_personas_with_feedback,
)


def test_empty_feedback_returns_insufficient() -> None:
    result = correlate_personas_with_feedback({}, [])
    assert isinstance(result, PersonaCorrelationReport)
    assert result.n_pairs_total == 0
    assert result.insufficient_data is True


def test_below_min_pairs_flag_set() -> None:
    panels = {"casual": [0.5, 0.6, 0.7]}
    feedback = [3.0, 4.0, 5.0]
    result = correlate_personas_with_feedback(panels, feedback, min_pairs=30)
    assert result.insufficient_data is True
    assert result.n_pairs_total == 3


def test_perfect_positive_correlation() -> None:
    panels = {"casual": [1.0, 2.0, 3.0, 4.0, 5.0]}
    feedback = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = correlate_personas_with_feedback(panels, feedback, min_pairs=3)
    assert result.panels[0].pearson == 1.0
    assert result.panels[0].spearman == 1.0


def test_perfect_negative_correlation() -> None:
    panels = {"casual": [5.0, 4.0, 3.0, 2.0, 1.0]}
    feedback = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = correlate_personas_with_feedback(panels, feedback, min_pairs=3)
    assert result.panels[0].pearson == -1.0
    assert result.panels[0].spearman == -1.0


def test_no_correlation_returns_near_zero() -> None:
    panels = {"casual": [3.0, 3.0, 3.0, 3.0, 3.0]}
    feedback = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = correlate_personas_with_feedback(panels, feedback, min_pairs=3)
    assert result.panels[0].pearson == 0.0


def test_overall_aggregates_across_panels() -> None:
    panels = {
        "casual": [1.0, 2.0, 3.0],
        "veteran": [3.0, 2.0, 1.0],
    }
    feedback = [1.0, 2.0, 3.0]
    result = correlate_personas_with_feedback(panels, feedback, min_pairs=3)
    assert result.overall_pearson == 0.0
    assert len(result.panels) == 2


def test_panel_with_wrong_length_zeroed() -> None:
    panels = {
        "casual": [1.0, 2.0],
        "veteran": [1.0, 2.0, 3.0],
    }
    feedback = [1.0, 2.0, 3.0]
    result = correlate_personas_with_feedback(panels, feedback, min_pairs=3)
    casual_panel = next(p for p in result.panels if p.panel_type == "casual")
    veteran_panel = next(p for p in result.panels if p.panel_type == "veteran")
    assert casual_panel.n_pairs == 0
    assert casual_panel.pearson == 0.0
    assert veteran_panel.n_pairs == 3
    assert veteran_panel.pearson == 1.0


def test_realistic_4_panel_above_min_pairs() -> None:
    n = 30
    feedback = [3.0 + (i % 5) * 0.5 for i in range(n)]
    panels = {
        "casual": [r * 0.18 + 0.1 for r in feedback],
        "veteran": [r * 0.12 + 0.4 for r in feedback],
        "satisfaction": [r * 0.20 for r in feedback],
        "editor": [0.5 for _ in range(n)],
    }
    result = correlate_personas_with_feedback(panels, feedback, min_pairs=30)
    assert result.insufficient_data is False
    assert result.n_pairs_total == 30
    assert len(result.panels) == 4
    casual = next(p for p in result.panels if p.panel_type == "casual")
    assert casual.pearson > 0.95
    editor = next(p for p in result.panels if p.panel_type == "editor")
    assert editor.pearson == 0.0


def test_report_immutable() -> None:
    result = correlate_personas_with_feedback(
        {"casual": [1.0, 2.0]}, [1.0, 2.0], min_pairs=2
    )
    try:
        result.n_pairs_total = 999  # type: ignore[misc]
    except Exception as exc:
        assert "frozen" in str(exc).lower() or "cannot" in str(exc).lower()
        return
    raise AssertionError("PersonaCorrelationReport should be frozen")
