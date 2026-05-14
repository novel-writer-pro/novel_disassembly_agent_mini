"""Re-materialize heuristic chapter artifacts to refresh contaminated retrieval_documents.

This is the Phase-4-equivalent (no destructive SQL): walks every chapter_artifact
tagged extraction_source='heuristic' and re-runs the existing materialization paths.
Phase 3 guards in retrieval_service / fact_service ensure the upsert overwrites
polluted keyword_list / query_hints / FactRecord rows with clean ones (empty entity
sets + title-only query hint).

Idempotent: running it twice produces the same result. Embedding vectors are
regenerated each pass — set --skip-embeddings to keep existing chunk vectors
(faster, but chunk_text may not match the cleaned keyword_list).

Usage:
    .venv/bin/python scripts/rematerialize_heuristic_artifacts.py --dry-run
    .venv/bin/python scripts/rematerialize_heuristic_artifacts.py --branch e5becabd-...
    .venv/bin/python scripts/rematerialize_heuristic_artifacts.py --commit-every 25
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Iterable

from sqlalchemy import text

from novel_analyzer.config.settings import Settings
from novel_analyzer.database.session import create_session_factory
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.retrieval_service import RetrievalService


SQL_FIND_HEURISTIC = """
SELECT id, branch_id, chapter_index
FROM chapter_artifacts
WHERE artifact_type = 'chapter_analysis'
  AND payload_json::jsonb ->> 'extraction_source' = 'heuristic'
  AND deleted_at IS NULL
"""


def iter_targets(session, branch_filter: str | None) -> Iterable[tuple[str, str, int]]:
    sql = SQL_FIND_HEURISTIC
    params: dict[str, str] = {}
    if branch_filter:
        sql += " AND branch_id = :b"
        params["b"] = branch_filter
    sql += " ORDER BY branch_id, chapter_index"
    yield from session.execute(text(sql), params).fetchall()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Count targets without re-materializing")
    parser.add_argument("--branch", default=None, help="Restrict to one branch_id (default: all heuristic rows)")
    parser.add_argument("--commit-every", type=int, default=10, help="Commit and reopen session every N rows")
    parser.add_argument("--skip-fact", action="store_true", help="Skip fact_service.materialize_for_artifact")
    args = parser.parse_args()

    settings = Settings()
    factory = create_session_factory(settings)

    with factory() as s:
        targets = list(iter_targets(s, args.branch))

    print(f"Found {len(targets)} heuristic chapter_artifacts to refresh")
    if not targets:
        return 0
    by_branch: dict[str, int] = {}
    for _aid, bid, _ch in targets:
        by_branch[bid] = by_branch.get(bid, 0) + 1
    for bid, n in sorted(by_branch.items(), key=lambda x: -x[1]):
        print(f"  {bid[:8]}: {n} chapters")
    if args.dry_run:
        print("(dry-run — no changes)")
        return 0

    started = time.perf_counter()
    done = 0
    failures = 0
    batch: list[tuple[str, str, int]] = []
    for row in targets:
        batch.append(row)
        if len(batch) >= args.commit_every:
            done, failures = _process_batch(factory, settings, batch, args.skip_fact, done, failures)
            batch = []
    if batch:
        done, failures = _process_batch(factory, settings, batch, args.skip_fact, done, failures)

    elapsed = time.perf_counter() - started
    print(
        f"\nFinished: {done}/{len(targets)} re-materialized, "
        f"{failures} failures in {elapsed:.1f}s "
        f"({done / max(elapsed, 0.01):.1f} rows/sec)"
    )
    return 0 if failures == 0 else 2


def _process_batch(
    factory,
    settings,
    batch: list[tuple[str, str, int]],
    skip_fact: bool,
    done: int,
    failures: int,
) -> tuple[int, int]:
    with factory() as s:
        retrieval = RetrievalService(s, settings)
        fact = FactService(s) if not skip_fact else None
        for artifact_id, branch_id, chapter_index in batch:
            try:
                retrieval.materialize_for_artifact(artifact_id)
                if fact is not None:
                    fact.materialize_for_artifact(artifact_id)
                done += 1
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(
                    f"  FAIL {branch_id[:8]} ch{chapter_index}: "
                    f"{type(exc).__name__}: {str(exc)[:120]}"
                )
                s.rollback()
                continue
        s.commit()
    print(f"  ✓ batch committed (cumulative: {done} done, {failures} failures)")
    return done, failures


if __name__ == "__main__":
    sys.exit(main())
