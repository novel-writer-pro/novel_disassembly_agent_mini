#!/usr/bin/env python3
"""Lint: prevent new session_* fields from being added in imitation pipeline.

Reads the audit report (`docs/imitation/session-fields-audit.md`) as the
authoritative inventory and fails CI if a freshly-scanned session_* field
is not present in the report.

Usage:
    .venv/bin/python scripts/check_no_new_session_fields.py

Exit codes:
    0 = no new fields detected
    1 = audit report missing or new fields found
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "imitation" / "session-fields-audit.md"
SCAN_DIRS = ["apps", "novel_analyzer", "tests"]
SESSION_PATTERN = re.compile(r"\bsession_[a-zA-Z_][a-zA-Z0-9_]*\b")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".venv", "node_modules", "upstream"}
ROW_PATTERN = re.compile(r"\|\s*`(session_[a-zA-Z_0-9]+)`\s*\|")


def known_fields() -> set[str]:
    if not REPORT.exists():
        sys.stderr.write(
            f"audit report missing: {REPORT}\n"
            "run scripts/audit_imitation_fields.py first\n"
        )
        sys.exit(1)
    fields: set[str] = set()
    for line in REPORT.read_text().split("\n"):
        m = ROW_PATTERN.search(line)
        if m:
            fields.add(m.group(1))
    return fields


def scan_fields() -> set[str]:
    fields: set[str] = set()
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for ext in ("*.py", "*.ts", "*.tsx", "*.json"):
            for path in base.rglob(ext):
                if any(part in SKIP_DIRS for part in path.parts):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for match in SESSION_PATTERN.finditer(text):
                    fields.add(match.group())
    return fields


def main() -> int:
    known = known_fields()
    current = scan_fields()
    new_fields = sorted(current - known)
    if new_fields:
        sys.stderr.write(
            "ERROR: new session_* fields detected (not in audit report):\n"
        )
        for f in new_fields:
            sys.stderr.write(f"  - {f}\n")
        sys.stderr.write(
            "\nIf intentional: re-run scripts/audit_imitation_fields.py to refresh "
            "the report, then commit both the new field and the updated audit.\n"
        )
        return 1
    print(f"OK: no new session_* fields. {len(known)} known, {len(current)} scanned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
