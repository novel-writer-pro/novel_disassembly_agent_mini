from __future__ import annotations

import json
from pathlib import Path

from scripts.compare_deconstruction_benchmarks import main as compare_main


def test_compare_benchmarks_json_output(tmp_path: Path, capsys) -> None:
    baseline = {
        'run_id': 'run-base',
        'completed_chapters': 20,
        'failed_jobs': 1,
        'elapsed_seconds': 1000.0,
        'avg_seconds_per_completed_chapter': 50.0,
        'prompt_char_totals': {
            'fact_extractor_chars': 2000,
            'analysis_generator_chars': 1000,
        },
    }
    candidate = {
        'run_id': 'run-new',
        'completed_chapters': 20,
        'failed_jobs': 0,
        'elapsed_seconds': 800.0,
        'avg_seconds_per_completed_chapter': 40.0,
        'prompt_char_totals': {
            'fact_extractor_chars': 1500,
            'analysis_generator_chars': 900,
        },
    }
    base_path = tmp_path / 'baseline.json'
    cand_path = tmp_path / 'candidate.json'
    base_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding='utf-8')
    cand_path.write_text(json.dumps(candidate, ensure_ascii=False), encoding='utf-8')

    import sys
    argv = sys.argv[:]
    sys.argv = ['compare_deconstruction_benchmarks.py', str(base_path), str(cand_path), '--json']
    try:
        assert compare_main() == 0
    finally:
        sys.argv = argv
    payload = json.loads(capsys.readouterr().out)
    assert payload['failed_jobs']['delta'] == -1
    assert payload['elapsed_seconds']['delta'] == -200.0
    assert payload['avg_seconds_per_completed_chapter']['delta'] == -10.0
    assert payload['prompt_char_totals']['fact_extractor_chars']['delta'] == -500


def test_compare_benchmarks_plain_output(tmp_path: Path, capsys) -> None:
    baseline = {
        'run_id': 'run-base',
        'completed_chapters': 20,
        'failed_jobs': 0,
        'elapsed_seconds': 1000.0,
        'avg_seconds_per_completed_chapter': 50.0,
        'prompt_char_totals': {},
    }
    candidate = {
        'run_id': 'run-new',
        'completed_chapters': 20,
        'failed_jobs': 0,
        'elapsed_seconds': 1100.0,
        'avg_seconds_per_completed_chapter': 55.0,
        'prompt_char_totals': {},
    }
    base_path = tmp_path / 'baseline.json'
    cand_path = tmp_path / 'candidate.json'
    base_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding='utf-8')
    cand_path.write_text(json.dumps(candidate, ensure_ascii=False), encoding='utf-8')

    import sys
    argv = sys.argv[:]
    sys.argv = ['compare_deconstruction_benchmarks.py', str(base_path), str(cand_path)]
    try:
        assert compare_main() == 0
    finally:
        sys.argv = argv
    out = capsys.readouterr().out
    assert 'baseline_run_id=run-base' in out
    assert 'candidate_run_id=run-new' in out
    assert 'elapsed_delta_seconds=100.0' in out
