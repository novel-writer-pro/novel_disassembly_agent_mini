#!/usr/bin/env python3
"""Compare two benchmark_deconstruction_run JSON outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two deconstruction benchmark JSON files.")
    parser.add_argument("baseline_json")
    parser.add_argument("candidate_json")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _pct_delta(old: float | None, new: float | None) -> float | None:
    if old in (None, 0) or new is None:
        return None
    return ((new - old) / old) * 100.0


def _comparability(base: dict[str, Any], cand: dict[str, Any]) -> dict[str, Any]:
    base_completed = base.get('completed_chapters')
    cand_completed = cand.get('completed_chapters')
    base_pure = base.get('is_pure_primary_provider_run')
    cand_pure = cand.get('is_pure_primary_provider_run')
    chapter_count_match = (
        base_completed is not None and cand_completed is not None and base_completed == cand_completed
    )
    provider_purity_match = base_pure is True and cand_pure is True
    return {
        'chapter_count_match': chapter_count_match,
        'provider_purity_match': provider_purity_match,
        'is_strictly_comparable': bool(chapter_count_match and provider_purity_match),
        'notes': [
            note for note in [
                None if chapter_count_match else 'chapter count differs between baseline and candidate',
                None if provider_purity_match else 'at least one run is not a pure primary-provider run',
            ] if note
        ],
    }


def main() -> int:
    args = _parse_args()
    baseline = _load(args.baseline_json)
    candidate = _load(args.candidate_json)

    base_elapsed = baseline.get('elapsed_seconds')
    cand_elapsed = candidate.get('elapsed_seconds')
    base_avg = baseline.get('avg_seconds_per_completed_chapter')
    cand_avg = candidate.get('avg_seconds_per_completed_chapter')

    base_prompts = baseline.get('prompt_char_totals') or {}
    cand_prompts = candidate.get('prompt_char_totals') or {}
    prompt_diff: dict[str, dict[str, Any]] = {}
    for key in sorted(set(base_prompts) | set(cand_prompts)):
        old = base_prompts.get(key)
        new = cand_prompts.get(key)
        prompt_diff[key] = {
            'baseline': old,
            'candidate': new,
            'delta': (None if old is None or new is None else new - old),
            'delta_pct': _pct_delta(float(old) if old is not None else None, float(new) if new is not None else None),
        }

    payload = {
        'baseline_run_id': baseline.get('run_id'),
        'candidate_run_id': candidate.get('run_id'),
        'comparability': _comparability(baseline, candidate),
        'completed_chapters': {
            'baseline': baseline.get('completed_chapters'),
            'candidate': candidate.get('completed_chapters'),
        },
        'failed_jobs': {
            'baseline': baseline.get('failed_jobs'),
            'candidate': candidate.get('failed_jobs'),
            'delta': (candidate.get('failed_jobs') or 0) - (baseline.get('failed_jobs') or 0),
        },
        'elapsed_seconds': {
            'baseline': base_elapsed,
            'candidate': cand_elapsed,
            'delta': (None if base_elapsed is None or cand_elapsed is None else cand_elapsed - base_elapsed),
            'delta_pct': _pct_delta(float(base_elapsed) if base_elapsed is not None else None, float(cand_elapsed) if cand_elapsed is not None else None),
        },
        'avg_seconds_per_completed_chapter': {
            'baseline': base_avg,
            'candidate': cand_avg,
            'delta': (None if base_avg is None or cand_avg is None else cand_avg - base_avg),
            'delta_pct': _pct_delta(float(base_avg) if base_avg is not None else None, float(cand_avg) if cand_avg is not None else None),
        },
        'prompt_char_totals': prompt_diff,
    }

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"baseline_run_id={payload['baseline_run_id']}")
        print(f"candidate_run_id={payload['candidate_run_id']}")
        print(f"is_strictly_comparable={str(payload['comparability']['is_strictly_comparable']).lower()}")
        print(f"elapsed_delta_seconds={payload['elapsed_seconds']['delta']}")
        print(f"elapsed_delta_pct={payload['elapsed_seconds']['delta_pct']}")
        print(f"avg_per_chapter_delta_seconds={payload['avg_seconds_per_completed_chapter']['delta']}")
        print(f"avg_per_chapter_delta_pct={payload['avg_seconds_per_completed_chapter']['delta_pct']}")
        print(f"failed_jobs_delta={payload['failed_jobs']['delta']}")
        for key, row in payload['prompt_char_totals'].items():
            print(f"{key}_delta={row['delta']}")
            print(f"{key}_delta_pct={row['delta_pct']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
