"""Elo tournament on top of pairwise evaluation outcomes.

Inspired by autonovel/compare_chapters.py head-to-head Elo. Pure math
helper that aggregates many pairwise comparisons into a stable rating
per draft variant. Operates on already-decided outcomes; this module
does NOT call the LLM judge — it only crunches the comparison results.

Why Elo on top of pairwise:
- pairwise_eval_service today produces single A/B/tie verdicts. Useful
  per-pair, but does not aggregate cleanly across N drafts when N grows
  (the 0509 reward dataset will eventually have 500+ pairs).
- Elo collapses an arbitrary tournament into a single number per draft
  in [base ± ~400], with built-in handling of upsets, ties, and varying
  opponent strength. Same algorithm chess has used since 1960.

Design:
- Caller owns the variant_id namespace. Typical id is a tuple key like
  f"{branch_id}#ch{chapter_index}@{run_id}" but the calculator does not
  enforce that. Just hashable strings.
- Stateless: pass the full outcome list each time, get the full rating
  dict back. No mutable rater object — easy to test, easy to A/B.
- Deterministic: outcomes processed in given order, same input gives
  same output every run.
- K-factor configurable per-call. Default 32 (chess "active player").

Boundary contract (same as B1/B4):
- Pure function, no DB, no LLM, no I/O.
- Never raises on empty / single-variant input.
- Returns frozen dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_DEFAULT_BASE_RATING = 1500.0
_DEFAULT_K_FACTOR = 32.0


@dataclass(frozen=True, slots=True)
class PairOutcome:
    variant_a: str
    variant_b: str
    winner: str
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class EloLeaderboard:
    ratings: dict[str, float] = field(default_factory=dict)
    games_played: dict[str, int] = field(default_factory=dict)
    win_count: dict[str, int] = field(default_factory=dict)
    loss_count: dict[str, int] = field(default_factory=dict)
    tie_count: dict[str, int] = field(default_factory=dict)

    def ranked(self) -> list[tuple[str, float]]:
        return sorted(self.ratings.items(), key=lambda item: (-item[1], item[0]))


def _expected_score(rating_self: float, rating_opp: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_opp - rating_self) / 400.0))


def _resolve_outcome_scores(outcome: PairOutcome) -> tuple[float, float]:
    if outcome.winner == "tie":
        return 0.5, 0.5
    if outcome.winner == outcome.variant_a:
        return 1.0, 0.0
    if outcome.winner == outcome.variant_b:
        return 0.0, 1.0
    raise ValueError(
        f"winner must equal variant_a, variant_b, or 'tie'; "
        f"got winner={outcome.winner!r}, variants=({outcome.variant_a!r}, {outcome.variant_b!r})"
    )


def compute_elo(
    outcomes: list[PairOutcome],
    *,
    base_rating: float = _DEFAULT_BASE_RATING,
    k_factor: float = _DEFAULT_K_FACTOR,
) -> EloLeaderboard:
    if not outcomes:
        return EloLeaderboard()

    ratings: dict[str, float] = {}
    games: dict[str, int] = {}
    wins: dict[str, int] = {}
    losses: dict[str, int] = {}
    ties: dict[str, int] = {}

    for outcome in outcomes:
        a = outcome.variant_a
        b = outcome.variant_b
        if a == b:
            raise ValueError(f"variant_a == variant_b not a valid pair: {a!r}")

        actual_a, actual_b = _resolve_outcome_scores(outcome)

        ratings.setdefault(a, base_rating)
        ratings.setdefault(b, base_rating)
        games[a] = games.get(a, 0) + 1
        games[b] = games.get(b, 0) + 1

        rating_a = ratings[a]
        rating_b = ratings[b]
        expected_a = _expected_score(rating_a, rating_b)
        expected_b = _expected_score(rating_b, rating_a)

        confidence = max(0.0, min(1.0, outcome.confidence))
        effective_k = k_factor * confidence

        ratings[a] = rating_a + effective_k * (actual_a - expected_a)
        ratings[b] = rating_b + effective_k * (actual_b - expected_b)

        if outcome.winner == "tie":
            ties[a] = ties.get(a, 0) + 1
            ties[b] = ties.get(b, 0) + 1
        elif outcome.winner == a:
            wins[a] = wins.get(a, 0) + 1
            losses[b] = losses.get(b, 0) + 1
        else:
            wins[b] = wins.get(b, 0) + 1
            losses[a] = losses.get(a, 0) + 1

    return EloLeaderboard(
        ratings={k: round(v, 2) for k, v in ratings.items()},
        games_played=games,
        win_count=wins,
        loss_count=losses,
        tie_count=ties,
    )
