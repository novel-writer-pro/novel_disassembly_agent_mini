from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings
from novel_analyzer.database.models import ChapterArtifact, ChapterJob, ChapterJobEvent
from novel_analyzer.database.session import create_schema
from novel_analyzer.domain.schemas import (
    AnalysisSummary,
    AntiFabricationGuardOutput,
    ChapterAnalysisLayerOutput,
    ChapterFactExtractionOutput,
    ChapterIntakeOutput,
    EvidenceBindingOutput,
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


def test_chapter_intake_output_accepts_chapter_number_alias() -> None:
    output = ChapterIntakeOutput.model_validate(
        {
            "chapter_number": 12,
            "chapter_title": "测试章",
            "paragraph_blocks": ["第一段", "第二段"],
        }
    )
    assert output.chapter_index == 12
    assert output.normalized_title == "测试章"
    assert output.cleaned_text


def test_chapter_intake_output_accepts_chapter_id_alias() -> None:
    output = ChapterIntakeOutput.model_validate(
        {
            "chapter_id": 10,
            "chapter_title": "测试章",
            "cleaned_text": "正文",
        }
    )
    assert output.chapter_index == 10
    assert output.normalized_title == "测试章"


def test_chapter_intake_output_accepts_title_alias_for_normalized_title() -> None:
    output = ChapterIntakeOutput.model_validate(
        {
            "chapter_number": 3,
            "title": "狡舌",
            "cleaned_text": "正文",
        }
    )
    assert output.chapter_index == 3
    assert output.normalized_title == "狡舌"


def test_chapter_intake_output_accepts_dialogue_candidate_objects() -> None:
    output = ChapterIntakeOutput.model_validate(
        {
            "chapter_number": 2,
            "chapter_title": "厌物丽人同行",
            "cleaned_text": "正文",
            "dialogue_candidates": [
                {"speaker": "青衫少女", "text": "你怎么了？小六子！"},
                {"speaker": "布衣少年", "text": "没，没什么。"},
                {"text": "没有说话人也要兼容。"},
            ],
        }
    )
    assert output.dialogue_candidates == [
        "青衫少女: 你怎么了？小六子！",
        "布衣少年: 没，没什么。",
        "没有说话人也要兼容。",
    ]


def test_stage_chapter_content_trims_large_input() -> None:
    text = "A" * 5000
    trimmed = AnalysisService._stage_chapter_content(text, max_chars=1000)
    assert len(trimmed) < len(text)
    assert "[... 中间内容已为阶段模型省略" in trimmed
    assert trimmed.startswith("A")
    assert trimmed.endswith("A")


def test_build_deconstruction_profile_marks_deferred_writer_without_schema_rename() -> None:
    payload = ChapterIntakeOutput.model_validate(
        {
            "chapter_index": 1,
            "normalized_title": "测试章",
            "cleaned_text": "正文",
        }
    )
    profile = AnalysisService._build_deconstruction_profile(
        chapter_content=payload.cleaned_text,
        stage_payload={},
        writer_deferred=True,
    )
    base = {
        "chapter_index": 1,
        "normalized_title": "测试章",
        "writer_learning_notes": [],
        "unsupported_inferences": [],
        "ambiguous_points": [],
        "quality_gate_notes": [],
    }
    enriched = AnalysisService._with_deconstruction_profile(base, profile)
    assert enriched["writer_learning_notes"] == []
    assert enriched["_deconstruction_profile"]["writer_lens_status"] == "deferred"
    assert "writer_learning_notes" in enriched
    assert "unsupported_inferences" in enriched


def test_writer_learning_lens_accepts_dict_transferable_lessons() -> None:
    output = WriterLearningLensOutput.model_validate(
        {
            'transferable_lessons': [
                {'lesson': '通过未解线索制造后续期待', 'category': 'pacing'},
                {'summary': '让人物关系在冲突中递进'},
                {
                    'lesson_id': 3,
                    'category': 'character_relationship',
                    'content': '把冲突线索埋入日常互动。',
                },
            ]
        }
    )
    assert output.transferable_lessons == [
        '通过未解线索制造后续期待',
        '让人物关系在冲突中递进',
        '把冲突线索埋入日常互动。',
    ]


def test_chapter_analysis_layer_output_accepts_dict_continuity_notes() -> None:
    output = ChapterAnalysisLayerOutput.model_validate(
        {
            "continuity_notes": [
                {"point": "本章对前文冲突做了延续推进。", "confidence": 0.9},
                {"note": "关系变化需要中间证据。"},
                {"text": "章尾通过下一步行动形成钩子。"},
            ]
        }
    )
    assert output.continuity_notes == [
        "本章对前文冲突做了延续推进。",
        "关系变化需要中间证据。",
        "章尾通过下一步行动形成钩子。",
    ]


def test_anti_fabrication_guard_accepts_dict_issue_items() -> None:
    output = AntiFabricationGuardOutput.model_validate(
        {
            'unsupported_inferences': [
                {'target': 'themes[2]', 'message': '该主题结论缺乏直接支撑。'},
                {'summary': '把准备状态说成完成状态。'},
            ],
            'ambiguous_points': [
                {'note': '角色动机仍可有两种解释。'},
            ],
            'overclaim_flags': [
                {'reason': '结论强度超过证据强度。'},
            ],
        }
    )
    assert output.unsupported_inferences == [
        '该主题结论缺乏直接支撑。',
        '把准备状态说成完成状态。',
    ]
    assert output.ambiguous_points == ['角色动机仍可有两种解释。']
    assert output.overclaim_flags == ['结论强度超过证据强度。']


def test_evidence_binding_accepts_dict_unsupported_items() -> None:
    output = EvidenceBindingOutput.model_validate(
        {
            'retained_items': [],
            'unsupported_items': [
                {'label': '巫仙师的动机缺乏原文直接支撑。'},
                {'summary': '把筹备状态误写成已完成。'},
            ],
            'coverage_summary': 'ok',
        }
    )
    assert output.unsupported_items == [
        '巫仙师的动机缺乏原文直接支撑。',
        '把筹备状态误写成已完成。',
    ]


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
        service = AnalysisService(session, Settings(llm_api_key='test-key', use_merged_stages=False))

        def _boom(*_args: object, **_kwargs: object) -> dict[str, object]:
            raise RuntimeError('boom')

        service.context_service.fact_context_json = _boom  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match='boom'):
            service.analyze_range(run.id, branch.id, 1, 1)


