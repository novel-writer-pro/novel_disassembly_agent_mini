from langchain_core.messages import AIMessage

from novel_analyzer.domain.schemas import (
    AnalysisSummary,
    AntiFabricationGuardOutput,
    ChapterAnalysisLayerOutput,
    ChapterFactExtractionOutput,
    EvidenceNote,
)
from novel_analyzer.services.analysis_service import AnalysisService


def test_extract_json_payload_accepts_fenced_json() -> None:
    message = AIMessage(
        content='```json\n{"chapter_index":1,"normalized_title":"X"}\n```'
    )
    assert AnalysisService._extract_json_payload(message) == {
        "chapter_index": 1,
        "normalized_title": "X",
    }


def test_state_summary_guard_flags_unsupported_resolution_claims() -> None:
    facts = ChapterFactExtractionOutput(
        conflicts=[],
        relations=[],
        foreshadowing=[],
        worldbuilding_facts=[],
    )
    analysis = ChapterAnalysisLayerOutput(
        summary=AnalysisSummary(short='摘要'),
        continuity_notes=['前文冲突已经彻底解决，规则限制也已解除。'],
    )
    guard = AntiFabricationGuardOutput()
    updated = AnalysisService._state_summary_guard(
        {
            'paid_off_foreshadowing': ['旧伏笔'],
            'escalated_conflicts': ['旧冲突'],
            'evolved_relations': ['旧关系'],
            'constraining_world_rules': ['旧规则'],
        },
        facts,
        analysis,
        guard,
    )
    assert updated.overclaim_flags
    assert updated.needs_human_review


def test_state_summary_guard_keeps_supported_transition_claims_clean() -> None:
    facts = ChapterFactExtractionOutput(
        conflicts=[EvidenceNote(label='旧冲突', evidence=['证据'], confidence=0.8)],
        relations=[EvidenceNote(label='旧关系', evidence=['证据'], confidence=0.8)],
        worldbuilding_facts=[EvidenceNote(label='旧规则', evidence=['证据'], confidence=0.8)],
    )
    analysis = ChapterAnalysisLayerOutput(
        summary=AnalysisSummary(short='摘要'),
        continuity_notes=['旧冲突继续升级，旧关系发生变化，旧规则仍在约束。'],
    )
    guard = AntiFabricationGuardOutput()
    updated = AnalysisService._state_summary_guard(
        {
            'escalated_conflicts': ['旧冲突'],
            'evolved_relations': ['旧关系'],
            'constraining_world_rules': ['旧规则'],
        },
        facts,
        analysis,
        guard,
    )
    assert updated.overclaim_flags == []


def test_derive_state_progression_returns_progress_resolution_and_unresolved_notes() -> None:
    facts = ChapterFactExtractionOutput(
        events=[EvidenceNote(label='卫图因命格得到机缘', evidence=['机缘'], confidence=0.9)],
        relations=[EvidenceNote(label='卫图与命格建立联系', evidence=['命格'], confidence=0.8)],
        conflicts=[EvidenceNote(label='卫图仍受家境掣肘', evidence=['家境'], confidence=0.8)],
        foreshadowing=[EvidenceNote(label='后续还有更大兑现', evidence=['暗示'], confidence=0.7)],
        worldbuilding_facts=[
            EvidenceNote(label='命格决定成长路径', evidence=['规则'], confidence=0.8)
        ],
    )
    analysis = ChapterAnalysisLayerOutput(
        summary=AnalysisSummary(short='摘要'),
        continuity_notes=['命格线继续推进。'],
    )
    transitions, resolutions, unresolved = AnalysisService._derive_state_progression(
        {
            'paid_off_foreshadowing': ['命格后续将改变命运'],
            'escalated_conflicts': ['卫图受限于出身'],
            'evolved_relations': ['卫图与命格建立联系'],
            'constraining_world_rules': ['命格决定成长路径'],
        },
        facts,
        analysis,
    )
    assert transitions
    assert resolutions
    assert unresolved
