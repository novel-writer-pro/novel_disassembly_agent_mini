# Session Final Handoff — 2026-05-15

> **Purpose**: Single read-once entry point for the next operator picking up after
> this session. Replaces the v1.0-v1.6 sequence in
> `session-handoff-20260514-kernel-and-integration.md` for daily use.
> The old handoff stays as full history; this one is the "what to do Monday" doc.

---

## Current state

- Branch: `v0.2.4` synced with `origin/v0.2.4` (0 ahead, 0 behind)
- Last commit: `247a0a8 docs(handoff): v1.6 — v5.1 broken tests CLOSED`
- Validation: `bash scripts/run-validation.sh --branch <id>` → 6/6 sections pass
- Test surfaces: 114/114 pass across imitation + harness + loom + api_main

### Working-tree state (preserved, NOT my work)

```
M novel_analyzer/cli/app.py                       # parallel session: imitate-chapter mapping_pack
M novel_analyzer/services/chapter_imitation_service.py  # same
?? test.md                                         # user scratch
?? .sisyphus/run-continuation/*.json               # runtime state (gitignored elsewhere)
?? .sisyphus/ralph-loop.local.md                   # runtime state
```

DO NOT discard. The 2 modified files are mid-flight mapping_pack support for the
`imitate-chapter` CLI command (not the `writer-imitate-range` flow which already
ships it). Likely a different operator is finishing this. Per AGENTS.md, hands off.

---

## What's done (no need to redo)

### Strategic deliverables (4 docs + 1 research)

| Path | What |
|---|---|
| `docs/strategy/kernel-sota-gap-assessment-20260514.md` | 6-domain kernel optimization gap matrix |
| `docs/strategy/external-integration-roadmap-20260514.md` | 5-category integration plan (Stage 1/2/3) |
| `docs/strategy/external-integration-checklist-20260514.md` | atomic Stage 1 checklist with verify+rollback |
| `docs/architecture/external-integration-architecture-20260514.md` | layered mermaid architecture (current GA / wired / planned) |
| `docs/research/competing-novel-ai-projects-20260515.md` | 12 GitHub AI-novel projects researched + 5 borrows / 5 rejects + "why low-utility skills get many stars" analysis |

### Code shipped — kernel sprint Week 1-2 (T1-T6)

| Task | Commit | Result |
|---|---|---|
| T1 jieba userdict validator | `ae16931` | sentence-shaped labels rejected; 7000+ → 2627 valid terms |
| T1.5 bm25-reindex executed | `127ae8c` | 891 rows rewritten; finding: +20-30% claim **falsified**, real delta 0pp on proper-noun benchmark — correctness fix only |
| T2 Helicone doctor + runbook | `26952d0` | scripts/dev/helicone-doctor.py 7 checks |
| T2.5 Runbook accuracy | `ba86531` | clone branch fixed (v1→main), web port (8586→3000), profiles documented |
| T3 risk_audit_service split | `80971ee` | 2156 → 365 + 1854 (9 GateChecker classes extracted) |
| T4 imitation_harness split | `03daf85` | 8 pure helpers extracted to imitation_harness_helpers.py |
| T6 contextual chunk prefix | `77670c4` | flag-gated, default off; ready for A/B |

### Code shipped — borrow items (5 pure-function helpers, all ready)

| Borrow | Module | Status |
|---|---|---|
| B1 AI-trace heuristic | `novel_analyzer/services/ai_trace_signal_service.py` | DIAGNOSTIC ONLY — validation showed B1 inverted vs verdict (`8f24346`); NOT to be wired as gate |
| B4 mechanical slop scorer | `novel_analyzer/services/slop_scorer_service.py` | DIAGNOSTIC ONLY — effect size below noise floor on harness output |
| B5 Elo tournament | `novel_analyzer/services/elo_tournament_service.py` | ready for wiring; needs DB schema decision |
| T7 FActScore-lite | `novel_analyzer/services/factscore_lite_service.py` | scoring half ready; LLM claim-extraction prompt half blocked by v5 prompts.py freeze |
| T8 Persona correlation | `novel_analyzer/services/persona_correlation_service.py` | ready; needs ≥30 reader_feedback rows (currently 6) |
| T5 Loom A/B | `novel_analyzer/services/loom_ab_comparison_service.py` + runbook | ready; needs ~20h LLM budget |