def test_risk_audit_failure_does_not_break_main_chapter_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n卫图觉醒命格。\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        service = AnalysisService(session, Settings(llm_api_key='test-key', use_merged_stages=False))

        monkeypatch.setattr(
            service,
            '_invoke_stage',
            lambda model, prompt, schema: schema.model_validate(
                {
                    'chapter_index': 1,
                    'normalized_title': '一',
                    'cleaned_text': '第1章 一\n卫图觉醒命格。',
                    'paragraph_blocks': [{'order': 1, 'text': '卫图觉醒命格。'}],
                }
                if schema.__name__ == 'ChapterIntakeOutput'
                else (
                    {
                        'characters': [{'label': '卫图', 'evidence': ['卫图'], 'confidence': 0.9}],
                        'events': [
                            {'label': '卫图觉醒命格', 'evidence': ['觉醒命格'], 'confidence': 0.9}
                        ],
                        'relations': [],
                        'conflicts': [],
                        'foreshadowing': [],
                        'worldbuilding_facts': [],
                    }
                    if schema.__name__ == 'ChapterFactExtractionOutput'
                    else (
                        {
                            'retained_items': [
                                {'label': '卫图', 'evidence': ['卫图'], 'confidence': 0.9}
                            ],
                            'unsupported_items': [],
                            'coverage_summary': 'ok',
                        }
                        if schema.__name__ == 'EvidenceBindingOutput'
                        else (
                            {
                                'summary': {'short': '卫图觉醒命格。'},
                                'themes': [],
                                'pacing': {},
                                'emotional_curve': {},
                                'continuity_notes': ['主线开启。'],
                            }
                            if schema.__name__ == 'ChapterAnalysisLayerOutput'
                            else (
                                {
                                    'hook_notes': [],
                                    'conflict_notes': [],
                                    'reveal_order_notes': [],
                                    'scene_efficiency_notes': [],
                                    'transferable_lessons': [],
                                }
                                if schema.__name__ == 'WriterLearningLensOutput'
                                else {
                                    'overclaim_flags': [],
                                    'ambiguous_points': [],
                                    'needs_human_review': False,
                                }
                            )
                        )
                    )
                )
            ),
        )

        monkeypatch.setattr(
            service.risk_audit_service,
            'generate_for_chapter',
            lambda branch_id, chapter_index: (_ for _ in ()).throw(RuntimeError('audit boom')),
        )

        artifact_ids = service.analyze_range(run.id, branch.id, 1, 1)
        assert len(artifact_ids) == 1
        job = session.scalar(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch.id)
            .where(ChapterJob.chapter_index == 1)
        )
        assert job is not None
        assert job.status == 'validated'


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


def test_provider_unavailable_uses_local_heuristic_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text(
        '第22章 卫图的拒绝\n卫图决定拒绝对方提议，但仍承受身份压力。\n',
        encoding='utf-8',
    )

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        service = AnalysisService(session, Settings(llm_api_key='test-key', use_merged_stages=False))

        def _provider_down(*_args: object, **_kwargs: object) -> dict[str, object]:
            raise RuntimeError("Error code: 403 - {'code':'SUBSCRIPTION_NOT_FOUND'}")

        monkeypatch.setattr(service, '_invoke_stage', _provider_down)
        monkeypatch.setattr(service, '_invoke_monolithic_analysis', _provider_down)

        artifact_ids = service.analyze_range(run.id, branch.id, 1, 1)
        assert len(artifact_ids) == 1
        job = session.scalar(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch.id)
            .where(ChapterJob.chapter_index == 1)
        )
        assert job is not None
        assert job.status == 'validated'


