#!/usr/bin/env python3
"""Clean imitation draft contamination from whole-book outputs.

Two contamination types observed in output/whole-book-*-*ch/:
1. Trailing 'Harness Action Queue' debug bleed appended to draft_text.
2. Scaffold-only chapters where draft_text is the planning skeleton, no prose.

This script:
- Reads per-chapter writer-imitate-ch*.json files
- Produces a sibling *.clean.json with cleaned draft_text + a flag
- Rebuilds a *-imitation-fullbook-clean.md aggregate skipping scaffold-only
- Writes a contamination-report.json beside the clean fullbook

Run:  python3 scripts/clean_imitation_drafts.py output/whole-book-xuezhong-103ch [...]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Match the trailing action-queue block that follows the prose.
# It starts at the first 【Harness Action Queue】 OR at a run of [Pn|...] lines
# at the end of the draft_text.
_ACTQ_BLOCK = re.compile(
    r"(?:\n+【Harness Action Queue】.*$)|(?:\n+\[P\d\|(?:high|medium|low)\][^\n]*(?:\n\[P\d\|[^\n]*)*\s*$)",
    re.DOTALL,
)

_SCAFFOLD_MARKERS = re.compile(
    r"【章节目标】|【硬约束】|【说明】当前为仿写结构草案|【修订提示】"
)


def clean_draft_text(text: str) -> tuple[str, bool]:
    """Return (clean_text, scaffold_only)."""
    if not text:
        return "", True
    cleaned = _ACTQ_BLOCK.sub("", text).rstrip()
    scaffold_only = _SCAFFOLD_MARKERS.search(cleaned) is not None
    return cleaned, scaffold_only


def process_dir(src_dir: Path) -> dict:
    src_dir = src_dir.resolve()
    if not src_dir.is_dir():
        raise SystemExit(f"not a directory: {src_dir}")

    chapters = []
    for jp in sorted(src_dir.glob("writer-imitate-ch*.json"), key=_chapter_key):
        try:
            d = json.loads(jp.read_text(encoding="utf-8"))
        except Exception as exc:
            chapters.append({"path": str(jp), "error": str(exc)})
            continue
        ch = d.get("source_chapter_index")
        fd = d.get("final_draft") or {}
        raw = fd.get("draft_text") or ""
        clean, scaffold_only = clean_draft_text(raw)
        chapters.append({
            "ch": ch,
            "title": fd.get("draft_title") or fd.get("original_title") or "",
            "raw_len": len(raw),
            "clean_len": len(clean),
            "trimmed": len(raw) - len(clean),
            "scaffold_only": scaffold_only,
            "clean_text": clean,
        })
    return {"src_dir": str(src_dir), "chapters": chapters}


def _chapter_key(p: Path) -> int:
    m = re.search(r"ch(\d+)", p.name)
    return int(m.group(1)) if m else 0


def write_clean_fullbook(novel_label: str, branch_id: str, chapters: list[dict], out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    valid = [c for c in chapters if not c.get("scaffold_only") and c.get("clean_len", 0) > 0]
    skipped = [c for c in chapters if c.get("scaffold_only") or c.get("clean_len", 0) == 0]

    total_chars = sum(c["clean_len"] for c in valid)
    fullbook_path = out_dir / f"{novel_label}-imitation-fullbook-clean.md"
    index_path = out_dir / "chapter-index-clean.md"
    report_path = out_dir / "contamination-report.json"

    lines = [
        f"# {novel_label} 整本仿写：完本草案（清洗版）",
        "",
        f"> 共 {len(valid)} 章有效（已剔除 {len(skipped)} 章 scaffold-only 失败），{total_chars:,} 字。",
        f"> 来源分支：{branch_id}",
        f"> 清洗规则：剥离 Harness Action Queue 调试尾巴；剔除无 prose 的 scaffold-only 章节。",
        "",
        "---",
        "",
    ]
    for c in valid:
        lines.append(f"## 第{c['ch']}章 {c['title']}")
        lines.append("")
        lines.append(c["clean_text"])
        lines.append("")
    fullbook_path.write_text("\n".join(lines), encoding="utf-8")

    idx = [
        f"# {novel_label} 整本章节索引（清洗版）",
        "",
        f"共 {len(valid)} 章有效 / 跳过 {len(skipped)} 章 scaffold-only / 总字数 {total_chars:,}",
        "",
        "| 章 | 标题 | 字数 | 调试尾巴字符 |",
        "|---|---|---|---|",
    ]
    for c in valid:
        idx.append(f"| {c['ch']} | {c['title']} | {c['clean_len']} | {c['trimmed']} |")
    if skipped:
        idx.append("")
        idx.append("## Scaffold-only 失败章节")
        idx.append("")
        idx.append("| 章 | 标题 | 原始字数 |")
        idx.append("|---|---|---|")
        for c in skipped:
            idx.append(f"| {c['ch']} | {c['title']} | {c['raw_len']} |")
    index_path.write_text("\n".join(idx), encoding="utf-8")

    report = {
        "novel_label": novel_label,
        "branch_id": branch_id,
        "total_chapters": len(chapters),
        "valid_chapters": len(valid),
        "scaffold_only_chapters": [c["ch"] for c in skipped],
        "total_chars_clean": total_chars,
        "total_chars_raw": sum(c["raw_len"] for c in chapters),
        "total_trimmed_chars": sum(c["trimmed"] for c in chapters),
        "per_chapter": [
            {k: v for k, v in c.items() if k != "clean_text"} for c in chapters
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "fullbook": str(fullbook_path),
        "index": str(index_path),
        "report": str(report_path),
        "valid": len(valid),
        "skipped": len(skipped),
        "chars": total_chars,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)

    manifest_path = Path(sys.argv[1])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for spec in manifest:
        chapters = []
        for sd in spec["src_dirs"]:
            chapters.extend(process_dir(Path(sd))["chapters"])
        chapters.sort(key=lambda c: c.get("ch") or 0)
        result = write_clean_fullbook(
            spec["novel_label"], spec["branch_id"], chapters, Path(spec["out_dir"])
        )
        print(f"[{spec['novel_label']}] -> {result}")
