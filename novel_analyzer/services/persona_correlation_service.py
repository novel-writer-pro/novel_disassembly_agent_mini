"""Persona correlation analysis: simulated reader panels vs real reader feedback.

Computes Pearson + Spearman correlation between reader_simulation panel
scores (casual / veteran / satisfaction / editor — see reader_simulation_service)
and real reader feedback ratings (1-5 stars from reader_feedback_comments)
on a per-chapter basis.

Why this matters:
- The 4 simulated reader panels are LLM-prompt-driven heuristics. Without
  validation against real human reader signal, we don't know if "veteran
  panel score = 0.7" actually correlates with "experienced readers liked
  this chapter".
- Loom Phase 5 SOTA progression checklist explicitly calls for this
  correlation as KPI for the persona panels.
- Below 0.5 Pearson → persona prompts need rewriting.

Boundary contract (same as B1/B4/B5/factscore_lite):
- Pure function; takes parallel lists; no DB, no LLM, no I/O.
- Caller is responsible for joining DB rows on (branch_id, chapter_index).
- Returns frozen dataclass. Empty input → zeroed correlations.
- Uses Python stdlib statistics only (no scipy dependency).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean


@dataclass(frozen=True, slots=True)
class CorrelationPanel:
    panel_type: str
    pearson: float
    spearman: float
    n_pairs: int


@dataclass(frozen=True, slots=True)
class PersonaCorrelationReport:
    n_pairs_total: int
    panels: list[CorrelationPanel] = field(default_factory=list)
    overall_pearson: float = 0.0
    overall_spearman: float = 0.0
    insufficient_data: bool = False


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mx = mean(xs)
    my = mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = sum((x - mx) ** 2 for x in xs) ** 0.5
    den_y = sum((y - my) ** 2 for y in ys) ** 0.5
    if den_x == 0 or den_y == 0:
        return 0.0
    return round(num / (den_x * den_y), 4)


def _rank(values: list[float]) -> list[float]:
    indexed = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[indexed[j + 1]] == values[indexed[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k]] = avg_rank
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    return _pearson(_rank(xs), _rank(ys))


def correlate_personas_with_feedback(
    panel_scores: dict[str, list[float]],
    real_feedback_ratings: list[float],
    *,
    min_pairs: int = 30,
) -> PersonaCorrelationReport:
    if not real_feedback_ratings:
        return PersonaCorrelationReport(n_pairs_total=0, insufficient_data=True)

    n = len(real_feedback_ratings)
    insufficient = n < min_pairs
    panels: list[CorrelationPanel] = []
    valid_pearson: list[float] = []
    valid_spearman: list[float] = []

    for panel_type, scores in panel_scores.items():
        if len(scores) != n:
            panels.append(
                CorrelationPanel(
                    panel_type=panel_type, pearson=0.0, spearman=0.0, n_pairs=0
                )
            )
            continue
        pearson = _pearson(scores, real_feedback_ratings)
        spearman = _spearman(scores, real_feedback_ratings)
        panels.append(
            CorrelationPanel(
                panel_type=panel_type,
                pearson=pearson,
                spearman=spearman,
                n_pairs=n,
            )
        )
        valid_pearson.append(pearson)
        valid_spearman.append(spearman)

    overall_pearson = round(mean(valid_pearson), 4) if valid_pearson else 0.0
    overall_spearman = round(mean(valid_spearman), 4) if valid_spearman else 0.0

    return PersonaCorrelationReport(
        n_pairs_total=n,
        panels=panels,
        overall_pearson=overall_pearson,
        overall_spearman=overall_spearman,
        insufficient_data=insufficient,
    )
