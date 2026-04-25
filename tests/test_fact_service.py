from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import FactRecord, WindowArtifact
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def _payload(chapter_index: int) -> dict[str, object]:
    return {
        'chapter_index': chapter_index,
        'normalized_title': f'第{chapter_index}章',
        'chapter_summary': f'第{chapter_index}章摘要',
        'key_entities': ['卫图', '养生功'],
        'key_events': [f'第{chapter_index}章事件'],
        'continuity_notes': [f'第{chapter_index}章衔接'],
        'writer_learning_notes': [],
        'unsupported_inferences': [],
        'ambiguous_points': [],
        'needs_human_review': False,
        'quality_gate_notes': [],
        'hook_score': 4.5,
        'dimensions': [],
    }


def test_fact_materialization_creates_fact_rows(tmp_path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        artifact = RunService(session).record_chapter_artifact(branch.id, 1, _payload(1))
        rows = FactService(session).materialize_for_artifact(artifact.id)
        assert rows
        stored = session.scalars(select(FactRecord).where(FactRecord.branch_id == branch.id)).all()
        assert stored


def test_fact_listing_and_window_materialization(tmp_path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        service = FactService(session)
        for idx in range(1, 6):
            artifact = RunService(session).record_chapter_artifact(branch.id, idx, _payload(idx))
            service.materialize_for_artifact(artifact.id)
            window = service.materialize_window_if_ready(branch.id, idx, 5)
        facts = service.list_facts(branch.id, chapter_index=1)
        assert facts
        assert window is not None
        stored = session.scalar(select(WindowArtifact).where(WindowArtifact.branch_id == branch.id))
        assert stored is not None
        assert stored.payload_json['window_start_chapter'] == 1
        assert stored.payload_json['window_end_chapter'] == 5
