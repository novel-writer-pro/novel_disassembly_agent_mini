from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.session import create_schema
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.raw_output_service import RawOutputService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_latest_raw_output_for_chapter_returns_most_recent_record(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_raw_output(
            run.id,
            branch.id,
            1,
            1,
            'first',
            parsed_json=None,
            parse_status='failed',
            parse_error='x',
            invocation_metadata={},
        )
        latest = RunService(session).record_raw_output(
            run.id,
            branch.id,
            1,
            2,
            'second',
            parsed_json={'ok': True},
            parse_status='parsed',
            parse_error=None,
            invocation_metadata={'model': 'gpt'},
        )
        found = RawOutputService(session).latest_for_chapter(branch.id, 1)
        assert found is not None
        assert found.id == latest.id
        assert found.raw_response_text == 'second'
