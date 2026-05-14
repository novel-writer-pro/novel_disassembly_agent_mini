#!/usr/bin/env python3
"""Check whether the repo is ready for a funded deconstruction benchmark rerun."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_PATHS = {
    'baseline_artifact': 'docs/deconstruction-acceleration/benchmarks/weitu-baseline-20260511.json',
    'funded_runbook': 'docs/deconstruction-acceleration/funded-benchmark-runbook.md',
    'benchmark_cli': 'scripts/benchmark_deconstruction_run.py',
    'compare_cli': 'scripts/compare_deconstruction_benchmarks.py',
    'runner_cli': 'scripts/run_deconstruction_benchmark.py',
    'bundle_exporter': 'scripts/export_deconstruction_benchmark_bundle.py',
    'bundle_runner': 'scripts/run_and_export_deconstruction_benchmark_bundle.py',
    'bundle_validator': 'scripts/check_deconstruction_benchmark_bundle.py',
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Check funded benchmark readiness.')
    parser.add_argument('--json', action='store_true', dest='as_json')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    path_status = {key: Path(path).exists() for key, path in REQUIRED_PATHS.items()}
    all_files_ready = all(path_status.values())
    payload = {
        'all_files_ready': all_files_ready,
        'path_status': path_status,
        'remaining_blockers': ([] if all_files_ready else ['missing benchmark assets']) + ['funded-provider availability / balance required for final 20-chapter candidate run'],
        'ready_for_funded_rerun_once_provider_is_available': all_files_ready,
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"all_files_ready={str(payload['all_files_ready']).lower()}")
        print(f"ready_for_funded_rerun_once_provider_is_available={str(payload['ready_for_funded_rerun_once_provider_is_available']).lower()}")
        for key, value in path_status.items():
            print(f"{key}={str(value).lower()}")
        print('remaining_blockers=' + ';'.join(payload['remaining_blockers']))
    return 0 if all_files_ready else 1


if __name__ == '__main__':
    raise SystemExit(main())
