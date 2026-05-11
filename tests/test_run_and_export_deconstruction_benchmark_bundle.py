from __future__ import annotations

from pathlib import Path

from scripts.run_and_export_deconstruction_benchmark_bundle import main as bundle_main


def test_run_and_export_bundle_orchestrates_benchmark_and_export(monkeypatch, tmp_path: Path, capsys) -> None:
    novel = tmp_path / 'novel.txt'
    novel.write_text('第1章 一\n正文\n', encoding='utf-8')
    baseline = tmp_path / 'baseline.json'
    baseline.write_text('{"run_id":"base"}', encoding='utf-8')
    out_dir = tmp_path / 'bundle'

    calls: list[list[str]] = []

    def fake_run(cmd, check, capture_output, text):
        calls.append(cmd)
        class _Done:
            def __init__(self, stdout: str):
                self.stdout = stdout
        if any('run_deconstruction_benchmark.py' in part for part in cmd):
            return _Done('{"run_id":"cand","completed_chapters":1}')
        if any('export_deconstruction_benchmark_bundle.py' in part for part in cmd):
            return _Done(f'bundle_dir={out_dir}\ncompare_json={out_dir / "compare.json"}\nsummary_md={out_dir / "summary.md"}\n')
        raise AssertionError(cmd)

    monkeypatch.setattr('subprocess.run', fake_run)

    import sys
    argv = sys.argv[:]
    sys.argv = [
        'run_and_export_deconstruction_benchmark_bundle.py',
        str(novel),
        '--title', '样例',
        '--database-url', 'postgresql+psycopg://x:y@127.0.0.1:5432/db',
        '--baseline-json', str(baseline),
        '--output-dir', str(out_dir),
        '--end-chapter', '1',
        '--ensure-db',
    ]
    try:
        assert bundle_main() == 0
    finally:
        sys.argv = argv
    assert (out_dir / 'candidate.json').exists()
    out = capsys.readouterr().out
    assert 'bundle_dir=' in out
    assert any(any('run_deconstruction_benchmark.py' in part for part in cmd) for cmd in calls)
    assert any(any('export_deconstruction_benchmark_bundle.py' in part for part in cmd) for cmd in calls)
