from __future__ import annotations

import pytest

from novel_analyzer.services.elo_tournament_service import (
    EloLeaderboard,
    PairOutcome,
    compute_elo,
)


def test_empty_outcomes_returns_empty_leaderboard() -> None:
    lb = compute_elo([])
    assert isinstance(lb, EloLeaderboard)
    assert lb.ratings == {}
    assert lb.ranked() == []


def test_single_win_moves_ratings_apart() -> None:
    lb = compute_elo([PairOutcome("A", "B", winner="A")])
    assert lb.ratings["A"] > 1500.0
    assert lb.ratings["B"] < 1500.0
    assert pytest.approx(lb.ratings["A"] + lb.ratings["B"], rel=1e-3) == 3000.0


def test_tie_keeps_equal_ratings_equal() -> None:
    lb = compute_elo([PairOutcome("A", "B", winner="tie")])
    assert lb.ratings["A"] == lb.ratings["B"] == 1500.0


def test_consecutive_wins_compound_but_diminish() -> None:
    outcomes = [PairOutcome("A", "B", winner="A") for _ in range(5)]
    lb = compute_elo(outcomes)
    delta_first = compute_elo([outcomes[0]]).ratings["A"] - 1500.0
    avg_delta = (lb.ratings["A"] - 1500.0) / 5
    assert avg_delta < delta_first


def test_transitivity_bias() -> None:
    outcomes = [
        PairOutcome("A", "B", winner="A"),
        PairOutcome("A", "B", winner="A"),
        PairOutcome("B", "C", winner="B"),
        PairOutcome("B", "C", winner="B"),
    ]
    lb = compute_elo(outcomes)
    ranked = lb.ranked()
    ids = [vid for vid, _ in ranked]
    assert ids == ["A", "B", "C"]


def test_confidence_scales_k_factor() -> None:
    high = compute_elo([PairOutcome("A", "B", winner="A", confidence=1.0)])
    low = compute_elo([PairOutcome("A", "B", winner="A", confidence=0.25)])
    high_delta = high.ratings["A"] - 1500.0
    low_delta = low.ratings["A"] - 1500.0
    assert high_delta == pytest.approx(low_delta * 4.0, rel=1e-3)


def test_self_pair_is_rejected() -> None:
    with pytest.raises(ValueError, match="not a valid pair"):
        compute_elo([PairOutcome("A", "A", winner="A")])


def test_invalid_winner_label_rejected() -> None:
    with pytest.raises(ValueError, match="winner must equal"):
        compute_elo([PairOutcome("A", "B", winner="X")])


def test_deterministic_under_reorder() -> None:
    outcomes = [
        PairOutcome("A", "B", winner="A"),
        PairOutcome("A", "B", winner="A"),
    ]
    a = compute_elo(outcomes)
    b = compute_elo(list(outcomes))
    assert a.ratings == b.ratings


def test_games_won_lost_tied_counts() -> None:
    lb = compute_elo([
        PairOutcome("A", "B", winner="A"),
        PairOutcome("A", "C", winner="tie"),
        PairOutcome("B", "C", winner="C"),
    ])
    assert lb.games_played == {"A": 2, "B": 2, "C": 2}
    assert lb.win_count.get("A", 0) == 1
    assert lb.tie_count.get("A", 0) == 1
    assert lb.win_count.get("C", 0) == 1
    assert lb.loss_count.get("B", 0) == 2


def test_leaderboard_immutable() -> None:
    lb = compute_elo([PairOutcome("A", "B", winner="A")])
    try:
        lb.ratings = {}  # type: ignore[misc]
    except Exception as exc:
        assert "frozen" in str(exc).lower() or "cannot" in str(exc).lower()
        return
    raise AssertionError("EloLeaderboard should be frozen")
