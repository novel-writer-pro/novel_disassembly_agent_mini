#!/usr/bin/env python3
"""Render per-chapter writer-imitate JSON into reviewer-friendly .md.

Two modes:
- Default: render raw final_draft.draft_text (matches legacy weitu workspace).
- --clean: strip the Harness Action Queue trail and skip scaffold-only chapters.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

_ACTQ_BLOCK = re.compile(
    r"(?:\n+【Harness Action Queue】.*$)|(?:\n+\[P\d\|(?:high|medium|low)\][^\n]*(?:\n\[P\d\|[^\n]*)*\s*$)",
    re.DOTALL,
)
_SCAFFOLD_MARKERS = re.compile(r"【章节目标】|【硬约束】|【说明】当前为仿写结构草案|【修订提示】")


def clean_text(raw: str) -> tuple[str, bool]:
    if not raw:
        return "", True
    cleaned = _ACTQ_BLOCK.sub("", raw).rstrip()
    return cleaned, _SCAFFOLD_MARKERS.search(cleaned) is not None


def render(json_path: Path, out_path: Path, clean: bool) -> dict:
    d = json.loads(json_path.read_text(encoding="utf-8"))
    ch = d.get("source_chapter_index")
    fd = d.get("final_draft") or {}
    sp = d.get("steering_pack") or {}
    ps = d.get("policy_summary") or {}

    raw_draft = str(fd.get("draft_text", ""))
    if clean:
        body, scaffold_only = clean_text(raw_draft)
    else:
        body, scaffold_only = raw_draft.strip(), _SCAFFOLD_MARKERS.search(raw_draft) is not None

    lines: list[str] = []
    lines.append(f"# writer-imitate-ch{ch}")
    if clean and scaffold_only:
        lines.append("")
        lines.append("> ⚠️ scaffold-only chapter — no real prose. Skipping rendering of body.")

    lines.extend(["", "## Steering Pack"])
    for key in ("worldview_capsule", "trope_axes", "innovation_directives", "taboo_innovations", "external_knowledge_refs"):
        val = sp.get(key, "")
        if isinstance(val, (list, dict)):
            val = json.dumps(val, ensure_ascii=False)
        lines.append(f"- {key}: {val}")

    lines.extend(["", "## Draft Title", str(fd.get("draft_title", ""))])
    lines.extend(["", "## Original Title", str(fd.get("original_title", ""))])
    lines.extend(["", "## Target Goal", str(d.get("target_goal", ""))])
    lines.extend(["", "## Draft Text"])
    if clean and scaffold_only:
        lines.append("[scaffold-only — body suppressed in clean render]")
    else:
        lines.append(body)

    for label, key in (("Method Notes", "method_notes"), ("Comparison Notes", "comparison_notes"), ("Risk Gate Notes", "risk_gate_notes")):
        notes = fd.get(key) or []
        if notes:
            lines.extend(["", f"## {label}"])
            for n in notes:
                lines.append(f"- {n}")

    lines.extend(["", "## Final Verdict", f"- {d.get('final_verdict', '')}"])
    lines.extend(["", "## Stop Reason", f"- {d.get('stop_reason', '')}"])

    if ps:
        lines.extend(["", "## Policy Summary"])
        for k, v in ps.items():
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            lines.append(f"- {k}: {v}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return {"ch": ch, "scaffold_only": scaffold_only, "raw_len": len(raw_draft), "clean_len": len(body)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", nargs="+", help="manual_eval workspace dir(s)")
    ap.add_argument("--clean", action="store_true", help="strip action-queue trail; flag scaffold-only")
    args = ap.parse_args()

    for ws in args.workspace:
        ws_dir = Path(ws) / "artifacts" / "writer-output"
        if not ws_dir.is_dir():
            print(f"skip {ws}: missing {ws_dir}", file=sys.stderr)
            continue
        rendered = []
        for jp in sorted(ws_dir.glob("writer-imitate-ch*.json")):
            mp = jp.with_suffix(".md")
            rendered.append(render(jp, mp, args.clean))
        scaffold = sum(1 for r in rendered if r["scaffold_only"])
        print(f"{ws}: rendered {len(rendered)} chapters (scaffold-only={scaffold}, clean={args.clean})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
