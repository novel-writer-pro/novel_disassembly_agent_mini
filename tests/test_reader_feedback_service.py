from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.session import create_schema
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.reader_feedback_service import ReaderFeedbackService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_reader_feedback_service_imports_and_summarizes(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session).create_run(novel.id, manifest.id)
        service = ReaderFeedbackService(session)
        payload = service.import_comments(branch.id, [
            {'chapter_index': 1, 'comment_text': '这章节奏有点慢，但我还是想继续看。', 'source': 'app'},
            {'chapter_index': 2, 'comment_text': '角色反应有点突兀，逻辑不太顺。', 'source': 'app'},
        ])
        assert payload['created_count'] == 2
        summary = service.summarize_branch_feedback(branch.id)
        assert summary['contract_version'] == 'reader-feedback-summary.v1'
        assert summary['comment_count'] == 2
        assert summary['signals']
        assert summary['pain_point_hypotheses']
        assert summary['revision_recommendations']
