"""Run B1 ai_trace + B4 slop scorers across all imitation drafts in output/.

Use this for threshold calibration and to identify draft outliers worthy of
reviewer attention. Pure read; no DB, no LLM, no writes.

Usage:
    python scripts/dev/heuristic-scorer-benchmark.py
    python scripts/dev/heuristic-scorer-benchmark.py --output-dir custom-dir
    python scripts/dev/heuristic-scorer-benchmark.py --top 20

Exit 0 always; this is a reporting tool not a gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean, median, stdev

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from novel_analyzer.services.ai_trace_signal_service import score_ai_trace  # noqa: E402
from novel_analyzer.services.slop_scorer_service import score_slop  # noqa: E402


def collect_drafts(root: Path, *, include_scaffold: bool = False) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    if not root.is_dir():
        return out
    for parent in sorted(root.iterdir()):
        if not parent.is_dir():
            continue
        for js in sorted(parent.glob("writer-imitate-ch*.json")):
            try:
                payload = json.loads(js.read_text(encoding="utf-8"))
            except Exception:
                continue
            final_draft = payload.get("final_draft") or {}
            text = final_draft.get("draft_text") or payload.get("draft_text") or ""
            if not isinstance(text, str) or len(text) <= 200:
                continue
            if not include_scaffold and final_draft.get("is_scaffold_only"):
                continue
            out.append((js, text))
    return out


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, int(len(sorted_values) * p))
    return sorted_values[idx]


def summarize(name: str, values: list[float]) -> str:
    if not values:
        return f"{name:30s}  n=0"
    sv = sorted(values)
    return (
        f"{name:30s}  n={len(values):4d}  "
        f"mean={mean(values):.3f}  median={median(values):.3f}  "
        f"stdev={(stdev(values) if len(values) >= 2 else 0):.3f}  "
        f"p90={percentile(sv, 0.90):.3f}  p95={percentile(sv, 0.95):.3f}  "
        f"p99={percentile(sv, 0.99):.3f}  max={max(values):.3f}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "output"),
        help="Root directory containing whole-book-* subdirs with writer-imitate-ch*.json files",
    )
    parser.add_argument(
        "--top", type=int, default=10, help="Show top-N flagged drafts"
    )
    parser.add_argument(
        "--include-scaffold",
        action="store_true",
        help="Include is_scaffold_only=True drafts (excluded by default — they are "
        "outline-only fallback artifacts that pollute the score distribution)",
    )
    parser.add_argument(
        "--ai-trace-warn", type=float, default=0.24,
        help="Threshold for warn (default p90 from real-data calibration)",
    )
    parser.add_argument(
        "--ai-trace-alert", type=float, default=0.30,
        help="Threshold for alert (>p99 on real data)",
    )
    parser.add_argument(
        "--slop-warn", type=float, default=0.02,
        help="Threshold for warn (default p90 from real-data calibration)",
    )
    parser.add_argument(
        "--slop-alert", type=float, default=0.05,
        help="Threshold for alert (>p99 on real data)",
    )
    args = parser.parse_args(argv)

    drafts = collect_drafts(Path(args.output_dir), include_scaffold=args.include_scaffold)
    print(f"Loaded {len(drafts)} drafts from {args.output_dir}")
    if not args.include_scaffold:
        print("(is_scaffold_only=True drafts excluded; pass --include-scaffold to include)")
    if not drafts:
        return 0
    print()

    ai_overall: list[float] = []
    ai_rep: list[float] = []
    ai_uniformity: list[float] = []
    ai_hedge: list[float] = []
    slop_overall: list[float] = []
    slop_cliche: list[float] = []
    slop_telling: list[float] = []
    slop_adverb: list[float] = []
    flagged_alerts: list[tuple[float, str, dict]] = []
    warn_count = {"ai": 0, "slop": 0}

    for path, text in drafts:
        ai = score_ai_trace(text)
        sl = score_slop(text)
        ai_overall.append(ai.overall_ai_trace_score)
        ai_rep.append(ai.ngram_repetition_score)
        ai_uniformity.append(ai.sentence_uniformity_score)
        ai_hedge.append(ai.hedge_word_density)
        slop_overall.append(sl.overall_slop_score)
        slop_cliche.append(sl.cliche_phrase_score)
        slop_telling.append(sl.telling_violation_score)
        slop_adverb.append(sl.adverb_stacking_score)

        if ai.overall_ai_trace_score >= args.ai_trace_warn:
            warn_count["ai"] += 1
        if sl.overall_slop_score >= args.slop_warn:
            warn_count["slop"] += 1
        if ai.overall_ai_trace_score >= args.ai_trace_alert or sl.overall_slop_score >= args.slop_alert:
            flagged_alerts.append((
                ai.overall_ai_trace_score + sl.overall_slop_score,
                str(path.relative_to(REPO_ROOT)),
                {
                    "ai_overall": ai.overall_ai_trace_score,
                    "ai_rep": ai.ngram_repetition_score,
                    "slop_overall": sl.overall_slop_score,
                    "top_ngrams": ai.top_repeated_ngrams[:3],
                },
            ))

    print("=== B1 ai_trace_signal_service ===")
    print(summarize("overall_ai_trace_score", ai_overall))
    print(summarize("ngram_repetition_score", ai_rep))
    print(summarize("sentence_uniformity_score", ai_uniformity))
    print(summarize("hedge_word_density", ai_hedge))
    print()
    print("=== B4 slop_scorer_service ===")
    print(summarize("overall_slop_score", slop_overall))
    print(summarize("cliche_phrase_score", slop_cliche))
    print(summarize("telling_violation_score", slop_telling))
    print(summarize("adverb_stacking_score", slop_adverb))
    print()
    print(
        f"=== Threshold counts ===  "
        f"warn(ai>={args.ai_trace_warn}): {warn_count['ai']}/{len(drafts)}  "
        f"warn(slop>={args.slop_warn}): {warn_count['slop']}/{len(drafts)}"
    )
    print()
    print(f"=== Top {args.top} alerts (ai>={args.ai_trace_alert} OR slop>={args.slop_alert}): {len(flagged_alerts)} total ===")
    for combined, p, detail in sorted(flagged_alerts, reverse=True)[:args.top]:
        print(
            f"  combined={combined:.3f}  "
            f"ai={detail['ai_overall']:.3f}(rep={detail['ai_rep']:.3f})  "
            f"slop={detail['slop_overall']:.3f}  "
            f"top_repeats={detail['top_ngrams']}"
        )
        print(f"    {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
