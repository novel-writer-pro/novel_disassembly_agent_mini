from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.session import create_schema
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.run_service import RunService
from novel_analyzer.services.status_service import StatusService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_run_status_reports_progress_and_counts(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n第2章 二\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        artifact = RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '一',
                'chapter_summary': '卫图觉醒命格。',
                'key_entities': ['卫图', '命格'],
                'key_events': ['卫图觉醒命格'],
                'continuity_notes': ['主线开启。'],
                'writer_learning_notes': [],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': False,
                'dimensions': [],
            },
        )
        RetrievalService(session).materialize_for_artifact(artifact.id)
        FactService(session).materialize_for_artifact(artifact.id)
        GraphService(session).materialize_for_artifact(artifact.id)
        status = StatusService(session).get_run_status(run.id, branch.id)
        assert status.completed_chapters == 1
        assert status.next_chapter == 2
        assert status.fact_count > 0
        assert status.graph_node_count > 0