def test_materialization_failure_restores_previous_active_artifact_and_blocks_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n卫图觉醒命格。\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        previous = RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '旧版本',
                'chapter_summary': '旧摘要',
                'key_entities': ['卫图'],
                'key_events': ['旧事件'],
                'continuity_notes': ['旧衔接'],
                'writer_learning_notes': [],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': False,
                'quality_gate_notes': [],
                'hook_score': 4.0,
                'dimensions': [],
            },
        )
        service = AnalysisService(session, Settings(llm_api_key='test-key', embedding_backend='stub'))

        monkeypatch.setattr(
            service,
            '_invoke_stage',
            lambda model, prompt, schema: schema.model_validate(
                {
                    'chapter_index': 1,
                    'normalized_title': '一',
                    'cleaned_text': '第1章 一\n卫图觉醒命格。',
                    'paragraph_blocks': [{'order': 1, 'text': '卫图觉醒命格。'}],
                }
                if schema.__name__ == 'ChapterIntakeOutput'
                else (
                    {
                        'characters': [{'label': '卫图', 'evidence': ['卫图'], 'confidence': 0.9}],
                        'events': [{'label': '卫图觉醒命格', 'evidence': ['觉醒命格'], 'confidence': 0.9}],
                        'relations': [],
                        'conflicts': [],
                        'foreshadowing': [],
                        'worldbuilding_facts': [],
                    }
                    if schema.__name__ == 'ChapterFactExtractionOutput'
                    else (
                        {
                            'retained_items': [{'label': '卫图', 'evidence': ['卫图'], 'confidence': 0.9}],
                            'unsupported_items': [],
                            'coverage_summary': 'ok',
                        }
                        if schema.__name__ == 'EvidenceBindingOutput'
                        else (
                            {
                                'summary': {'short': '卫图觉醒命格。'},
                                'themes': [],
                                'pacing': {},
                                'emotional_curve': {},
                                'continuity_notes': ['主线开启。'],
                            }
                            if schema.__name__ == 'ChapterAnalysisLayerOutput'
                            else (
                                {
                                    'hook_notes': [],
                                    'conflict_notes': [],
                                    'reveal_order_notes': [],
                                    'scene_efficiency_notes': [],
                                    'transferable_lessons': [],
                                }
                                if schema.__name__ == 'WriterLearningLensOutput'
                                else {'overclaim_flags': [], 'ambiguous_points': [], 'needs_human_review': False}
                            )
                        )
                    )
                )
            ),
        )
        monkeypatch.setattr(
            service.retrieval_service,
            'materialize_for_artifact',
            lambda artifact_id: (_ for _ in ()).throw(RuntimeError('retrieval boom')),
        )

        with pytest.raises(RuntimeError, match='retrieval boom'):
            service.analyze_range(run.id, branch.id, 1, 1)

        job = session.scalar(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch.id)
            .where(ChapterJob.chapter_index == 1)
        )
        assert job is not None
        assert job.status == 'failed'

        artifacts = session.scalars(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch.id)
            .where(ChapterArtifact.chapter_index == 1)
            .order_by(ChapterArtifact.created_at)
        ).all()
        assert len(artifacts) == 2
        active_ids = [artifact.id for artifact in artifacts if artifact.visibility == 'active']
        assert active_ids == [previous.id]
        assert artifacts[-1].visibility == 'hidden'


def test_quick_profile_defers_writer_lens_stage_and_preserves_profile(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n卫图觉醒命格。\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)

        service = AnalysisService(session, Settings(llm_api_key='test-key', use_merged_stages=False))
        responses = iter([
            '{"chapter_index":1,"normalized_title":"一","cleaned_text":"第1章 一\n卫图觉醒命格。","paragraph_blocks":[{"order":1,"text":"第1章 一"}],"notes":[]}',
            '{"characters":[{"label":"卫图","evidence":["卫图觉醒命格。"],"confidence":0.9}],"events":[{"label":"卫图觉醒命格","evidence":["卫图觉醒命格。"],"confidence":0.9}],"relations":[],"conflicts":[],"foreshadowing":[],"worldbuilding_facts":[]}',
            '{"retained_items":[{"label":"卫图觉醒命格","evidence":["卫图觉醒命格。"],"confidence":0.9}],"unsupported_items":[],"coverage_summary":"ok"}',
            '{"summary":{"one_sentence":"卫图觉醒命格。","short":"卫图觉醒命格。","detailed":"卫图觉醒命格。"},"themes":[],"pacing":{},"emotional_curve":{},"continuity_notes":["主线开启"]}',
            '{"unsupported_inferences":[],"ambiguous_points":[],"overclaim_flags":[],"needs_human_review":false}',
        ])

        def _fake_invoke(_model, _prompt):
            return AIMessage(content=next(responses))

        service._invoke_with_retry = _fake_invoke  # type: ignore[method-assign]
        service.analyze_range(run.id, branch.id, 1, 1)

        artifact = session.scalar(
            select(ChapterArtifact).where(ChapterArtifact.branch_id == branch.id)
        )
        assert artifact is not None
        assert artifact.payload_json['writer_learning_notes'] == []
        assert artifact.payload_json['_deconstruction_profile']['writer_lens_status'] == 'deferred'


