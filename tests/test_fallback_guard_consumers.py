from __future__ import annotations

from novel_analyzer.services._fallback_guard import is_heuristic_artifact
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.risk_semantic_signal_service import RiskSemanticSignalService

HEURISTIC_PAYLOAD = {
    "chapter_index": 16,
    "normalized_title": "驱物",
    "key_entities": ["第十六章", "驱物", "汪汪汪", "吱吱吱吱", "犬吠声与"],
    "key_events": ["驱物事件"],
    "continuity_notes": ["本地启发式分析保底生成。"],
    "extraction_source": "heuristic",
}

LLM_PAYLOAD = {
    "chapter_index": 1,
    "normalized_title": "大器晚成",
    "key_entities": ["卫图", "李宅", "李老爷"],
    "key_events": ["卫图觉醒命格"],
    "continuity_notes": ["前情铺垫到位。"],
    "extraction_source": "llm",
}


def test_guard_recognises_explicit_tag() -> None:
    assert is_heuristic_artifact(HEURISTIC_PAYLOAD) is True
    assert is_heuristic_artifact(LLM_PAYLOAD) is False


def test_retrieval_normalize_keywords_skips_heuristic() -> None:
    assert RetrievalService._normalize_keywords(HEURISTIC_PAYLOAD) == []


def test_retrieval_normalize_keywords_passes_llm_payload() -> None:
    keywords = RetrievalService._normalize_keywords(LLM_PAYLOAD)
    assert "卫图" in keywords
    assert "卫图觉醒命格" in keywords


def test_retrieval_query_hints_skips_heuristic_entities() -> None:
    hints = RetrievalService._query_hints(HEURISTIC_PAYLOAD, "驱物")
    assert hints == ["第16章 驱物 讲了什么"]
    assert all("汪汪汪" not in h for h in hints)
    assert all("第十六章 在" not in h for h in hints)


def test_retrieval_query_hints_includes_llm_entities() -> None:
    hints = RetrievalService._query_hints(LLM_PAYLOAD, "大器晚成")
    assert hints[0] == "第1章 大器晚成 讲了什么"
    assert "卫图 在这一章发生了什么" in hints


def test_risk_common_signals_drops_heuristic_entities() -> None:
    common = RiskSemanticSignalService.common_signals(HEURISTIC_PAYLOAD)
    assert common.key_entities == []


def test_risk_common_signals_keeps_llm_entities() -> None:
    common = RiskSemanticSignalService.common_signals(LLM_PAYLOAD)
    assert "卫图" in common.key_entities


def test_legacy_payload_without_tag_falls_back_to_marker() -> None:
    legacy = {**HEURISTIC_PAYLOAD}
    legacy.pop("extraction_source")
    assert is_heuristic_artifact(legacy) is True
    assert RetrievalService._normalize_keywords(legacy) == []
