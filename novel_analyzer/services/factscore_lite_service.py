"""FActScore-lite: pure-function grounding scorer for QA answers.

Takes a list of atomic claims (extracted from an LLM answer by an upstream
LLM call) and a list of retrieval chunks (the evidence pool), and computes
per-claim grounding via simple lexical overlap. Returns frozen dataclass
with overall grounding rate + per-claim verdicts.

This module is the SCORING half of FActScore-lite. The CLAIM EXTRACTION
half requires a new LLM prompt (decompose answer into atomic factual
statements), which would touch novel_analyzer/llm/prompts.py — that file
is currently frozen by the v5 cutover constraint. Until the freeze lifts,
callers must supply pre-extracted claims (e.g. via a heuristic sentence
splitter or external service).

Why lexical overlap and not LLM:
- The whole point of FActScore is to be a CHEAP screen. LLM-based
  per-claim grounding would cost as much as the original answer; we'd
  rather use the per-claim score as a feature, not a gate.
- Anthropic's original FActScore paper (Min et al. 2023) showed that
  retrieval-based lexical scoring correlates ~0.7 with human grounding
  judgments. Good enough to flag answers worth a deeper review.

Boundary contract (same as B1/B4/B5):
- Pure functions; no DB, no LLM, no I/O.
- Input: list[str] claims + list[str] chunks. Output: frozen dataclass.
- Never raises; returns zeroed scores on empty input.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_DEFAULT_MIN_OVERLAP = 0.30


def _chinese_chars(text: str) -> str:
    return "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")


def _claim_tokens(claim: str, *, min_token_len: int = 2) -> set[str]:
    chars = _chinese_chars(claim)
    if len(chars) < min_token_len:
        return set()
    tokens: set[str] = set()
    for n in (2, 3):
        if len(chars) < n:
            continue
        for i in range(len(chars) - n + 1):
            tokens.add(chars[i:i + n])
    return tokens


@dataclass(frozen=True, slots=True)
class ClaimGroundingResult:
    claim: str
    grounded: bool
    overlap_score: float
    matched_chunk_index: int
    matched_chunk_excerpt: str


@dataclass(frozen=True, slots=True)
class FActScoreLiteResult:
    overall_grounding_rate: float
    grounded_count: int
    unsupported_count: int
    total_claims: int
    per_claim: list[ClaimGroundingResult] = field(default_factory=list)


def _score_claim_against_chunks(
    claim: str,
    chunks: list[str],
    *,
    min_overlap: float,
) -> ClaimGroundingResult:
    claim_tokens = _claim_tokens(claim)
    if not claim_tokens:
        return ClaimGroundingResult(
            claim=claim,
            grounded=False,
            overlap_score=0.0,
            matched_chunk_index=-1,
            matched_chunk_excerpt="",
        )

    best_score = 0.0
    best_idx = -1
    for idx, chunk in enumerate(chunks):
        chunk_tokens = _claim_tokens(chunk)
        if not chunk_tokens:
            continue
        intersection = len(claim_tokens & chunk_tokens)
        score = intersection / len(claim_tokens)
        if score > best_score:
            best_score = score
            best_idx = idx

    grounded = best_score >= min_overlap
    excerpt = ""
    if best_idx >= 0:
        excerpt = chunks[best_idx][:120]
    return ClaimGroundingResult(
        claim=claim,
        grounded=grounded,
        overlap_score=round(best_score, 4),
        matched_chunk_index=best_idx,
        matched_chunk_excerpt=excerpt,
    )


def score_grounding(
    claims: list[str],
    chunks: list[str],
    *,
    min_overlap: float = _DEFAULT_MIN_OVERLAP,
) -> FActScoreLiteResult:
    if not claims:
        return FActScoreLiteResult(
            overall_grounding_rate=0.0,
            grounded_count=0,
            unsupported_count=0,
            total_claims=0,
        )

    per_claim: list[ClaimGroundingResult] = []
    for claim in claims:
        per_claim.append(_score_claim_against_chunks(claim, chunks, min_overlap=min_overlap))

    grounded = sum(1 for r in per_claim if r.grounded)
    total = len(per_claim)
    rate = grounded / total if total else 0.0

    return FActScoreLiteResult(
        overall_grounding_rate=round(rate, 4),
        grounded_count=grounded,
        unsupported_count=total - grounded,
        total_claims=total,
        per_claim=per_claim,
    )