def test_quick_profile_defers_risk_aggregation_stage(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n卫图觉醒命格。\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)

        service = AnalysisService(session, Settings(llm_api_key='test-key', use_merged_stages=False))
        responses = iter([
            '{"chapter_index":1,"normalized_title":"一","cleaned_text":"第1章 一\\n卫图觉醒命格。","paragraph_blocks":[{"order":1,"text":"第1章 一"}],"notes":[]}',
            '{"characters":[{"label":"卫图","evidence":["卫图觉醒命格。"],"confidence":0.9}],"events":[{"label":"卫图觉醒命格","evidence":["卫图觉醒命格。"],"confidence":0.9}],"relations":[],"conflicts":[],"foreshadowing":[],"worldbuilding_facts":[]}',
            '{"retained_items":[{"label":"卫图觉醒命格","evidence":["卫图觉醒命格。"],"confidence":0.9}],"unsupported_items":[],"coverage_summary":"ok"}',
            '{"summary":{"one_sentence":"卫图觉醒命格。","short":"卫图觉醒命格。","detailed":"卫图觉醒命格。"},"themes":[],"pacing":{},"emotional_curve":{},"continuity_notes":["主线开启"]}',
            '{"unsupported_inferences":[],"ambiguous_points":[],"overclaim_flags":[],"needs_human_review":false}',
        ])

        def _fake_invoke(_model, _prompt):
            return AIMessage(content=next(responses))

        service._invoke_with_retry = _fake_invoke  # type: ignore[method-assign]
        service.analyze_range(run.id, branch.id, 1, 1)

        job = session.scalar(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch.id)
            .where(ChapterJob.chapter_index == 1)
        )
        assert job is not None
        events = session.scalars(
            select(ChapterJobEvent)
            .where(ChapterJobEvent.branch_id == branch.id)
            .where(ChapterJobEvent.chapter_index == 1)
        ).all()
        labels = [f"{item.event_type}:{item.stage}:{item.message}" for item in events]
        assert any('stage_deferred:risk_aggregation:' in item for item in labels)


def test_compact_state_summary_json_keeps_only_key_lists() -> None:
    payload = AnalysisService._compact_state_summary_json(
        {
            'paid_off_foreshadowing': ['A', 'B', 'C', 'D'],
            'escalated_conflicts': ['X'],
            'evolved_relations': [],
            'constraining_world_rules': ['R1', 'R2'],
            'active_conflicts': ['should-drop'],
            'misc': {'ignored': True},
        }
    )
    assert 'should-drop' not in payload
    assert 'misc' not in payload
    assert 'A' in payload and 'C' in payload
    assert 'D' not in payload
    assert 'R1' in payload


