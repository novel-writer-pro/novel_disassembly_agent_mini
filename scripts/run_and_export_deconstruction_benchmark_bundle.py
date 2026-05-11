#!/usr/bin/env python3
"""Run a candidate benchmark and export the full comparison bundle against a committed baseline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run benchmark and export comparison bundle.')
    parser.add_argument('novel_path')
    parser.add_argument('--title', default='benchmark-novel')
    parser.add_argument('--database-url', required=True)
    parser.add_argument('--baseline-json', default='docs/deconstruction-acceleration/benchmarks/weitu-baseline-20260511.json')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--start-chapter', type=int, default=1)
    parser.add_argument('--end-chapter', type=int, default=20)
    parser.add_argument('--ensure-db', action='store_true')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_json = output_dir / 'candidate.json'

    run_out = subprocess.run(
        [
            sys.executable,
            'scripts/run_deconstruction_benchmark.py',
            args.novel_path,
            '--title', args.title,
            '--database-url', args.database_url,
            '--start-chapter', str(args.start_chapter),
            '--end-chapter', str(args.end_chapter),
            *( ['--ensure-db'] if args.ensure_db else [] ),
            '--json',
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    candidate_json.write_text(run_out, encoding='utf-8')

    bundle_out = subprocess.run(
        [
            sys.executable,
            'scripts/export_deconstruction_benchmark_bundle.py',
            args.baseline_json,
            str(candidate_json),
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    print(bundle_out.strip())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
