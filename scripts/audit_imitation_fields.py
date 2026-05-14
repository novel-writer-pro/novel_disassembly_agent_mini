#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ["apps", "novel_analyzer", "tests"]
SESSION_PATTERN = re.compile(r"\bsession_[a-zA-Z_][a-zA-Z0-9_]*\b")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".venv", "node_modules", "upstream"}


def collect_fields(scan_dirs):
    fields = defaultdict(list)
    for d in scan_dirs:
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
                for line_num, line in enumerate(text.split("\n"), 1):
                    for match in SESSION_PATTERN.finditer(line):
                        name = match.group()
                        rel = str(path.relative_to(ROOT))
                        fields[name].append((rel, line_num, line.strip()[:120]))
    return fields


def classify(fields):
    rows = []
    for name in sorted(fields.keys()):
        refs = fields[name]
        unique_files = {ref[0] for ref in refs}
        if len(unique_files) >= 3 or len(refs) >= 5:
            status = "active"
        elif len(unique_files) == 1 and len(refs) <= 2:
            status = "orphan"
        else:
            status = "unknown"
        rows.append((name, len(refs), status, refs[:3]))
    return rows


def render_md(rows, total_unique):
    lines = ["# imitation session_* 字段使用率审计", ""]
    lines.append("> 自动生成 by `scripts/audit_imitation_fields.py`")
    lines.append(f"> 共扫描出 **{total_unique}** 个唯一字段名")
    lines.append("")
    counts = defaultdict(int)
    for _, _, status, _ in rows:
        counts[status] += 1
    lines.append(
        f"分类汇总：active = {counts['active']}, "
        f"unknown = {counts['unknown']}, orphan = {counts['orphan']}"
    )
    lines.append("")
    lines.append("| 字段名 | 引用数 | 状态 | 示例位置 |")
    lines.append("|---|---|---|---|")
    for name, count, status, examples in rows:
        ex = "<br>".join(f"`{p}:{ln}`" for p, ln, _ in examples)
        lines.append(f"| `{name}` | {count} | **{status}** | {ex} |")
    lines.append("")
    lines.append("## 处理建议")
    lines.append("")
    lines.append("- **active**：保留，加入冻结 schema（T17）")
    lines.append("- **unknown**：人工 review，补 TODO 注释")
    lines.append("- **orphan**：进入 `deprecated_in: writer-studio-v2` 弃用窗口")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/imitation/session-fields-audit.md")
    args = parser.parse_args()

    fields = collect_fields(SCAN_DIRS)
    rows = classify(fields)
    md = render_md(rows, total_unique=len(rows))

    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    print(f"wrote {out}")

    counts = defaultdict(int)
    for _, _, status, _ in rows:
        counts[status] += 1
    print(
        f"unique={len(rows)} active={counts['active']} "
        f"unknown={counts['unknown']} orphan={counts['orphan']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
