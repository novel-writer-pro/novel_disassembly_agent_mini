from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.session import create_schema
from novel_analyzer.services.context_service import ContextService
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_context_service_exposes_prior_summary_facts_window_and_graph(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        fact_service = FactService(session)
        graph_service = GraphService(session)
        for idx in range(1, 6):
            artifact = RunService(session).record_chapter_artifact(
                branch.id,
                idx,
                {
                    'chapter_index': idx,
                    'normalized_title': f'第{idx}章',
                    'chapter_summary': f'第{idx}章摘要',
                    'key_entities': ['卫图', '养生功'],
                    'key_events': [f'第{idx}章事件'],
                    'continuity_notes': [f'第{idx}章衔接'],
                    'writer_learning_notes': [],
                    'unsupported_inferences': [],
                    'ambiguous_points': [],
                    'needs_human_review': False,
                    'quality_gate_notes': [],
                    'hook_score': 4.5,
                    'dimensions': [],
                },
            )
            fact_service.materialize_for_artifact(artifact.id)
            graph_service.materialize_for_artifact(artifact.id)
            fact_service.materialize_window_if_ready(branch.id, idx, 5)
        service = ContextService(session)
        bundle = service.context_bundle(branch.id, 6)
        assert bundle['previous_summary'] == '第5章摘要'
        assert bundle['fact_context']['facts']
        assert bundle['window_summary']
        assert bundle['graph_context']['nodes']
        assert 'overview' in bundle['graph_context']
        assert 'state_summary' in bundle


def test_previous_summary_ignores_non_downstream_active_companion(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n第2章 二\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        run_service = RunService(session)
        run_service.record_chapter_artifact(
            branch.id,
            1,
            {'chapter_summary': 'canonical summary'},
        )
        run_service.record_chapter_artifact(
            branch.id,
            1,
            {'chapter_summary': 'companion summary'},
            source_kind='manual',
            participates_in_downstream=False,
        )

        assert ContextService(session).previous_summary(branch.id, 2) == 'canonical summary'
