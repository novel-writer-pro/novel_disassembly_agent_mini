#!/usr/bin/env python3
"""Summarize one real deconstruction run for benchmark comparison."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import AnalysisRun, ChapterJob, ChapterRawOutput, RunBranch


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize one deconstruction run.")
    parser.add_argument("run_id")
    parser.add_argument("branch_id")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def main() -> int:
    args = _parse_args()
    engine = create_engine(args.database_url, future=True)
    with Session(engine) as session:
        run = session.scalar(select(AnalysisRun).where(AnalysisRun.id == args.run_id))
        branch = session.scalar(select(RunBranch).where(RunBranch.id == args.branch_id))
        if run is None or branch is None:
            raise SystemExit("unknown run_id or branch_id")

        jobs = session.scalars(
            select(ChapterJob)
            .where(ChapterJob.branch_id == args.branch_id)
            .order_by(ChapterJob.chapter_index)
        ).all()
        raws = session.scalars(
            select(ChapterRawOutput)
            .where(ChapterRawOutput.branch_id == args.branch_id)
            .order_by(ChapterRawOutput.chapter_index)
        ).all()

        completed = [job for job in jobs if job.status == "validated"]
        failed = [job for job in jobs if job.status == "failed"]
        started_at = min((job.started_at for job in jobs if job.started_at is not None), default=None)
        finished_at = max((job.updated_at for job in completed if job.updated_at is not None), default=None)
        elapsed_seconds = None
        if started_at and finished_at:
            elapsed_seconds = (finished_at - started_at).total_seconds()

        totals: dict[str, int] = defaultdict(int)
        per_chapter: list[dict[str, Any]] = []
        for raw in raws:
            meta = raw.invocation_metadata or {}
            counts = meta.get("prompt_char_counts") or {}
            if isinstance(counts, dict):
                for key, value in counts.items():
                    try:
                        totals[str(key)] += int(value)
                    except Exception:
                        pass
            total_prompt_chars = meta.get("total_prompt_chars")
            per_chapter.append(
                {
                    "chapter_index": raw.chapter_index,
                    "job_attempt": raw.job_attempt,
                    "model_name": meta.get("model_name"),
                    "pipeline": meta.get("pipeline"),
                    "total_prompt_chars": total_prompt_chars,
                    "prompt_char_counts": counts,
                    "parse_status": raw.parse_status,
                }
            )

        payload = {
            "run_id": args.run_id,
            "branch_id": args.branch_id,
            "completed_chapters": len(completed),
            "failed_jobs": len(failed),
            "started_at": _iso(started_at),
            "finished_at": _iso(finished_at),
            "elapsed_seconds": elapsed_seconds,
            "avg_seconds_per_completed_chapter": (
                elapsed_seconds / len(completed) if elapsed_seconds and completed else None
            ),
            "prompt_char_totals": dict(sorted(totals.items())),
            "per_chapter": per_chapter,
        }

        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"run_id={payload['run_id']}")
            print(f"branch_id={payload['branch_id']}")
            print(f"completed_chapters={payload['completed_chapters']}")
            print(f"failed_jobs={payload['failed_jobs']}")
            print(f"started_at={payload['started_at']}")
            print(f"finished_at={payload['finished_at']}")
            print(f"elapsed_seconds={payload['elapsed_seconds']}")
            print(f"avg_seconds_per_completed_chapter={payload['avg_seconds_per_completed_chapter']}")
            for key, value in payload["prompt_char_totals"].items():
                print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
