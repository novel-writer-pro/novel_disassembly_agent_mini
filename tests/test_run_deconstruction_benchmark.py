from __future__ import annotations

import json
from pathlib import Path

from scripts.run_deconstruction_benchmark import main as run_main


def test_run_deconstruction_benchmark_orchestrates_cli(monkeypatch, tmp_path: Path, capsys) -> None:
    novel = tmp_path / 'novel.txt'
    novel.write_text('第1章 一\n正文\n', encoding='utf-8')

    calls: list[list[str]] = []

    def fake_run(cmd, check, capture_output, text, env=None):
        calls.append(cmd)
        class _Done:
            def __init__(self, stdout: str):
                self.stdout = stdout
        if 'ingest' in cmd:
            return _Done('novel_id=n1\nmanifest_id=m1\nchapter_count=1\n')
        if 'start-run' in cmd:
            return _Done('run_id=r1\nbranch_id=b1\nactive_branch_id=b1\n')
        if 'analyze-range' in cmd:
            return _Done('artifact_count=1\nartifact_id=a1\n')
        if any('benchmark_deconstruction_run.py' in part for part in cmd):
            return _Done(json.dumps({
                'run_id': 'r1',
                'branch_id': 'b1',
                'completed_chapters': 1,
                'failed_jobs': 0,
                'elapsed_seconds': 12.0,
                'avg_seconds_per_completed_chapter': 12.0,
                'prompt_char_totals': {},
                'per_chapter': [],
            }))
        if 'init-db' in cmd:
            return _Done('initialized database\n')
        raise AssertionError(cmd)

    monkeypatch.setattr('subprocess.run', fake_run)

    import sys
    argv = sys.argv[:]
    sys.argv = [
        'run_deconstruction_benchmark.py',
        str(novel),
        '--title', '样例',
        '--database-url', 'postgresql+psycopg://x:y@127.0.0.1:5432/db',
        '--end-chapter', '1',
        '--ensure-db',
        '--json',
    ]
    try:
        assert run_main() == 0
    finally:
        sys.argv = argv
    payload = json.loads(capsys.readouterr().out)
    assert payload['novel_id'] == 'n1'
    assert payload['manifest_id'] == 'm1'
    assert payload['completed_chapters'] == 1
    assert any('ingest' in cmd for cmd in calls)
    assert any('start-run' in cmd for cmd in calls)
    assert any('analyze-range' in cmd for cmd in calls)
    assert any(any('benchmark_deconstruction_run.py' in part for part in cmd) for cmd in calls)
