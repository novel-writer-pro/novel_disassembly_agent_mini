from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.session import create_schema
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.package_service import PackageService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_export_branch_package_writes_expected_files(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        artifact = RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '命格初现',
                'chapter_summary': '卫图觉醒命格。',
                'key_entities': ['卫图', '命格'],
                'key_events': ['卫图觉醒命格'],
                'continuity_notes': ['主线推进。'],
                'writer_learning_notes': [],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': False,
                'quality_gate_notes': [],
                'hook_score': 4.0,
                'dimensions': [],
            },
        )
        RetrievalService(session).materialize_for_artifact(artifact.id)
        FactService(session).materialize_for_artifact(artifact.id)
        GraphService(session).materialize_for_artifact(artifact.id)
        output_dir = tmp_path / 'pkg'
        PackageService(session).export_branch_package(run.id, branch.id, output_dir)
        assert (output_dir / 'branch_bundle.json').exists()
        assert (output_dir / 'branch_report.md').exists()
        assert (output_dir / 'chapter_index.json').exists()
        assert (output_dir / 'chapters' / 'chapter_0001.json').exists()
        assert (output_dir / 'chapters' / 'chapter_0001.md').exists()
        assert (output_dir / 'chapters' / 'chapter_0001.raw.json').exists()
        assert (output_dir / 'chapters' / 'chapter_0001.context.json').exists()
