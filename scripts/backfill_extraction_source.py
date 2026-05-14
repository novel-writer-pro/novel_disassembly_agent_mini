"""One-shot backfill: tag legacy chapter_artifacts with extraction_source.

Phase 2 of fallback isolation. Run once after Phase-1 deploy to retroactively
mark the existing rows so consumer guards (Phase 3) work uniformly.

Idempotent: rows already tagged are skipped.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from novel_analyzer.config.settings import Settings
from novel_analyzer.database.session import create_session_factory

SQL_TAG_HEURISTIC = """
UPDATE chapter_artifacts
SET payload_json = jsonb_set(
    payload_json::jsonb,
    '{extraction_source}',
    '"heuristic"'::jsonb,
    true
)
WHERE artifact_type = 'chapter_analysis'
  AND payload_json::jsonb -> 'continuity_notes' ->> 0 LIKE '%本地启发式分析保底生成%'
  AND (payload_json::jsonb -> 'extraction_source') IS NULL
"""

SQL_TAG_LLM = """
UPDATE chapter_artifacts
SET payload_json = jsonb_set(
    payload_json::jsonb,
    '{extraction_source}',
    '"llm"'::jsonb,
    true
)
WHERE artifact_type = 'chapter_analysis'
  AND (payload_json::jsonb -> 'extraction_source') IS NULL
"""

SQL_AUDIT = """
SELECT
  COUNT(*) FILTER (WHERE payload_json::jsonb ->> 'extraction_source' = 'heuristic')
    AS heuristic_count,
  COUNT(*) FILTER (WHERE payload_json::jsonb ->> 'extraction_source' = 'llm') AS llm_count,
  COUNT(*) FILTER (WHERE (payload_json::jsonb -> 'extraction_source') IS NULL)
    AS untagged_count,
  COUNT(*) AS total
FROM chapter_artifacts
WHERE artifact_type = 'chapter_analysis'
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report counts without updating")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    factory = create_session_factory(settings)
    with factory() as s:
        before = s.execute(text(SQL_AUDIT)).fetchone()
        print(
            f"Before: heuristic={before[0]} llm={before[1]} "
            f"untagged={before[2]} total={before[3]}"
        )
        if args.dry_run:
            print("(dry-run — no updates applied)")
            return 0
        h_result = s.execute(text(SQL_TAG_HEURISTIC))
        l_result = s.execute(text(SQL_TAG_LLM))
        s.commit()
        after = s.execute(text(SQL_AUDIT)).fetchone()
        print(f"Tagged heuristic: {h_result.rowcount} rows")
        print(f"Tagged llm:       {l_result.rowcount} rows")
        print(
            f"After:  heuristic={after[0]} llm={after[1]} "
            f"untagged={after[2]} total={after[3]}"
        )
        if after[2] != 0:
            print(f"WARN: {after[2]} rows remain untagged")
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