### Cascade bug fixes (discovered during validation, real prod issues)

5 sites filtering `is_scaffold_only=True` drafts so outline text doesn't leak
into next-chapter prompt context. Fixed: `db2a179` / `a7d43a3` / `d29d771`.

### Operator-facing tooling

| Path | What |
|---|---|
| `docs/runbook/deployment-and-operations-manual-20260515.md` | 1038-line from-zero deploy + daily ops (single-read) |
| `docs/runbook/bm25-jieba-reindex.md` | BM25 dictionary refresh procedure |
| `docs/runbook/helicone-enable.md` | Helicone proxy enable (real upstream layout) |
| `docs/runbook/loom-ab-experiment.md` | Loom A/B run procedure |
| `scripts/run-validation.sh` | 6-section validation suite, --quick / --branch flags |
| `scripts/dev/helicone-doctor.py` | 7-check Helicone readiness diagnostic |
| `scripts/dev/heuristic-scorer-benchmark.py` | B1/B4 distribution + alert outliers |

### v5.1 broken tests CLOSED (this session, last)

`tests/test_api_main.py` 67/67 pass (was 27 fail / 40 pass at session start).
Path: `fe42daf` (wave 1: StaticPool + monkeypatch re-export + handler contract)
+ `28f9f28` (wave 2: recovery handler / multipart migration / doc-drift / README).
All preserved-but-uncommitted v5.1 state from prior session is now committed.

---

## What's NOT done (and why)

### Genuinely external blockers — operator action required

| Item | What's blocking | When you can do it |
|---|---|---|
| **T2.5 Helicone container start** | 4-5 GB memory + 10-15 GB disk commit; operator decision | Run `cd infra/helicone/upstream/docker && ./helicone-compose.sh helicone up`. Wait 60s. `python scripts/dev/helicone-doctor.py` should exit 0 |
| **T5 Loom A/B run** | ~20h LLM budget (150 calls/ch × 20 ch × 2 sides) | Follow `docs/runbook/loom-ab-experiment.md` step-by-step |
| **T7 FActScore-lite end-to-end** | v5 `prompts.py` freeze decision | Lift freeze → add `build_qa_atomic_claim_extraction_prompt()` → wire qa_service shadow mode |
| **T8 Persona correlation real run** | reader_feedback table has 6 rows (need ≥30) | Wait for Reader Studio adoption; meanwhile `correlate_personas_with_feedback()` runs on synthetic data fine |
| **B2 relationship dim in retrieval** | needs live retrieval testing | Add `_relationship_route()` to ContextService when DB write window is clean |
| **B3 arc-rolling planning** | multi-day; new schema field on RunBranch + Architect agent stage | Open a separate plan: `kernel-7week-arc-rolling.md` |

None of these are "if you have time". They're "if you have $RESOURCE":

- T2.5 needs disk + memory commit
- T5 needs LLM API budget
- T7 needs a freeze-lift decision
- T8 needs accumulated user data
- B2/B3 need uninterrupted DB time

---

## Honest mistakes captured (do NOT repeat)

1. **B1 was inverted, not a quality signal.** First validation pass showed
   `pass_verdict_mean=0.201 > needs_revision_mean=0.184`. The dominant
   ngram_repetition component tracks narrative density (more named entities
   = more repetition = "AI-flavored" by my metric, but ALSO = better draft).
   See `docs/research/heuristic-scorer-validation-findings-20260515.md`.

2. **T1.5 +20-30% claim was unfounded.** Pre/post-reindex MRR is byte-identical
   on all 3 sample branches. Real fix is correctness-on-tail (sentence-shaped
   userdict entries no longer collapse into single tokens), not recall-on-common.
   See `.sisyphus/reports/bm25-reindex-validation-findings-20260515.md`.

3. **"Inspired by N-star repo X" doesn't transfer between harnesses.** The inkos
   33-dim audit lives in a different harness; their dimensions might not be
   redundant with their main pipeline. Ours are. ALWAYS run a baseline before
   promising a delta.

