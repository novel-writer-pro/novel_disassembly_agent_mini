from __future__ import annotations

import json
from pathlib import Path

from scripts.export_deconstruction_benchmark_bundle import main as export_main


def test_export_benchmark_bundle_writes_all_outputs(tmp_path: Path, monkeypatch, capsys) -> None:
    baseline = {
        'run_id': 'base',
        'completed_chapters': 20,
        'failed_jobs': 0,
        'elapsed_seconds': 1000.0,
        'avg_seconds_per_completed_chapter': 50.0,
        'prompt_char_totals': {},
    }
    candidate = {
        'run_id': 'cand',
        'completed_chapters': 20,
        'failed_jobs': 0,
        'elapsed_seconds': 800.0,
        'avg_seconds_per_completed_chapter': 40.0,
        'prompt_char_totals': {},
    }
    base = tmp_path / 'baseline.json'
    cand = tmp_path / 'candidate.json'
    out = tmp_path / 'bundle'
    base.write_text(json.dumps(baseline, ensure_ascii=False), encoding='utf-8')
    cand.write_text(json.dumps(candidate, ensure_ascii=False), encoding='utf-8')

    def fake_run(cmd, check, capture_output, text):
        class _Done:
            stdout = json.dumps({
                'baseline_run_id': 'base',
                'candidate_run_id': 'cand',
                'completed_chapters': {'baseline': 20, 'candidate': 20},
                'failed_jobs': {'baseline': 0, 'candidate': 0, 'delta': 0},
                'elapsed_seconds': {'baseline': 1000.0, 'candidate': 800.0, 'delta': -200.0, 'delta_pct': -20.0},
                'avg_seconds_per_completed_chapter': {'baseline': 50.0, 'candidate': 40.0, 'delta': -10.0, 'delta_pct': -20.0},
                'prompt_char_totals': {},
            })
        return _Done()

    monkeypatch.setattr('subprocess.run', fake_run)

    import sys
    argv = sys.argv[:]
    sys.argv = ['export_deconstruction_benchmark_bundle.py', str(base), str(cand), str(out)]
    try:
        assert export_main() == 0
    finally:
        sys.argv = argv
    assert (out / 'baseline.json').exists()
    assert (out / 'candidate.json').exists()
    assert (out / 'compare.json').exists()
    assert (out / 'summary.md').exists()
    summary = (out / 'summary.md').read_text(encoding='utf-8')
    assert 'elapsed_seconds.delta_pct' in summary