def test_analysis_and_guard_prompts_use_compact_state_and_no_graph_context(monkeypatch, tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n卫图觉醒命格。\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        service = AnalysisService(session, Settings(llm_api_key='test-key', use_merged_stages=False))

        captured: list[tuple[str, str]] = []
        real_build = __import__('novel_analyzer.services.analysis_service', fromlist=['build_agent_stage_prompts'])
        original = real_build.build_agent_stage_prompts

        def _capture(context):
            prompts = original(context)
            if context.evidence_bound_json != '{}' or context.analysis_json != '{}':
                captured.append(prompts['analysis_generator'])
                captured.append(prompts['anti_fabrication_guard'])
            return prompts

        monkeypatch.setattr('novel_analyzer.services.analysis_service.build_agent_stage_prompts', _capture)
        monkeypatch.setattr(service.context_service, 'previous_summary', lambda *args, **kwargs: '前情')
        monkeypatch.setattr(service.context_service, 'fact_context_json', lambda *args, **kwargs: {'facts': []})
        monkeypatch.setattr(service.context_service, 'graph_context_json', lambda *args, **kwargs: {'overview': {'node_count': 999}, 'central_nodes': ['GRAPH-BIG']})
        monkeypatch.setattr(service.context_service, 'state_summary_json', lambda *args, **kwargs: {
            'paid_off_foreshadowing': ['伏笔A', '伏笔B', '伏笔C', '伏笔D'],
            'escalated_conflicts': ['冲突X'],
            'constraining_world_rules': ['规则R'],
            'active_conflicts': ['不应进入analysis/guard prompt'],
        })
        monkeypatch.setattr(service.context_service, 'window_summary', lambda *args, **kwargs: '窗口摘要')

        responses = iter([
            '{"chapter_index":1,"normalized_title":"一","cleaned_text":"第1章 一\\n卫图觉醒命格。","paragraph_blocks":[{"order":1,"text":"第1章 一"}],"notes":[]}',
            '{"characters":[{"label":"卫图","evidence":["卫图觉醒命格。"],"confidence":0.9}],"events":[{"label":"卫图觉醒命格","evidence":["卫图觉醒命格。"],"confidence":0.9}],"relations":[],"conflicts":[],"foreshadowing":[],"worldbuilding_facts":[]}',
            '{"retained_items":[{"label":"卫图觉醒命格","evidence":["卫图觉醒命格。"],"confidence":0.9}],"unsupported_items":[],"coverage_summary":"ok"}',
            '{"summary":{"one_sentence":"卫图觉醒命格。","short":"卫图觉醒命格。","detailed":"卫图觉醒命格。"},"themes":[],"pacing":{},"emotional_curve":{},"continuity_notes":["主线开启"]}',
            '{"unsupported_inferences":[],"ambiguous_points":[],"overclaim_flags":[],"needs_human_review":false}',
        ])

        def _fake_invoke(_model, _prompt):
            return AIMessage(content=next(responses))

        service._invoke_with_retry = _fake_invoke  # type: ignore[method-assign]
        service.analyze_range(run.id, branch.id, 1, 1)

        joined = '\n'.join(captured)
        assert 'GRAPH-BIG' not in joined
        assert '不应进入analysis/guard prompt' not in joined
        assert '伏笔A' in joined
        assert '伏笔D' not in joined


def test_fact_and_evidence_prompts_drop_graph_and_minimize_state(monkeypatch, tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n卫图觉醒命格。\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        service = AnalysisService(session, Settings(llm_api_key='test-key', use_merged_stages=False))

        captured: list[tuple[str, str]] = []
        real_build = __import__('novel_analyzer.services.analysis_service', fromlist=['build_agent_stage_prompts'])
        original = real_build.build_agent_stage_prompts

        def _capture(context):
            prompts = original(context)
            if context.fact_json == '{}' and context.intake_json != '{}':
                captured.append(('fact', prompts['fact_extractor']))
            if context.fact_json != '{}':
                captured.append(('evidence', prompts['evidence_binder']))
            return prompts

        monkeypatch.setattr('novel_analyzer.services.analysis_service.build_agent_stage_prompts', _capture)
        monkeypatch.setattr(service.context_service, 'previous_summary', lambda *args, **kwargs: '前情')
        monkeypatch.setattr(service.context_service, 'fact_context_json', lambda *args, **kwargs: {'facts': ['FACT-BIG']})
        monkeypatch.setattr(service.context_service, 'graph_context_json', lambda *args, **kwargs: {'overview': {'node_count': 999}, 'central_nodes': ['GRAPH-BIG']})
        monkeypatch.setattr(service.context_service, 'state_summary_json', lambda *args, **kwargs: {
            'paid_off_foreshadowing': ['伏笔A', '伏笔B', '伏笔C', '伏笔D'],
            'escalated_conflicts': ['冲突X'],
            'constraining_world_rules': ['规则R'],
            'active_conflicts': ['不应进入fact/evidence prompt'],
        })
        monkeypatch.setattr(service.context_service, 'window_summary', lambda *args, **kwargs: '窗口摘要')

        responses = iter([
            '{"chapter_index":1,"normalized_title":"一","cleaned_text":"第1章 一\\n卫图觉醒命格。","paragraph_blocks":[{"order":1,"text":"第1章 一"}],"notes":[]}',
            '{"characters":[{"label":"卫图","evidence":["卫图觉醒命格。"],"confidence":0.9}],"events":[{"label":"卫图觉醒命格","evidence":["卫图觉醒命格。"],"confidence":0.9}],"relations":[],"conflicts":[],"foreshadowing":[],"worldbuilding_facts":[]}',
            '{"retained_items":[{"label":"卫图觉醒命格","evidence":["卫图觉醒命格。"],"confidence":0.9}],"unsupported_items":[],"coverage_summary":"ok"}',
            '{"summary":{"one_sentence":"卫图觉醒命格。","short":"卫图觉醒命格。","detailed":"卫图觉醒命格。"},"themes":[],"pacing":{},"emotional_curve":{},"continuity_notes":["主线开启"]}',
            '{"unsupported_inferences":[],"ambiguous_points":[],"overclaim_flags":[],"needs_human_review":false}',
        ])

        def _fake_invoke(_model, _prompt):
            return AIMessage(content=next(responses))

        service._invoke_with_retry = _fake_invoke  # type: ignore[method-assign]
        service.analyze_range(run.id, branch.id, 1, 1)

        fact_prompt = next(text for kind, text in captured if kind == 'fact')
        evidence_prompt = next(text for kind, text in captured if kind == 'evidence')
        assert 'GRAPH-BIG' not in fact_prompt
        assert 'GRAPH-BIG' not in evidence_prompt
        assert '不应进入fact/evidence prompt' not in fact_prompt
        assert '窗口摘要' not in evidence_prompt
        assert '伏笔A' in fact_prompt
        assert '伏笔D' not in fact_prompt


def test_compact_prior_context_json_keeps_only_small_fact_fields() -> None:
    payload = AnalysisService._compact_prior_context_json(
        {
            'previous_summary': '这是一个很长的前情摘要。' * 40,
            'facts': [
                {'chapter_index': 1, 'fact_type': 'entity', 'label': '卫图', 'confidence': 0.9, 'evidence': ['drop-me']},
                {'chapter_index': 2, 'fact_type': 'event', 'label': '觉醒命格', 'confidence': 0.8, 'metadata': {'drop': True}},
            ],
            'other': {'ignored': True},
        }
    )
    assert 'drop-me' not in payload
    assert 'metadata' not in payload
    assert 'ignored' not in payload
    assert '卫图' in payload and '觉醒命格' in payload
    assert len(payload) < 600


def test_fact_analysis_and_guard_prompts_use_compact_prior_context(monkeypatch, tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n卫图觉醒命格。\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        service = AnalysisService(session, Settings(llm_api_key='test-key', use_merged_stages=False))

        captured: list[str] = []
        real_build = __import__('novel_analyzer.services.analysis_service', fromlist=['build_agent_stage_prompts'])
        original = real_build.build_agent_stage_prompts

        def _capture(context):
            prompts = original(context)
            if context.intake_json != '{}' and context.fact_json == '{}':
                captured.append(('fact', prompts['fact_extractor']))
            if context.evidence_bound_json != '{}':
                captured.append(('analysis', prompts['analysis_generator']))
                captured.append(('guard', prompts['anti_fabrication_guard']))
            return prompts

        monkeypatch.setattr('novel_analyzer.services.analysis_service.build_agent_stage_prompts', _capture)
        monkeypatch.setattr(service.context_service, 'previous_summary', lambda *args, **kwargs: '前情')
        monkeypatch.setattr(service.context_service, 'fact_context_json', lambda *args, **kwargs: {
            'previous_summary': '很长很长的前情摘要' * 50,
            'facts': [
                {'chapter_index': 1, 'fact_type': 'entity', 'label': '卫图', 'confidence': 0.9, 'evidence': ['SHOULD-DROP']},
                {'chapter_index': 2, 'fact_type': 'event', 'label': '觉醒命格', 'confidence': 0.8, 'metadata': {'drop': True}},
            ],
        })
        monkeypatch.setattr(service.context_service, 'graph_context_json', lambda *args, **kwargs: {'overview': {'node_count': 999}, 'central_nodes': ['GRAPH-BIG']})
        monkeypatch.setattr(service.context_service, 'state_summary_json', lambda *args, **kwargs: {'paid_off_foreshadowing': ['伏笔A']})
        monkeypatch.setattr(service.context_service, 'window_summary', lambda *args, **kwargs: '窗口摘要')

        responses = iter([
            '{"chapter_index":1,"normalized_title":"一","cleaned_text":"第1章 一\\n卫图觉醒命格。","paragraph_blocks":[{"order":1,"text":"第1章 一"}],"notes":[]}',
            '{"characters":[{"label":"卫图","evidence":["卫图觉醒命格。"],"confidence":0.9}],"events":[{"label":"卫图觉醒命格","evidence":["卫图觉醒命格。"],"confidence":0.9}],"relations":[],"conflicts":[],"foreshadowing":[],"worldbuilding_facts":[]}',
            '{"retained_items":[{"label":"卫图觉醒命格","evidence":["卫图觉醒命格。"],"confidence":0.9}],"unsupported_items":[],"coverage_summary":"ok"}',
            '{"summary":{"one_sentence":"卫图觉醒命格。","short":"卫图觉醒命格。","detailed":"卫图觉醒命格。"},"themes":[],"pacing":{},"emotional_curve":{},"continuity_notes":["主线开启"]}',
            '{"unsupported_inferences":[],"ambiguous_points":[],"overclaim_flags":[],"needs_human_review":false}',
        ])

        def _fake_invoke(_model, _prompt):
            return AIMessage(content=next(responses))

        service._invoke_with_retry = _fake_invoke  # type: ignore[method-assign]
        service.analyze_range(run.id, branch.id, 1, 1)

        fact_prompt = next(text for kind, text in captured if kind == 'fact')
        analysis_prompt = next(text for kind, text in captured if kind == 'analysis')
        guard_prompt = next(text for kind, text in captured if kind == 'guard')
        joined = '\n'.join([fact_prompt, analysis_prompt, guard_prompt])
        assert 'SHOULD-DROP' not in joined
        assert 'metadata' not in joined
        assert '卫图' in joined
        assert '觉醒命格' in joined


def test_prompt_budget_guards_on_real_weitu_ch20_context() -> None:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from novel_analyzer.database.models import RunBranch, ChapterManifest, ChapterSegment
    from novel_analyzer.agent.pipeline import ChapterAgentContext, build_agent_stage_prompts
    from novel_analyzer.services.context_service import ContextService

    dburl = 'postgresql+psycopg://d2:d2pass@127.0.0.1:5432/novel_analyzer_weitu_deconstruction_20260511'
    engine = create_engine(dburl, future=True)
    branch_id = '03c657c8-5389-4e42-9234-b14137c04125'
    with Session(engine) as session:
        branch = session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        assert branch is not None
        manifest = session.scalar(select(ChapterManifest).where(ChapterManifest.id == branch.run.manifest_id))
        assert manifest is not None
        segment = session.scalar(
            select(ChapterSegment)
            .where(ChapterSegment.manifest_id == manifest.id)
            .where(ChapterSegment.chapter_index == 20)
        )
        assert segment is not None
        source_text = Path(branch.run.novel.source_path).read_text(encoding='utf-8')
        chapter_content = source_text[segment.start_offset:segment.end_offset].strip()
        staged = AnalysisService._stage_chapter_content(chapter_content)
        ctx = ContextService(session)
        previous_summary = ctx.previous_summary(branch_id, 20)
        prior_context = ctx.fact_context_json(branch_id, 20)
        state_summary = ctx.state_summary_json(branch_id, 20)
        compact_prior_context_json = AnalysisService._compact_prior_context_json(prior_context)
        compact_state_summary_json = AnalysisService._compact_state_summary_json(state_summary)

        fact_prompt = build_agent_stage_prompts(ChapterAgentContext(
            chapter_index=20,
            normalized_title=segment.normalized_title,
            chapter_content=staged,
            previous_summary=previous_summary,
            intake_json='{"chapter_index":20}',
            prior_context_json=compact_prior_context_json,
            graph_context_json='{}',
            state_summary_json=compact_state_summary_json,
            cleaned_text='sample cleaned text',
            window_summary=ctx.window_summary(branch_id, 20),
        ))['fact_extractor']
        analysis_prompt = build_agent_stage_prompts(ChapterAgentContext(
            chapter_index=20,
            normalized_title=segment.normalized_title,
            chapter_content=staged,
            previous_summary=previous_summary,
            intake_json='{"chapter_index":20}',
            prior_context_json=compact_prior_context_json,
            graph_context_json='{}',
            state_summary_json=compact_state_summary_json,
            cleaned_text='sample cleaned text',
            window_summary=ctx.window_summary(branch_id, 20),
            fact_json='{"events":[{"label":"x"}]}',
            evidence_bound_json='{"retained_items":[{"label":"x"}]}',
        ))['analysis_generator']
        guard_prompt = build_agent_stage_prompts(ChapterAgentContext(
            chapter_index=20,
            normalized_title=segment.normalized_title,
            chapter_content=staged,
            previous_summary=previous_summary,
            intake_json='{"chapter_index":20}',
            prior_context_json=compact_prior_context_json,
            graph_context_json='{}',
            state_summary_json=compact_state_summary_json,
            cleaned_text='sample cleaned text',
            window_summary=ctx.window_summary(branch_id, 20),
            fact_json='{"events":[{"label":"x"}]}',
            analysis_json='{"summary":{"short":"x"}}',
            writer_json='{}',
            chapter_json='{}',
        ))['anti_fabrication_guard']

        assert len(fact_prompt) < 3000
        assert len(analysis_prompt) < 2000
        assert len(guard_prompt) < 1200


def test_prompt_budget_regression_ratios_on_real_weitu_ch20_context() -> None:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from novel_analyzer.database.models import RunBranch, ChapterManifest, ChapterSegment
    from novel_analyzer.agent.pipeline import ChapterAgentContext, build_agent_stage_prompts
    from novel_analyzer.services.context_service import ContextService
    import json

    dburl = 'postgresql+psycopg://d2:d2pass@127.0.0.1:5432/novel_analyzer_weitu_deconstruction_20260511'
    engine = create_engine(dburl, future=True)
    branch_id = '03c657c8-5389-4e42-9234-b14137c04125'
    with Session(engine) as session:
        branch = session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        assert branch is not None
        manifest = session.scalar(select(ChapterManifest).where(ChapterManifest.id == branch.run.manifest_id))
        assert manifest is not None
        segment = session.scalar(
            select(ChapterSegment)
            .where(ChapterSegment.manifest_id == manifest.id)
            .where(ChapterSegment.chapter_index == 20)
        )
        assert segment is not None
        source_text = Path(branch.run.novel.source_path).read_text(encoding='utf-8')
        chapter_content = source_text[segment.start_offset:segment.end_offset].strip()
        staged = AnalysisService._stage_chapter_content(chapter_content)
        ctx = ContextService(session)
        previous_summary = ctx.previous_summary(branch_id, 20)
        prior_context = ctx.fact_context_json(branch_id, 20)
        graph_context = ctx.graph_context_json(branch_id, 20)
        state_summary = ctx.state_summary_json(branch_id, 20)
        window_summary = ctx.window_summary(branch_id, 20)
        prior_context_json = json.dumps(prior_context, ensure_ascii=False, indent=2)
        graph_context_json = json.dumps(graph_context, ensure_ascii=False, indent=2)
        state_summary_json = json.dumps(state_summary, ensure_ascii=False, indent=2)
        compact_prior_context_json = AnalysisService._compact_prior_context_json(prior_context)
        compact_state_summary_json = AnalysisService._compact_state_summary_json(state_summary)

        old_fact = build_agent_stage_prompts(ChapterAgentContext(
            chapter_index=20, normalized_title=segment.normalized_title, chapter_content=staged,
            previous_summary=previous_summary, intake_json='{"chapter_index":20}', prior_context_json=prior_context_json,
            graph_context_json=graph_context_json, state_summary_json=state_summary_json,
            cleaned_text='sample cleaned text', window_summary=window_summary,
        ))['fact_extractor']
        new_fact = build_agent_stage_prompts(ChapterAgentContext(
            chapter_index=20, normalized_title=segment.normalized_title, chapter_content=staged,
            previous_summary=previous_summary, intake_json='{"chapter_index":20}', prior_context_json=compact_prior_context_json,
            graph_context_json='{}', state_summary_json=compact_state_summary_json,
            cleaned_text='sample cleaned text', window_summary=window_summary,
        ))['fact_extractor']
        old_analysis = build_agent_stage_prompts(ChapterAgentContext(
            chapter_index=20, normalized_title=segment.normalized_title, chapter_content=staged,
            previous_summary=previous_summary, intake_json='{"chapter_index":20}', prior_context_json=prior_context_json,
            graph_context_json=graph_context_json, state_summary_json=state_summary_json,
            cleaned_text='sample cleaned text', window_summary=window_summary,
            fact_json='{"events":[{"label":"x"}]}', evidence_bound_json='{"retained_items":[{"label":"x"}]}'
        ))['analysis_generator']
        new_analysis = build_agent_stage_prompts(ChapterAgentContext(
            chapter_index=20, normalized_title=segment.normalized_title, chapter_content=staged,
            previous_summary=previous_summary, intake_json='{"chapter_index":20}', prior_context_json=compact_prior_context_json,
            graph_context_json='{}', state_summary_json=compact_state_summary_json,
            cleaned_text='sample cleaned text', window_summary=window_summary,
            fact_json='{"events":[{"label":"x"}]}', evidence_bound_json='{"retained_items":[{"label":"x"}]}'
        ))['analysis_generator']
        old_guard = build_agent_stage_prompts(ChapterAgentContext(
            chapter_index=20, normalized_title=segment.normalized_title, chapter_content=staged,
            previous_summary=previous_summary, intake_json='{"chapter_index":20}', prior_context_json=prior_context_json,
            graph_context_json=graph_context_json, state_summary_json=state_summary_json,
            cleaned_text='sample cleaned text', window_summary=window_summary,
            fact_json='{"events":[{"label":"x"}]}', analysis_json='{"summary":{"short":"x"}}', writer_json='{}', chapter_json='{}'
        ))['anti_fabrication_guard']
        new_guard = build_agent_stage_prompts(ChapterAgentContext(
            chapter_index=20, normalized_title=segment.normalized_title, chapter_content=staged,
            previous_summary=previous_summary, intake_json='{"chapter_index":20}', prior_context_json=compact_prior_context_json,
            graph_context_json='{}', state_summary_json=compact_state_summary_json,
            cleaned_text='sample cleaned text', window_summary=window_summary,
            fact_json='{"events":[{"label":"x"}]}', analysis_json='{"summary":{"short":"x"}}', writer_json='{}', chapter_json='{}'
        ))['anti_fabrication_guard']

        assert len(new_fact) / len(old_fact) < 0.12
        assert len(new_analysis) / len(old_analysis) < 0.1
        assert len(new_guard) / len(old_guard) < 0.1


def test_compact_previous_summary_truncates_and_marks_ellipsis() -> None:
    text = '卫图' * 200
    compact = AnalysisService._compact_previous_summary(text, max_chars=50)
    assert len(compact) <= 50
    assert compact.endswith('…')


def test_stage_prompts_use_compacted_previous_summary(monkeypatch, tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n卫图觉醒命格。\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        service = AnalysisService(session, Settings(llm_api_key='test-key', use_merged_stages=False))

        captured: list[str] = []
        real_build = __import__('novel_analyzer.services.analysis_service', fromlist=['build_agent_stage_prompts'])
        original = real_build.build_agent_stage_prompts

        def _capture(context):
            prompts = original(context)
            captured.append(prompts['chapter_intake'])
            captured.append(prompts['fact_extractor'])
            return prompts

        monkeypatch.setattr('novel_analyzer.services.analysis_service.build_agent_stage_prompts', _capture)
        monkeypatch.setattr(service.context_service, 'previous_summary', lambda *args, **kwargs: '上一章摘要' * 200)
        monkeypatch.setattr(service.context_service, 'fact_context_json', lambda *args, **kwargs: {'facts': []})
        monkeypatch.setattr(service.context_service, 'graph_context_json', lambda *args, **kwargs: {})
        monkeypatch.setattr(service.context_service, 'state_summary_json', lambda *args, **kwargs: {})
        monkeypatch.setattr(service.context_service, 'window_summary', lambda *args, **kwargs: '')

        responses = iter([
            '{"chapter_index":1,"normalized_title":"一","cleaned_text":"第1章 一\\n卫图觉醒命格。","paragraph_blocks":[{"order":1,"text":"第1章 一"}],"notes":[]}',
            '{"characters":[{"label":"卫图","evidence":["卫图觉醒命格。"],"confidence":0.9}],"events":[{"label":"卫图觉醒命格","evidence":["卫图觉醒命格。"],"confidence":0.9}],"relations":[],"conflicts":[],"foreshadowing":[],"worldbuilding_facts":[]}',
            '{"retained_items":[{"label":"卫图觉醒命格","evidence":["卫图觉醒命格。"],"confidence":0.9}],"unsupported_items":[],"coverage_summary":"ok"}',
            '{"summary":{"one_sentence":"卫图觉醒命格。","short":"卫图觉醒命格。","detailed":"卫图觉醒命格。"},"themes":[],"pacing":{},"emotional_curve":{},"continuity_notes":["主线开启"]}',
            '{"unsupported_inferences":[],"ambiguous_points":[],"overclaim_flags":[],"needs_human_review":false}',
        ])

        def _fake_invoke(_model, _prompt):
            return AIMessage(content=next(responses))

        service._invoke_with_retry = _fake_invoke  # type: ignore[method-assign]
        service.analyze_range(run.id, branch.id, 1, 1)

        joined = '\n'.join(captured)
        assert ('上一章摘要' * 200) not in joined
        assert '…' in joined
        assert len(joined) < 12000
