from __future__ import annotations

from novel_analyzer.services.factscore_lite_service import (
    ClaimGroundingResult,
    FActScoreLiteResult,
    score_grounding,
)


def test_empty_claims_returns_zero() -> None:
    result = score_grounding([], ["some chunk"])
    assert isinstance(result, FActScoreLiteResult)
    assert result.overall_grounding_rate == 0.0
    assert result.grounded_count == 0
    assert result.total_claims == 0
    assert result.per_claim == []


def test_empty_chunks_grounds_nothing() -> None:
    result = score_grounding(["卫图觉醒命格"], [])
    assert result.overall_grounding_rate == 0.0
    assert result.unsupported_count == 1
    assert result.per_claim[0].grounded is False
    assert result.per_claim[0].matched_chunk_index == -1


def test_exact_match_grounds_claim() -> None:
    chunks = ["卫图觉醒命格之后开始修炼养生功"]
    result = score_grounding(["卫图觉醒命格"], chunks)
    assert result.grounded_count == 1
    assert result.overall_grounding_rate == 1.0
    assert result.per_claim[0].overlap_score >= 0.9
    assert result.per_claim[0].matched_chunk_index == 0


def test_unrelated_claim_marked_unsupported() -> None:
    chunks = ["卫图觉醒命格之后开始修炼养生功"]
    result = score_grounding(["路朝歌进入剑宗试炼"], chunks)
    assert result.grounded_count == 0
    assert result.per_claim[0].grounded is False


def test_partial_overlap_threshold() -> None:
    chunks = ["卫图坐在山顶望着远方"]
    result = score_grounding(["卫图觉醒命格之后修炼"], chunks, min_overlap=0.5)
    assert result.per_claim[0].grounded is False
    result_lenient = score_grounding(["卫图觉醒命格之后修炼"], chunks, min_overlap=0.05)
    assert result_lenient.per_claim[0].overlap_score > 0.0
    assert result_lenient.per_claim[0].grounded is True


def test_picks_best_chunk_among_many() -> None:
    chunks = [
        "无关章节描述风景",
        "卫图修炼养生功多年终成大器",
        "另一段无关内容",
    ]
    result = score_grounding(["卫图修炼养生功"], chunks)
    assert result.per_claim[0].matched_chunk_index == 1
    assert result.per_claim[0].grounded is True


def test_aggregate_rate_with_mixed_claims() -> None:
    chunks = ["卫图觉醒命格之后修炼养生功"]
    claims = ["卫图觉醒命格", "卫图修炼养生功", "路朝歌进入剑宗"]
    result = score_grounding(claims, chunks)
    assert result.total_claims == 3
    assert result.grounded_count == 2
    assert result.unsupported_count == 1
    assert result.overall_grounding_rate == round(2 / 3, 4)


def test_result_immutable() -> None:
    result = score_grounding(["c"], ["c"])
    try:
        result.overall_grounding_rate = 999.0  # type: ignore[misc]
    except Exception as exc:
        assert "frozen" in str(exc).lower() or "cannot" in str(exc).lower()
        return
    raise AssertionError("FActScoreLiteResult should be frozen")


def test_excerpt_truncated() -> None:
    long_chunk = "卫图觉醒命格之后" + "修炼" * 200
    result = score_grounding(["卫图觉醒"], [long_chunk])
    assert len(result.per_claim[0].matched_chunk_excerpt) <= 120
