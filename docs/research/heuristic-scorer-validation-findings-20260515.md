# Heuristic Scorer Validation Findings — 2026-05-15

> **Verdict**: B1 ai_trace_signal_service does NOT correlate with draft quality
> in the direction documented. B4 slop_scorer_service correlates directionally
> but with effect size too small to act on alone. **Both deferred from
> production wiring** until we understand the signal better.
> **Source**: 507-draft real-data correlation analysis run at commit `3eeecda`.

---

## TL;DR

| Borrow | Original claim | Real-data finding | Verdict |
|---|---|---|---|
| **B1** ai_trace | "high score = AI-flavored draft, deserves reviewer attention" | **Inverted**: pass-verdict drafts have HIGHER mean B1 (0.201) than needs_revision drafts (0.184). The signal is more likely tracking "narrative density" than "AI flavor". | **Do NOT wire as a quality gate.** Keep as exploratory tool. |
| **B4** slop | "regex-only, ~1000× faster than LLM-judge, catches loud tells" | Directionally correct: needs_revision mean (0.006) is 3× pass mean (0.002). Effect size near noise floor — both medians = 0. | **Defer wiring** until we know if effect size grows under non-imitation conditions. |

The two scorers and the benchmark tool itself remain in tree as **diagnostic helpers**, not quality gates.

---

## 1. The check

After landing B1+B4+B5 + real-data threshold calibration, ran a correlation
check that I should have done before claiming "B1 catches AI-flavored
drafts":

```bash
python3 -c "
import json, sys
sys.path.insert(0, '/home/user/ai-books')
from pathlib import Path
from novel_analyzer.services.ai_trace_signal_service import score_ai_trace
from novel_analyzer.services.slop_scorer_service import score_slop

verdict_buckets = {}
for parent in sorted(Path('output').iterdir()):
    if not parent.is_dir(): continue
    for js in sorted(parent.glob('writer-imitate-ch*.json')):
        payload = json.loads(js.read_text())
        text = payload.get('final_draft', {}).get('draft_text', '')
        if len(text) < 200: continue
        verdict = payload.get('final_verdict', 'unknown')
        ai = score_ai_trace(text).overall_ai_trace_score
        sl = score_slop(text).overall_slop_score
        verdict_buckets.setdefault(verdict, []).append((ai, sl))
"
```

Result on 507 drafts:

```
verdict          n     B1_mean  B1_p95  B4_mean  B4_p95
needs_revision   344   0.184    0.251   0.006    0.032
pass             163   0.201    0.259   0.002    0.013
```

## 2. Why B1 is inverted

The `ngram_repetition_score` component dominates B1's variance. Production
imitation drafts that pass the harness are typically:

- Longer (3-4k chars vs 1.5-2k for needs_revision)
- Denser with named entities (`徐凤年` / `卫图` / `路朝歌` repeating naturally
  through dialogue and POV)
- Coherent enough to mention the same locations/objects multiple times

Drafts that need revision are typically:

- Shorter (often the harness gave up early)
- Thinner on entity recurrence (less narrative completeness)

So `ngram_repetition_score` rewards exactly the wrong pattern: dense
character-driven narrative scores HIGH, threadbare scaffold prose scores LOW.
The 0.55 outlier (`ch74 叛军×28`) is real, but it's a 1-in-507 case, not the
typical signal.

## 3. Why B4 is too weak

B4's components — cliché phrases, telling violations, degree-adverb stacking
— **are caught by the existing harness pipeline**. The imitation harness
already runs through stage-merged prompts that explicitly avoid cliché tells.
By the time a draft reaches `final_draft`, the obvious slop has been
scrubbed.

This is a "dog that didn't bark" finding: B4 doesn't help because the harness
already does its job upstream. B4 might help in a context where drafts come
from outside the harness (raw LLM output, user pastes, etc.).

## 4. The one thing that DID work

