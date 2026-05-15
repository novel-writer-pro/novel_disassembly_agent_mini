# Loom Carry-Over Shadow vs Enabled A/B Experiment

> **Goal**: Validate the kernel-sota §10 T5 claim that `loom_memory_mode=enabled`
> reduces character_ooc trigger rate ≥20% vs the legacy `shadow` mode on a
> real branch over 20+ chapters.
> **Effort**: ~3 days LLM runtime (~100-150 LLM calls per chapter × 20 chapters
> × 2 sides). Plan the budget before starting.
> **Reversibility**: Setting `loom_memory_mode` is per-process env; running
> the experiment leaves only output/ artifacts and DB writes.
> **Companion**: [docs/loom/roadmap.md](../loom/roadmap.md),
> [kernel-sota-gap-assessment-20260514.md §10](../strategy/kernel-sota-gap-assessment-20260514.md)

---

## 0. Preconditions

```bash
source .venv/bin/activate

# Need a branch with at least 20 source chapters analyzed
psql -tA -c "
SELECT branch_id, count(DISTINCT chapter_index) AS analyzed_chapters
FROM chapter_artifacts
WHERE chapter_index > 0
GROUP BY branch_id
HAVING count(DISTINCT chapter_index) >= 20
ORDER BY analyzed_chapters DESC
LIMIT 5;"
```

The Loom Phase 1 layered-memory path activates at `chapter_index >= 10`
(see `chapter_imitation_service.build_llm_draft`). A 20-chapter run gives
≥10 chapters where the difference between modes is observable.

Disk + LLM budget:

- ~150-200 LLM calls per chapter (analysis + imitation + audit)
- Round trip ~10s per call → ~30 min per chapter on average
- 20 chapters × 2 sides = 40 chapters total → ~20 hours of runtime
- Output footprint: ~50 MB per side

---

## 1. Side A: shadow mode (legacy carry-over)

Default behavior — no env override needed. Run a clean writer-imitate-range:

```bash
cd /home/user/ai-books
mkdir -p output/loom-ab-shadow-<branch_id_prefix>

set -a && source .env.local && set +a
unset NOVEL_ANALYZER_LOOM_MEMORY_MODE  # explicit for clarity

python -m novel_analyzer.cli.app writer-imitate-range \
    <branch_id> \
    "1:章节1目标" "2:章节2目标" ... "20:章节20目标" \
    --output-dir output/loom-ab-shadow-<branch_id_prefix> \
    --use-llm --max-rounds 3 \
    > /tmp/loom-ab-shadow.log 2>&1 &
```

Save the PID. Tail `/tmp/loom-ab-shadow.log` for progress lines like
`[N/20] chN done in Xs chars=Y verdict=Z`.

---

## 2. Side B: enabled mode (Loom Phase 1 layered memory)

Use the SAME chapter goals as Side A, write to a sibling directory.

```bash
mkdir -p output/loom-ab-enabled-<branch_id_prefix>

set -a && source .env.local && set +a
export NOVEL_ANALYZER_LOOM_MEMORY_MODE=enabled

python -m novel_analyzer.cli.app writer-imitate-range \
    <branch_id> \
    "1:章节1目标" "2:章节2目标" ... "20:章节20目标" \
    --output-dir output/loom-ab-enabled-<branch_id_prefix> \
    --use-llm --max-rounds 3 \
    > /tmp/loom-ab-enabled.log 2>&1 &
```

**IMPORTANT**: The chapter goals MUST be byte-identical to Side A or the
metric delta gets confounded by goal-content differences. Save the goal
list to a file and reuse:

```bash
python -m novel_analyzer.cli.app writer-imitate-range \
    <branch_id> \
    $(cat /tmp/loom-ab-goals.txt) \
    --output-dir output/loom-ab-enabled-<branch_id_prefix> \
    ...
```

---

## 3. Wait for completion

```bash
# Check both sides are still running:
ps -ef | grep writer-imitate-range | grep -v grep

# Verify chapter file count grows:
watch 'ls output/loom-ab-shadow-*/writer-imitate-ch*.json | wc -l; \
       ls output/loom-ab-enabled-*/writer-imitate-ch*.json | wc -l'
```

Both should reach 20 files. If one side stalls (CTRL-C at ~3-hour mark
suggests provider issues), restart with a different branch as the
experiment will be invalidated by the gap.

---

## 4. Compare metrics

