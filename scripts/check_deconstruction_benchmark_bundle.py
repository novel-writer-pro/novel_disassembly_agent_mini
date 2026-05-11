#!/usr/bin/env python3
"""Validate a deconstruction benchmark bundle directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_FILES = ('baseline.json', 'candidate.json', 'compare.json', 'summary.md')
REQUIRED_COMPARE_KEYS = (
    'baseline_run_id',
    'candidate_run_id',
    'comparability',
    'completed_chapters',
    'failed_jobs',
    'elapsed_seconds',
    'avg_seconds_per_completed_chapter',
    'prompt_char_totals',
)
REQUIRED_COMPARABILITY_KEYS = (
    'chapter_count_match',
    'provider_purity_match',
    'is_strictly_comparable',
    'notes',
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Validate a deconstruction benchmark bundle directory.')
    parser.add_argument('bundle_dir')
    parser.add_argument('--json', action='store_true', dest='as_json')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    bundle_dir = Path(args.bundle_dir)
    missing_files = [name for name in REQUIRED_FILES if not (bundle_dir / name).exists()]
    compare_path = bundle_dir / 'compare.json'
    missing_compare_keys: list[str] = []
    missing_comparability_keys: list[str] = []
    if compare_path.exists():
        payload = json.loads(compare_path.read_text(encoding='utf-8'))
        missing_compare_keys = [key for key in REQUIRED_COMPARE_KEYS if key not in payload]
        comparability = payload.get('comparability') or {}
        if isinstance(comparability, dict):
            missing_comparability_keys = [key for key in REQUIRED_COMPARABILITY_KEYS if key not in comparability]
        else:
            missing_comparability_keys = list(REQUIRED_COMPARABILITY_KEYS)
    else:
        missing_compare_keys = list(REQUIRED_COMPARE_KEYS)
        missing_comparability_keys = list(REQUIRED_COMPARABILITY_KEYS)

    ok = not missing_files and not missing_compare_keys and not missing_comparability_keys
    result = {
        'bundle_dir': str(bundle_dir),
        'ok': ok,
        'missing_files': missing_files,
        'missing_compare_keys': missing_compare_keys,
        'missing_comparability_keys': missing_comparability_keys,
    }
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"bundle_dir={result['bundle_dir']}")
        print(f"ok={str(result['ok']).lower()}")
        print(f"missing_files={','.join(missing_files)}")
        print(f"missing_compare_keys={','.join(missing_compare_keys)}")
        print(f"missing_comparability_keys={','.join(missing_comparability_keys)}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
