#!/usr/bin/env python3
"""Export a complete benchmark bundle from baseline/candidate benchmark JSON files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a deconstruction benchmark bundle.")
    parser.add_argument("baseline_json")
    parser.add_argument("candidate_json")
    parser.add_argument("output_dir")
    return parser.parse_args()


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main() -> int:
    args = _parse_args()
    baseline_path = Path(args.baseline_json)
    candidate_path = Path(args.candidate_json)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline = _load(str(baseline_path))
    candidate = _load(str(candidate_path))

    compare_json = subprocess.run(
        [sys.executable, 'scripts/compare_deconstruction_benchmarks.py', str(baseline_path), str(candidate_path), '--json'],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    compare = json.loads(compare_json)

    (output_dir / 'baseline.json').write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding='utf-8')
    (output_dir / 'candidate.json').write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding='utf-8')
    (output_dir / 'compare.json').write_text(json.dumps(compare, ensure_ascii=False, indent=2), encoding='utf-8')

    summary = output_dir / 'summary.md'
    summary.write_text(
        (
            '# 拆书 benchmark 对照摘要\n\n'
            f"- baseline_run_id: `{compare['baseline_run_id']}`\n"
            f"- candidate_run_id: `{compare['candidate_run_id']}`\n"
            f"- baseline.completed_chapters: `{compare['completed_chapters']['baseline']}`\n"
            f"- candidate.completed_chapters: `{compare['completed_chapters']['candidate']}`\n"
            f"- failed_jobs.delta: `{compare['failed_jobs']['delta']}`\n"
            f"- elapsed_seconds.delta: `{compare['elapsed_seconds']['delta']}`\n"
            f"- elapsed_seconds.delta_pct: `{compare['elapsed_seconds']['delta_pct']}`\n"
            f"- avg_seconds_per_completed_chapter.delta: `{compare['avg_seconds_per_completed_chapter']['delta']}`\n"
            f"- avg_seconds_per_completed_chapter.delta_pct: `{compare['avg_seconds_per_completed_chapter']['delta_pct']}`\n"
        ),
        encoding='utf-8',
    )
    print(f'bundle_dir={output_dir}')
    print(f'compare_json={output_dir / "compare.json"}')
    print(f'summary_md={summary}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
