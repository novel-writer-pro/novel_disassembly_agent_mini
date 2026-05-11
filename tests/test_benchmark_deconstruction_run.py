from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.session import create_schema
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.run_service import RunService
from scripts.benchmark_deconstruction_run import main as benchmark_main


def _seed_run(tmp_path: Path, *, with_prompt_metrics: bool) -> tuple[str, str, str]:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    dburl = 'sqlite+pysqlite:///:memory:'
    # main() needs a DB URL, so we persist to a temp sqlite file instead.
    sqlite_path = tmp_path / ('bench_metrics.db' if with_prompt_metrics else 'bench_plain.db')
    file_url = f'sqlite+pysqlite:///{sqlite_path}'
    engine = create_engine(file_url, future=True)
    create_schema(engine)
    with Session(engine) as session:
        novel_path = tmp_path / ('novel_metrics.txt' if with_prompt_metrics else 'novel_plain.txt')
        novel_path.write_text('第1章 一\n正文\n第2章 二\n正文\n', encoding='utf-8')
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        service = RunService(session)
        for idx in (1, 2):
            job = service.start_chapter_job(branch.id, idx)
            service.record_raw_output(
                run.id,
                branch.id,
                idx,
                job.attempts,
                '{"ok":true}',
                parsed_json=(
                    {'ok': True, '_deconstruction_profile': {'timing': {'fallback_mode': 'local-heuristic'}}}
                    if with_prompt_metrics and idx == 2
                    else {'ok': True}
                ),
                parse_status='parsed',
                parse_error=None,
                invocation_metadata=(
                    {
                        'pipeline': 'small-model-skills-v1',
                        'model_name': 'demo',
                        'prompt_char_counts': {
                            'chapter_intake_chars': 10 * idx,
                            'fact_extractor_chars': 20 * idx,
                        },
                        'total_prompt_chars': 30 * idx,
                    }
                    if with_prompt_metrics
                    else {
                        'pipeline': 'small-model-skills-v1',
                        'model_name': 'demo',
                    }
                ),
            )
            service.record_chapter_artifact(branch.id, idx, {'chapter_index': idx, 'chapter_summary': f'第{idx}章摘要', '_deconstruction_profile': {'timing': ({'fallback_mode': 'local-heuristic'} if with_prompt_metrics and idx == 2 else {})}})
            service.complete_chapter_job(branch.id, idx)
        return file_url, run.id, branch.id


def test_benchmark_cli_summarizes_prompt_metrics(tmp_path: Path, capsys) -> None:
    dburl, run_id, branch_id = _seed_run(tmp_path, with_prompt_metrics=True)
    import sys
    argv = sys.argv[:]
    sys.argv = ['benchmark_deconstruction_run.py', run_id, branch_id, '--database-url', dburl, '--json']
    try:
        assert benchmark_main() == 0
    finally:
        sys.argv = argv
    payload = json.loads(capsys.readouterr().out)
    assert payload['completed_chapters'] == 2
    assert payload['failed_jobs'] == 0
    assert payload['prompt_char_totals']['chapter_intake_chars'] == 30
    assert payload['prompt_char_totals']['fact_extractor_chars'] == 60
    assert payload['per_chapter'][0]['total_prompt_chars'] == 30
    assert payload['fallback_modes']['local-heuristic'] == 1
    assert payload['fallback_chapter_count'] == 1
    assert payload['is_pure_primary_provider_run'] is False


def test_benchmark_cli_handles_runs_without_prompt_metrics(tmp_path: Path, capsys) -> None:
    dburl, run_id, branch_id = _seed_run(tmp_path, with_prompt_metrics=False)
    import sys
    argv = sys.argv[:]
    sys.argv = ['benchmark_deconstruction_run.py', run_id, branch_id, '--database-url', dburl, '--json']
    try:
        assert benchmark_main() == 0
    finally:
        sys.argv = argv
    payload = json.loads(capsys.readouterr().out)
    assert payload['completed_chapters'] == 2
    assert payload['prompt_char_totals'] == {}
    assert payload['per_chapter'][0]['prompt_char_counts'] == {}
    assert payload['fallback_modes'] == {}
    assert payload['fallback_chapter_count'] == 0
    assert payload['is_pure_primary_provider_run'] is True
