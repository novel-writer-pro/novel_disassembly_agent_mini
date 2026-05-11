#!/usr/bin/env python3
"""Run a deconstruction benchmark end-to-end on one novel file and emit summary."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a deconstruction benchmark end-to-end.")
    parser.add_argument("novel_path")
    parser.add_argument("--title", default="benchmark-novel")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--start-chapter", type=int, default=1)
    parser.add_argument("--end-chapter", type=int, default=20)
    parser.add_argument("--ensure-db", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
    return completed.stdout.strip()


def _parse_key_values(text: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for line in text.splitlines():
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        payload[key.strip()] = value.strip()
    return payload


def main() -> int:
    args = _parse_args()
    novel_path = Path(args.novel_path)
    if not novel_path.exists():
        raise SystemExit(f"novel_path not found: {novel_path}")

    python = sys.executable
    base_cmd = [python, '-m', 'novel_analyzer.cli.app']

    if args.ensure_db:
        _run(base_cmd + ['init-db', '--database-url', args.database_url])

    ingest_out = _run(base_cmd + ['ingest', str(novel_path), '--title', args.title, '--database-url', args.database_url])
    ingest_kv = _parse_key_values(ingest_out)
    novel_id = ingest_kv['novel_id']
    manifest_id = ingest_kv['manifest_id']

    start_out = _run(base_cmd + ['start-run', novel_id, manifest_id, '--database-url', args.database_url])
    start_kv = _parse_key_values(start_out)
    run_id = start_kv['run_id']
    branch_id = start_kv['branch_id']

    analyze_out = _run(
        base_cmd + [
            'analyze-range',
            run_id,
            branch_id,
            str(args.start_chapter),
            str(args.end_chapter),
            '--database-url',
            args.database_url,
        ],
        env=os.environ.copy(),
    )

    benchmark_out = _run(
        [python, 'scripts/benchmark_deconstruction_run.py', run_id, branch_id, '--database-url', args.database_url, '--json']
    )
    benchmark = json.loads(benchmark_out)
    benchmark['novel_id'] = novel_id
    benchmark['manifest_id'] = manifest_id
    benchmark['analyze_stdout'] = analyze_out

    if args.as_json:
        print(json.dumps(benchmark, ensure_ascii=False, indent=2))
    else:
        print(f"novel_id={novel_id}")
        print(f"manifest_id={manifest_id}")
        print(f"run_id={run_id}")
        print(f"branch_id={branch_id}")
        print(f"completed_chapters={benchmark['completed_chapters']}")
        print(f"failed_jobs={benchmark['failed_jobs']}")
        print(f"elapsed_seconds={benchmark['elapsed_seconds']}")
        print(f"avg_seconds_per_completed_chapter={benchmark['avg_seconds_per_completed_chapter']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
