from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.session import create_schema
from novel_analyzer.services.consistency_service import ConsistencyService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.repair_service import RepairService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_validate_branch_reports_missing_materializations(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '第1章',
                'chapter_summary': '摘要',
                'key_entities': [],
                'key_events': [],
                'continuity_notes': [],
                'writer_learning_notes': [],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': False,
                'quality_gate_notes': [],
                'hook_score': 4.0,
                'dimensions': [],
            },
            source_kind='demo',
        )
        report = ConsistencyService(session).validate_branch(branch.id)
        assert report.issue_count > 0
        assert any(issue.code == 'missing_retrieval' for issue in report.issues)
        assert not any(issue.code == 'missing_facts' for issue in report.issues)


def test_repair_branch_backfills_jobs_and_materializations(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '第1章',
                'chapter_summary': '摘要',
                'key_entities': [],
                'key_events': [],
                'continuity_notes': [],
                'writer_learning_notes': [],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': False,
                'quality_gate_notes': [],
                'hook_score': 4.0,
                'dimensions': [],
            },
            source_kind='demo',
        )
        before = ConsistencyService(session).validate_branch(branch.id)
        assert before.issue_count > 0
        report = RepairService(session).repair_branch(branch.id)
        assert report.ensured_jobs >= 1
        after = ConsistencyService(session).validate_branch(branch.id)
        assert after.issue_count == 0
