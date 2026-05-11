from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings
from novel_analyzer.database.models import ChapterArtifact, ChapterRawOutput
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.analysis_service import AnalysisService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.run_service import RunService


class _DummyModel:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._index = 0

    def invoke(self, _prompt: str):
        from langchain_core.messages import AIMessage

        content = self._responses[self._index]
        self._index += 1
        return AIMessage(content=content)


INTAKE_OK = (
    '{"chapter_index":1,"normalized_title":"一","cleaned_text":"第1章 一\\n卫图觉醒命格。",'
    '"paragraph_blocks":[{"order":1,"text":"第1章 一"}],"notes":[]}'
)
FACTS_EMPTY = (
    '{"characters":[],"events":[],"relations":[],"conflicts":[],'
    '"foreshadowing":[],"worldbuilding_facts":[]}'
)
EVIDENCE_EMPTY = '{"retained_items":[],"unsupported_items":[],"coverage_summary":"空"}'
ANALYSIS_SPARSE = (
    '{"summary":{"one_sentence":"","short":"","detailed":""},"themes":[],'
    '"pacing":{},"emotional_curve":{},"continuity_notes":[]}'
)
GUARD_EMPTY = (
    '{"unsupported_inferences":[],"ambiguous_points":[],'
    '"overclaim_flags":[],"needs_human_review":false}'
)
WRITER_EMPTY = (
    '{"hook_notes":[],"conflict_notes":[],"reveal_order_notes":[],'
    '"scene_efficiency_notes":[],"transferable_lessons":[]}'
)
MONOLITHIC_SUCCESS = (
    '{"chapter_index":1,"normalized_title":"一","dimensions":[],'
    '"chapter_summary":"卫图觉醒命格。","key_entities":["卫图"],'
    '"key_events":["觉醒命格"],"continuity_notes":["主线开启"],'
    '"writer_learning_notes":[],"unsupported_inferences":[],"ambiguous_points":[],'
    '"needs_human_review":false}'
)


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_stage_failure_falls_back_to_monolithic_and_persists_result(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n卫图觉醒命格。\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)

        service = AnalysisService(session, Settings(llm_api_key='test-key'))
        dummy_model = _DummyModel(
            [
                INTAKE_OK,
                FACTS_EMPTY,
                EVIDENCE_EMPTY,
                ANALYSIS_SPARSE,
                WRITER_EMPTY,
                GUARD_EMPTY,
                MONOLITHIC_SUCCESS,
            ]
        )
        service._invoke_with_retry = lambda _model, _prompt: dummy_model.invoke(_prompt)  # type: ignore[method-assign]
        service.analyze_range(run.id, branch.id, 1, 1)

        artifact = session.scalar(
            select(ChapterArtifact).where(ChapterArtifact.branch_id == branch.id)
        )
        assert artifact is not None
        assert artifact.payload_json['chapter_summary'].startswith('本章围绕')

        raw_output = session.scalar(
            select(ChapterRawOutput).where(ChapterRawOutput.branch_id == branch.id)
        )
        assert raw_output is not None
        assert raw_output.parse_status == 'parsed'
        assert raw_output.parsed_json is not None


def test_recorded_raw_output_includes_prompt_metrics(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n卫图觉醒命格。\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)

        service = AnalysisService(session, Settings(llm_api_key='test-key'))
        dummy_model = _DummyModel(
            [
                INTAKE_OK,
                FACTS_EMPTY,
                EVIDENCE_EMPTY,
                '{"summary":{"one_sentence":"卫图觉醒命格。","short":"卫图觉醒命格。","detailed":"卫图觉醒命格。"},"themes":[],"pacing":{},"emotional_curve":{},"continuity_notes":["主线开启"]}',
                GUARD_EMPTY,
            ]
        )
        service._invoke_with_retry = lambda _model, _prompt: dummy_model.invoke(_prompt)  # type: ignore[method-assign]
        service.analyze_range(run.id, branch.id, 1, 1)

        raw_output = session.scalar(
            select(ChapterRawOutput).where(ChapterRawOutput.branch_id == branch.id)
        )
        assert raw_output is not None
        meta = raw_output.invocation_metadata
        assert meta.get('pipeline') == 'small-model-skills-v1'
        assert isinstance(meta.get('prompt_char_counts'), dict)
        assert meta.get('total_prompt_chars', 0) > 0
        assert 'chapter_intake_chars' in meta['prompt_char_counts']
        assert 'fact_extractor_chars' in meta['prompt_char_counts']
        assert 'analysis_generator_chars' in meta['prompt_char_counts']
