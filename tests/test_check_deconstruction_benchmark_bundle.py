from __future__ import annotations

import json
from pathlib import Path

from scripts.check_deconstruction_benchmark_bundle import main as check_main


def test_check_bundle_reports_ok_for_complete_bundle(tmp_path: Path, capsys) -> None:
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    (bundle / 'baseline.json').write_text('{}', encoding='utf-8')
    (bundle / 'candidate.json').write_text('{}', encoding='utf-8')
    (bundle / 'summary.md').write_text('# summary', encoding='utf-8')
    (bundle / 'compare.json').write_text(json.dumps({
        'baseline_run_id': 'b',
        'candidate_run_id': 'c',
        'comparability': {
            'chapter_count_match': True,
            'provider_purity_match': True,
            'is_strictly_comparable': True,
            'notes': [],
        },
        'completed_chapters': {},
        'failed_jobs': {},
        'elapsed_seconds': {},
        'avg_seconds_per_completed_chapter': {},
        'prompt_char_totals': {},
    }), encoding='utf-8')

    import sys
    argv = sys.argv[:]
    sys.argv = ['check_deconstruction_benchmark_bundle.py', str(bundle), '--json']
    try:
        assert check_main() == 0
    finally:
        sys.argv = argv
    payload = json.loads(capsys.readouterr().out)
    assert payload['ok'] is True
    assert payload['missing_files'] == []


def test_check_bundle_reports_missing_compare_keys(tmp_path: Path, capsys) -> None:
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    for name in ('baseline.json', 'candidate.json', 'summary.md'):
        (bundle / name).write_text('{}', encoding='utf-8')
    (bundle / 'compare.json').write_text(json.dumps({'baseline_run_id': 'b'}), encoding='utf-8')

    import sys
    argv = sys.argv[:]
    sys.argv = ['check_deconstruction_benchmark_bundle.py', str(bundle), '--json']
    try:
        assert check_main() == 1
    finally:
        sys.argv = argv
    payload = json.loads(capsys.readouterr().out)
    assert payload['ok'] is False
    assert 'candidate_run_id' in payload['missing_compare_keys']
    assert 'chapter_count_match' in payload['missing_comparability_keys']
