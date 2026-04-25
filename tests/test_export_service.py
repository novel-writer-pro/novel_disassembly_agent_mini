from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.session import create_schema
from novel_analyzer.services.export_service import ExportService
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_export_branch_bundle_contains_status_windows_and_graph(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        retrieval = RetrievalService(session)
        facts = FactService(session)
        graph = GraphService(session)
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
            retrieval.materialize_for_artifact(artifact.id)
            facts.materialize_for_artifact(artifact.id)
            graph.materialize_for_artifact(artifact.id)
            facts.materialize_window_if_ready(branch.id, idx, 5)
        bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        assert bundle['status']['completed_chapters'] == 5
        assert bundle['windows']
        assert bundle['graph_nodes']
        assert bundle['graph_edges']
