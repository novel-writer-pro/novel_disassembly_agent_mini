from pathlib import Path
import json

from _pytest.monkeypatch import MonkeyPatch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typer.testing import CliRunner

from novel_analyzer.cli.app import app
from novel_analyzer.runtime.cluster_review_state import write_cluster_review_state
from tests.cli_test_support import patch_cli_sqlite_runtime
from novel_analyzer.services.retrieval_service import RetrievalHit, RetrievalRouteDiagnostics, RetrievalSearchDiagnostics

runner = CliRunner()


def test_export_markdown_cli(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    _engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    runner.invoke(app, ['init-db', '--database-url', db_url])
    ingest = runner.invoke(app, ['ingest', str(novel_path), '--database-url', db_url])
    lines = dict(line.split('=', 1) for line in ingest.stdout.strip().splitlines())
    start = runner.invoke(
        app,
        ['start-run', lines['novel_id'], lines['manifest_id'], '--database-url', db_url],
    )
    run_lines = dict(line.split('=', 1) for line in start.stdout.strip().splitlines())
    runner.invoke(app, ['commit-demo', run_lines['branch_id'], '1', '--database-url', db_url])
    out = tmp_path / 'chapter1.md'
    result = runner.invoke(
        app,
        ['export-markdown', run_lines['branch_id'], '1', str(out), '--database-url', db_url],
    )
    assert result.exit_code == 0
    assert out.exists()


def test_export_qa_context_cli(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    _engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    runner.invoke(app, ['init-db', '--database-url', db_url])
    ingest = runner.invoke(app, ['ingest', str(novel_path), '--database-url', db_url])
    lines = dict(line.split('=', 1) for line in ingest.stdout.strip().splitlines())
    start = runner.invoke(
        app,
        ['start-run', lines['novel_id'], lines['manifest_id'], '--database-url', db_url],
    )
    run_lines = dict(line.split('=', 1) for line in start.stdout.strip().splitlines())
    runner.invoke(app, ['commit-demo', run_lines['branch_id'], '1', '--database-url', db_url])
    chapter_out = tmp_path / 'chapter1-qa.json'
    branch_out = tmp_path / 'branch-qa.json'
    chapter_result = runner.invoke(
        app,
        [
            'export-chapter-qa-context',
            run_lines['branch_id'],
            '1',
            str(chapter_out),
            '--database-url',
            db_url,
        ],
    )
    branch_result = runner.invoke(
        app,
        [
            'export-branch-qa-context',
            run_lines['run_id'],
            run_lines['branch_id'],
            str(branch_out),
            '--database-url',
            db_url,
        ],
    )
    assert chapter_result.exit_code == 0
    assert branch_result.exit_code == 0
    assert chapter_out.exists()
    assert branch_out.exists()


def test_show_cluster_history_cli_supports_filters_and_fallback(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    _engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    from novel_analyzer.config.settings import get_settings

    settings = get_settings().model_copy(deep=True)
    settings.runtime_cache_dir = str(tmp_path / "runtime-cache")
    monkeypatch.setattr("novel_analyzer.cli.app.get_settings", lambda: settings)
    fallback_engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    fallback_factory = sessionmaker(bind=fallback_engine, future=True)
    monkeypatch.setattr(
        "novel_analyzer.cli.app.create_session_factory",
        lambda settings=None: fallback_factory,
    )

    write_cluster_review_state(
        "branch-x",
        "cluster-y",
        "needs_review",
        review_result="deferred",
        review_notes="待处理",
        review_owner="editor-a",
        review_actor="editor-a",
        settings=settings,
    )
    write_cluster_review_state(
        "branch-x",
        "cluster-y",
        "needs_review",
        review_result="deferred",
        review_notes="待处理",
        review_owner="editor-b",
        review_actor="review-bot",
        settings=settings,
    )

    result = runner.invoke(
        app,
        [
            "show-cluster-history",
            "branch-x",
            "cluster-y",
            "--event-type",
            "assignment_update",
            "--review-owner",
            "editor-b",
            "--review-result",
            "deferred",
            "--limit",
            "1",
            "--database-url",
            db_url,
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload) == 1
    assert payload[0]["event_type"] == "assignment_update"
    assert payload[0]["review_owner"] == "editor-b"
    assert payload[0]["review_actor"] == "review-bot"


def test_author_knowledge_cli(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    _engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    runner.invoke(app, ['init-db', '--database-url', db_url])
    ingest = runner.invoke(app, ['ingest', str(novel_path), '--database-url', db_url])
    lines = dict(line.split('=', 1) for line in ingest.stdout.strip().splitlines())
    start = runner.invoke(
        app,
        ['start-run', lines['novel_id'], lines['manifest_id'], '--database-url', db_url],
    )
    run_lines = dict(line.split('=', 1) for line in start.stdout.strip().splitlines())

    runner.invoke(app, ['commit-demo', run_lines['branch_id'], '1', '--database-url', db_url])
    out = tmp_path / 'author-knowledge.json'
    export_result = runner.invoke(
        app,
        ['export-author-knowledge', run_lines['branch_id'], str(out), '--database-url', db_url],
    )
    show_result = runner.invoke(
        app,
        ['show-author-knowledge', run_lines['branch_id'], '--database-url', db_url],
    )

    assert export_result.exit_code == 0
    assert show_result.exit_code == 0
    payload = json.loads(out.read_text(encoding='utf-8'))
    assert payload['contract_version'] == 'author-knowledge.v1'
    assert 'chapter_cards' in payload
    assert 'knowledge_index' in payload
    assert 'entity_profiles' in payload
    assert 'relationship_index' in payload
    assert 'rule_index' in payload
    assert 'thread_index' in payload
    assert 'summary_layer' in payload
    assert 'recommended_questions' in payload

    focused_out = tmp_path / 'author-knowledge-focused.json'
    focused_result = runner.invoke(
        app,
        [
            'export-author-knowledge',
            run_lines['branch_id'],
            str(focused_out),
            '--from-chapter-index',
            '1',
            '--upto-chapter-index',
            '1',
            '--focus-label',
            'chapter',
            '--database-url',
            db_url,
        ],
    )
    assert focused_result.exit_code == 0


def test_search_branch_diagnostics_cli(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    _engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    runner.invoke(app, ['init-db', '--database-url', db_url])
    ingest = runner.invoke(app, ['ingest', str(novel_path), '--database-url', db_url])
    lines = dict(line.split('=', 1) for line in ingest.stdout.strip().splitlines())
    start = runner.invoke(
        app,
        ['start-run', lines['novel_id'], lines['manifest_id'], '--database-url', db_url],
    )
    run_lines = dict(line.split('=', 1) for line in start.stdout.strip().splitlines())

    class _FakeRetrievalService:
        def search_branch_with_diagnostics(self, branch_id: str, query: str, limit: int) -> RetrievalSearchDiagnostics:
            _ = branch_id, query, limit
            return RetrievalSearchDiagnostics(
                query='卫图',
                raw_hits=[RetrievalHit(chapter_index=1, title='命格初现', summary_text='卫图觉醒命格', score=1.2, keyword_list=['卫图'])],
                reranked_hits=[RetrievalHit(chapter_index=1, title='命格初现', summary_text='卫图觉醒命格', score=0.9, keyword_list=['卫图'])],
                rerank_applied=True,
                fusion_applied=True,
                route_counts={'entity_exact': 1, 'vector': 1},
                route_diagnostics=[RetrievalRouteDiagnostics(route='entity_exact', hit_count=1, latency_ms=1.5)],
                raw_latency_ms=3.0,
                rerank_latency_ms=8.0,
            )

    monkeypatch.setattr('novel_analyzer.cli.app._retrieval_service', lambda session, settings: _FakeRetrievalService())
    result = runner.invoke(
        app,
        ['search-branch-diagnostics', run_lines['branch_id'], '卫图', '--database-url', db_url],
    )
    assert result.exit_code == 0
    assert 'query=卫图' in result.stdout
    assert 'fusion_applied=True' in result.stdout
    assert 'rerank_applied=True' in result.stdout
    assert 'route=entity_exact' in result.stdout
    assert 'raw_hit=chapter_index=1' in result.stdout


def test_export_search_branch_diagnostics_cli(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    _engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    runner.invoke(app, ['init-db', '--database-url', db_url])
    ingest = runner.invoke(app, ['ingest', str(novel_path), '--database-url', db_url])
    lines = dict(line.split('=', 1) for line in ingest.stdout.strip().splitlines())
    start = runner.invoke(
        app,
        ['start-run', lines['novel_id'], lines['manifest_id'], '--database-url', db_url],
    )
    run_lines = dict(line.split('=', 1) for line in start.stdout.strip().splitlines())

    class _FakeRetrievalService:
        def search_branch_with_diagnostics(self, branch_id: str, query: str, limit: int) -> RetrievalSearchDiagnostics:
            _ = branch_id, query, limit
            return RetrievalSearchDiagnostics(
                query='卫图',
                raw_hits=[RetrievalHit(chapter_index=1, title='命格初现', summary_text='卫图觉醒命格', score=1.2, keyword_list=['卫图'])],
                reranked_hits=[RetrievalHit(chapter_index=1, title='命格初现', summary_text='卫图觉醒命格', score=0.9, keyword_list=['卫图'])],
                rerank_applied=True,
                fusion_applied=True,
                route_counts={'entity_exact': 1},
                route_diagnostics=[RetrievalRouteDiagnostics(route='entity_exact', hit_count=1, latency_ms=1.5)],
                raw_latency_ms=3.0,
                rerank_latency_ms=8.0,
            )

    monkeypatch.setattr('novel_analyzer.cli.app._retrieval_service', lambda session, settings: _FakeRetrievalService())
    out = tmp_path / 'search-diagnostics.json'
    result = runner.invoke(
        app,
        ['export-search-branch-diagnostics', run_lines['branch_id'], '卫图', str(out), '--database-url', db_url],
    )
    assert result.exit_code == 0
    payload = json.loads(out.read_text(encoding='utf-8'))
    assert payload['query'] == '卫图'
    assert payload['route_counts']['entity_exact'] == 1
    assert payload['rerank_applied'] is True
