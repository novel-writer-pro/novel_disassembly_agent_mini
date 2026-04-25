from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings
from novel_analyzer.database.session import create_schema
from novel_analyzer.domain.schemas import (
    AnalysisSummary,
    AntiFabricationGuardOutput,
    ChapterAnalysisLayerOutput,
    ChapterFactExtractionOutput,
    EvidenceNote,
    WriterLearningLensOutput,
)
from novel_analyzer.services.analysis_service import AnalysisService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_extract_json_payload_accepts_fenced_json() -> None:
    message = AIMessage(
        content='```json\n{"chapter_index":1,"normalized_title":"X"}\n```'
    )
    assert AnalysisService._extract_json_payload(message) == {
        "chapter_index": 1,
        "normalized_title": "X",
    }


def test_extract_json_payload_repairs_trailing_comma() -> None:
    message = AIMessage(
        content='{"chapter_index":1,"normalized_title":"X",}'
    )
    assert AnalysisService._extract_json_payload(message) == {
        "chapter_index": 1,
        "normalized_title": "X",
    }


def test_analysis_summary_compact_prefers_short_and_truncates() -> None:
    summary = AnalysisSummary(
        short='这是一个非常长的摘要' * 10,
        one_sentence='一句话',
    )
    compact = summary.compact(max_chars=20)
    assert len(compact) <= 20
    assert compact.endswith('。')


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


def test_early_context_failure_does_not_raise_unboundlocalerror(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n卫图觉醒命格。\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        service = AnalysisService(session, Settings(llm_api_key='test-key'))

        def _boom(*_args: object, **_kwargs: object) -> dict[str, object]:
            raise RuntimeError('boom')

        service.context_service.fact_context_json = _boom  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match='boom'):
            service.analyze_range(run.id, branch.id, 1, 1)


def test_writer_learning_fallback_uses_transition_resolution_and_unresolved() -> None:
    output = WriterLearningLensOutput().ensure_minimum_writer_notes(
        '测试章',
        '这是摘要',
        ['本章推进了关系变化。'],
        ['前文冲突获得阶段性解决。'],
        ['仍有未解线程待处理。'],
    )
    lessons = output.transferable_lessons
    assert lessons
    assert any('推进' in item for item in lessons)
    assert any('可信' in item or '解决' in item for item in lessons)
    assert any('未解线程' in item for item in lessons)