4. **Scaffold flag means nothing if downstream doesn't check it.** Producer set
   `final_draft.is_scaffold_only=True` correctly; 5 downstream consumers
   (loom signal extractor / multi-chapter consistency / whole-book carry-over /
   whole-book draft excerpt / writer router) silently fed scaffold text into
   next-chapter prompts. Always audit cascade.

---

## Recommended next actions (pick one)

### Option A: B5 Elo wiring into pairwise_eval_service

**Cost**: ~1 day  
**Blocker**: DB schema decision (new column or reuse?)

Add Elo delta tracking to `pairwise_eval_service.evaluate()`. Schema options:
- Reuse: store Elo per-variant in `loom_pairwise_evaluations.metadata_json`
- New: add `elo_rating_after` column to `loom_pairwise_evaluations`

Code path: `from novel_analyzer.services.elo_tournament_service import compute_elo`
already wired and tested. Just need a CLI command + DB read/write surface.

### Option B: Resume v5 final cutover (retire WSGI fallback)

**Cost**: ~half day  
**Blocker**: none (just hadn't been done)

Currently `apps/api/app/main.py` still has 1 WSGI dispatch path
(`/api/review-batch-execute` 404 fallback). The actual handler is now in
`apps/api/app/routers/risk_review.py`. Removing the WSGI dispatch:

1. Delete the `if path == "/api/review-batch-execute"` block in main.py
2. Drop `application` callable export
3. Remove `make api-wsgi-legacy` Makefile target
4. Update CHANGELOG

### Option C: Coordinate with parallel session on mapping_pack rollout

**Cost**: ~half day  
**Blocker**: depends on what the parallel session is doing

The 2 working-tree modified files (`cli/app.py` + `chapter_imitation_service.py`)
add `--world-map / --character-map / --power-map / --rule-override` flags to
`imitate-chapter` CLI + `mapping_pack` parameter to `iterate_draft`. This
matches the `writer-imitate-range` flow that already shipped (commits
`9eb30e3` / `35798f4`). The next operator should:

1. Check `git log --since="6 hours ago" --all --oneline`  
2. Find the parallel branch / commit author
3. Either coordinate completion or rebase onto stable

### Option D: Stop. Genuinely nothing to do without external input.

If none of A-C apply, the system is in a clean state. Push none, pull none,
walk away. Next operator opens issues for T2.5/T5/T7/T8 with explicit
unblock criteria as ticket descriptions.

---

## Quick command reference

```bash
# Verify state
cd /home/user/ai-books
source .venv/bin/activate
git status -s | head -10                                    # Should show only parallel-session files
git rev-list --left-right --count origin/v0.2.4...HEAD      # Should be 0/0
bash scripts/run-validation.sh --quick                       # 4 sections in ~3 min

# Health check
python scripts/dev/helicone-doctor.py                        # exit 1 (proxy not running, expected)
python scripts/dev/tei-doctor.py                             # only if you use TEI backend
PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d novel_analyzer  -c "SELECT count(*) FROM run_branches;"

# Start dev stack
make api-dev                                                  # backend :8011
cd apps/web && pnpm dev                                       # frontend :4173
```

---

## Crucial reading order for new operator

1. `docs/runbook/deployment-and-operations-manual-20260515.md` (the deploy bible)
2. This doc (`session-handoff-20260515-final.md`)
3. `docs/strategy/kernel-sota-gap-assessment-20260514.md` (what's the kernel's optimization gap)
4. `docs/strategy/external-integration-roadmap-20260514.md` (where we're going)
5. `docs/research/competing-novel-ai-projects-20260515.md` (what others are doing)
6. `docs/research/heuristic-scorer-validation-findings-20260515.md` (the B1 lesson)
7. `.sisyphus/reports/bm25-reindex-validation-findings-20260515.md` (the T1.5 lesson)
8. `docs/session-handoff-20260514-kernel-and-integration.md` (full session history; reference only)

Estimated: 30-40 min total to be fully briefed.

---

## Modification log

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.0 | 2026-05-15 | 初版,session 完整收尾 |
