from __future__ import annotations

import json
from pathlib import Path

from scripts.check_deconstruction_benchmark_readiness import main as readiness_main


def test_readiness_reports_missing_assets_when_run_outside_repo(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    import sys
    argv = sys.argv[:]
    sys.argv = ['check_deconstruction_benchmark_readiness.py', '--json']
    try:
        assert readiness_main() == 1
    finally:
        sys.argv = argv
    payload = json.loads(capsys.readouterr().out)
    assert payload['all_files_ready'] is False
    assert 'missing benchmark assets' in payload['remaining_blockers'][0]


def test_readiness_reports_ready_inside_repo(capsys, monkeypatch) -> None:
    monkeypatch.chdir('/home/user/ai-books')
    import sys
    argv = sys.argv[:]
    sys.argv = ['check_deconstruction_benchmark_readiness.py', '--json']
    try:
        assert readiness_main() == 0
    finally:
        sys.argv = argv
    payload = json.loads(capsys.readouterr().out)
    assert payload['all_files_ready'] is True
    assert payload['ready_for_funded_rerun_once_provider_is_available'] is True
