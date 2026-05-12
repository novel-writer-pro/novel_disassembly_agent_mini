from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings
from novel_analyzer.database.models import FactRecord, GraphNode, RunBranch
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.domain_dictionary_service import DomainDictionaryService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def _branch(session: Session, tmp_path) -> RunBranch:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
    _, branch = RunService(session).create_run(novel.id, manifest.id)
    return branch


def _settings(tmp_path) -> Settings:
    return Settings(runtime_cache_dir=str(tmp_path / 'cache'))


def test_update_from_chapter_writes_plain_and_jieba_dict(tmp_path) -> None:
    settings = _settings(tmp_path)
    with _session() as session:
        branch = _branch(session, tmp_path)
        session.add_all([
            FactRecord(
                branch_id=branch.id,
                chapter_index=1,
                fact_type='entity',
                label='卫图',
                evidence_list=[],
                confidence=0.9,
            ),
            FactRecord(
                branch_id=branch.id,
                chapter_index=1,
                fact_type='event',
                label='修炼养生功',
                evidence_list=[],
                confidence=0.8,
            ),
        ])
        session.flush()

        service = DomainDictionaryService(session, settings)
        added = service.update_from_chapter(branch.id, 1)
        assert added >= 2

    plain_path = tmp_path / 'cache' / 'domain-dict.txt'
    jieba_path = tmp_path / 'cache' / 'jieba-user-dict.txt'
    assert plain_path.exists()
    assert jieba_path.exists()

    plain_terms = {line for line in plain_path.read_text(encoding='utf-8').splitlines() if line}
    assert '卫图' in plain_terms
    assert '修炼养生功' in plain_terms

    jieba_lines = [line for line in jieba_path.read_text(encoding='utf-8').splitlines() if line]
    assert len(jieba_lines) == len(plain_terms)
    for line in jieba_lines:
        parts = line.split()
        assert len(parts) == 3
        assert parts[1].isdigit() and int(parts[1]) >= 50
        assert parts[2] == 'n'

    jieba_terms = {line.split()[0] for line in jieba_lines}
    assert jieba_terms == plain_terms


def test_update_from_branch_rewrites_both_files(tmp_path) -> None:
    settings = _settings(tmp_path)
    with _session() as session:
        branch = _branch(session, tmp_path)
        session.add_all([
            GraphNode(
                branch_id=branch.id,
                node_type='character',
                label='卫图',
                chapter_first_seen=1,
                chapter_last_seen=1,
            ),
            FactRecord(
                branch_id=branch.id,
                chapter_index=2,
                fact_type='foreshadowing',
                label='丹火秘阵',
                evidence_list=[],
                confidence=0.7,
            ),
        ])
        session.flush()

        service = DomainDictionaryService(session, settings)
        added = service.update_from_branch(branch.id)
        assert added >= 2

    plain_terms = set((tmp_path / 'cache' / 'domain-dict.txt').read_text(encoding='utf-8').split())
    jieba_terms = {
        line.split()[0]
        for line in (tmp_path / 'cache' / 'jieba-user-dict.txt').read_text(encoding='utf-8').splitlines()
        if line.strip()
    }
    assert '卫图' in plain_terms
    assert '丹火秘阵' in plain_terms
    assert plain_terms == jieba_terms


def test_get_terms_unaffected_by_jieba_file(tmp_path) -> None:
    settings = _settings(tmp_path)
    with _session() as session:
        branch = _branch(session, tmp_path)
        session.add(
            FactRecord(
                branch_id=branch.id,
                chapter_index=1,
                fact_type='entity',
                label='卫图',
                evidence_list=[],
                confidence=0.9,
            )
        )
        session.flush()
        service = DomainDictionaryService(session, settings)
        service.update_from_chapter(branch.id, 1)
        assert '卫图' in service.get_terms()