The benchmark surfaced one real anomaly:
`output/whole-book-zhuxian-scifi-59ch/writer-imitate-ch49.json` — a 502-char
draft that is **pure outline scaffold leaked into final_draft**:

```
第49章 看相
【章节目标】斗败老怪
场景1：承接上一章结果并明确当前需求/目标
...
【修订提示】后续版本应补足中段阻力、行动抉择与章尾钩子之间的承接。
【修订提示】... (×4 repeated)
```

`is_scaffold_only=True`, `verdict=needs_revision`. The harness DID know it
failed, but the draft was committed to disk anyway. This is a real harness
bug:

- `is_scaffold_only=True` drafts should not be persisted as the final
  artifact unless explicitly user-requested
- Or: the consuming code (whole_book_imitation, evaluation reports) should
  filter these out

**This is a higher-value follow-up than wiring B1/B4.**

## 5. What stays, what goes

Stays in tree:

- `novel_analyzer/services/ai_trace_signal_service.py` — diagnostic helper,
  documented as "narrative density proxy, NOT a quality gate"
- `novel_analyzer/services/slop_scorer_service.py` — diagnostic helper,
  documented with weak effect size
- `novel_analyzer/services/elo_tournament_service.py` — independent of
  B1/B4 outcome; pure math; still useful when pairwise data accumulates
- `scripts/dev/heuristic-scorer-benchmark.py` — re-runnable, parameterized

Stays in tree but **NOT to be promoted to GateChecker without further work**:

- B1 and B4 wiring into `risk_audit_checkers.py`. The original plan was to
  add them as `AITraceChecker` and `SlopChecker` GateCheckers. **Do not do
  this** until either:
  - We find a non-imitation corpus where B4 effect size > 5×, or
  - We redesign B1 to NOT use ngram repetition as the dominant component

Already-rejected paths:

- "Tune the threshold lower so more drafts trip B1" — won't help, the
  signal direction is wrong
- "Use B1 + B4 as a multiplicative gate" — multiplying near-zero
  signals doesn't fix correlation direction

## 6. Lessons learned (for future borrow items)

1. **Threshold calibration ≠ signal validation**. p99 of 0.27 told me where
   the cliff was, NOT whether the cliff is in the right place. Always run a
   correlation against the **outcome variable** (here: harness verdict)
   before claiming a heuristic is a quality signal.
2. **"Inspired by N-star repo X" doesn't transfer**. The inkos 33-dimension
   audit lives inside a different harness; their dimensions might not be
   redundant with their main pipeline. Ours are.
3. **Pure-function helpers are still cheap to keep around**. The 250 lines
   of B1+B4 cost nothing to leave in tree as diagnostic tools, but **the
   wiring is what would have cost us** — false alerts in production reviewer
   queues.
4. **Always check the dog-that-didn't-bark hypothesis**: if your scorer
   rarely fires (B4 median = 0.000), the upstream pipeline might already
   handle the issue. Run on out-of-distribution data before committing.

## 7. Updated handoff guidance

Update [`session-handoff-20260514-kernel-and-integration.md`](../session-handoff-20260514-kernel-and-integration.md) §10:

- B1: **kept as diagnostic, NOT for GateChecker promotion**
- B4: **kept as diagnostic, defer to non-imitation corpus**
- B5: **independent of this finding, still ready for wiring** when the DB
  maintenance window opens
- ch49 scaffold-leak bug surfaced: log as separate follow-up

## 8. ch49 scaffold-leak follow-up (out of scope here)

Recommended fix shape (for whoever picks this up):

1. Search `whole_book_imitation_service.py` and `imitation_harness_service.py`
   for sites that write `final_draft` to disk
2. Add a guard: if `final_draft.is_scaffold_only` AND user did NOT pass
   `--allow-scaffold-output`, skip persistence and keep the previous round's
   draft (or fail loudly)
3. Add a regression test using the ch49 payload as a fixture

This is a real harness bug worth ~half a day. Not a borrow item.