The `loom_ab_comparison_service` does the actual delta computation. No
new CLI command needed — invoke from a 5-line script:

```bash
source .venv/bin/activate
python3 <<'PY'
import json
from pathlib import Path
from novel_analyzer.services.loom_ab_comparison_service import compare_carry_over_modes

def load(d):
    return [
        json.loads(jp.read_text(encoding="utf-8"))
        for jp in sorted(Path(d).glob("writer-imitate-ch*.json"))
    ]

side_a = load("output/loom-ab-shadow-<branch_id_prefix>")
side_b = load("output/loom-ab-enabled-<branch_id_prefix>")

result = compare_carry_over_modes(side_a, side_b)
print("Side A (shadow):", result.side_a)
print("Side B (enabled):", result.side_b)
print("Delta:", result.delta)
for note in result.interpretation:
    print(f"  - {note}")
PY
```

Save the output to `.sisyphus/reports/loom-ab-<branch>-<date>.txt`.

---

## 5. Interpretation thresholds

| Metric | Direction | Pass threshold | Notes |
|---|---|---|---|
| `character_ooc_trigger_rate` | lower | -20pp (kernel-sota target) | The kernel-sota §10 T5 headline claim |
| `avg_overall_score` | higher | +2 points | Marginal — score is bounded [0, 100] |
| `avg_blocking_issues` | lower | -0.5 | A blocking issue prevents the chapter from passing |
| `high_risk_chapter_rate` | lower | -10pp | Reduction signals fewer bad-state generations |
| `pass_verdict_rate` | higher | +5pp | Direct proxy for "fewer manual interventions" |

If the OOC delta hits -20pp, T5 is validated. If it doesn't:

1. **DO NOT lower the threshold** to claim a smaller win. Same lesson as B1
   ai_trace and the bm25 reindex finding (commits `8f24346`, `127ae8c`):
   when the data doesn't show the predicted effect, the claim is wrong, not
   the threshold.
2. Run on a second branch to rule out branch-specific anomaly.
3. If both branches show < -10pp, report that the layered memory does not
   give the predicted delta in the current harness configuration. The
   conclusion is "Loom Phase 1 in current code does not yet justify
   default-on" — useful negative result.

---

## 6. Rollback

The experiment is read-mostly. Side effects:

- Output files in `output/loom-ab-*/` — keep for the report
- Loom Phase 1 writes consolidation rows to `loom_episodic_*` and
  `loom_semantic_*` tables when mode=enabled. These are harmless if not
  consumed; safe to leave.
- The mode env is per-process; no further env management needed.

If the layered memory writes are problematic, drop them via:

```sql
DELETE FROM fact_records
WHERE branch_id = '<branch>' AND episodic_status IS NOT NULL;
```

Rare; only do this if the write volume is materially slowing analysis.

---

## 7. Artifacts to produce

After both sides finish + compare runs:

| Path | Content |
|---|---|
| `output/loom-ab-shadow-<branch>/` | 20 writer-imitate-ch*.json |
| `output/loom-ab-enabled-<branch>/` | 20 writer-imitate-ch*.json |
| `.sisyphus/reports/loom-ab-<branch>-<date>.txt` | compare_carry_over_modes() output |
| `.sisyphus/reports/loom-ab-findings-<date>.md` | Pass/fail vs kernel-sota threshold + lessons |

The findings doc closes T5 in the handoff. Following B1/T1.5 pattern:
write what you found, not what you hoped to find.

---

## 8. Why two branches if budget allows

Single-branch A/B is vulnerable to per-book content variance — for
example, branches with very few named characters will have low OOC rates
on BOTH sides regardless of mode. If LLM budget allows, run 2 branches:

- One with high character density (scifi mapping books typically have
  6-10 named characters)
- One with lower character density (urban / cultivation arcs often have
  3-5 sustained POV characters)

Average the deltas. This rules out "OOC was already low so mode change
didn't matter" as a confound.

---

## 9. Companion docs

- [docs/loom/roadmap.md](../loom/roadmap.md) — Phase 1 design rationale
- [docs/loom/sota-imitation-progression-checklist.md](../loom/sota-imitation-progression-checklist.md)
- [docs/strategy/kernel-sota-gap-assessment-20260514.md](../strategy/kernel-sota-gap-assessment-20260514.md) §10 T5
- `novel_analyzer/services/loom_ab_comparison_service.py` — comparison helper
- `tests/test_loom_ab_comparison_service.py` — unit tests covering interpretation thresholds
