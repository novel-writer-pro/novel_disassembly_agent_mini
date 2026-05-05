#!/usr/bin/env python3
"""Bootstrap a manual evaluation workspace from the tracked template."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "runs" / "manual_eval" / "_template"
TARGET_ROOT = ROOT / "runs" / "manual_eval"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a manual evaluation workspace for a new novel slug.",
    )
    parser.add_argument("novel_slug", help="Target folder name under runs/manual_eval/")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the target directory if it already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    slug = args.novel_slug.strip().strip("/")
    if not slug:
        raise SystemExit("novel_slug must not be empty")
    if slug == "_template":
        raise SystemExit("novel_slug must not be _template")

    source = TEMPLATE_DIR
    target = TARGET_ROOT / slug

    if not source.exists():
        raise SystemExit(f"template directory missing: {source}")

    if target.exists():
        if not args.force:
            raise SystemExit(
                f"target already exists: {target}\n"
                "Use --force to replace it."
            )
        shutil.rmtree(target)

    shutil.copytree(source, target)
    print(f"manual_eval_workspace={target}")
    print("next_step=fill notes/manual-review-notes.md and export artifacts into this workspace")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
