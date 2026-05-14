## Summary

Take novel-analyzer from "internal analyst workbench" to "framework-first commercial-ready" by **leveraging existing OSS platforms instead of self-building**, while keeping the existing WSGI service untouched.

- **Dify** replaces hand-rolled chat UI, prompt versioning, and Langfuse SDK plumbing
- **n8n** handles outer-orchestration (notifications, daily reports)
- **Langfuse** receives traces via Dify built-in integration (zero business-code touch)
- New `/writer/*` route group with editor-first UX, isolated from legacy Workbench shell
- DB-level multi-user scoping via `owner_user_id` (additive migration, no breaking changes)
- `imitation` pipeline schema frozen with CI lint to prevent further accumulation

## What's Done (17/23 plan tasks)

| Wave | Tasks | Status |
|------|-------|--------|
| Foundation | T1 Contract baseline · T2 Trace context | Done, 41/41 tests |
| Infra | N1 Dify · N2 n8n · N3 Langfuse self-host | docker-compose YAMLs + READMEs ready |
| Data | T22 owner_user_id migration · T7 Audit · T17 Freeze lint | 5/5 isolation + 215 fields cataloged |
| UI | T4 /writer/* · T13 Editor · T14 Loom panel · N8 Dify iframe | Next.js build clean |
| Eval | N9 Promptfoo · N10 Helicone vs Langfuse · N11 FastGPT memo | Decision docs |
| Verify | F1 Zero-regression APPROVE · F4 Scope fidelity APPROVE · F3 partial | Evidence in `.sisyphus/evidence/` |

## What's Pending (6/23, all docker-blocked)

Manual UI configuration tasks that require running stacks. **`make v2-pickup-checklist`** prints the step-by-step procedure (~30 min total).

| Task | What |
|------|------|
| N4 | Dify Writer Copilot app (DSL pre-staged) |
| N5 | Langfuse keys → Dify Monitoring |
| N6, N7 | n8n workflow imports (JSON pre-staged) |
| F2 | `bash scripts/verify_infra.sh` after `make v2-up-all` |
| F3 | Playwright run against running iframe (spec ready) |

## Zero-Regression Guarantees (verified)

- `apps/api/app/main.py`: **0 lines changed** (still 2630)
- `novel_analyzer/services/`: **0 lines changed**
- `langfuse`/`dify` imports in business code: **0**
- `trace_context` imports in business code: **0** (intentionally not yet wired)
- 28/28 contract assertions, 13/13 trace_context tests, 5/5 owner_scoping tests
- Next.js production build clean, 0 TypeScript errors
- Bundle isolation verified: `/writer/*` 226 kB First Load vs `/control` 417 kB

## Rejected Alternatives

- ~~FastAPI cutover~~ — deferred; existing WSGI works
- ~~Custom AI chat UI / SSE client~~ — Dify already does this well
- ~~Langfuse SDK in business code~~ — Dify built-in integration is zero-touch
- ~~PostgreSQL row-level security~~ — overkill for internal-only multi-user

## Test Plan

Already passing locally:
```bash
make v2-test    # 46/46 backend
make v2-build   # Next.js prod build
make v2-lint    # No new session_* fields
make v2-audit   # Re-generate field census
```

CI workflows added in `.github/workflows/` will run these on every PR touching the relevant paths.

## Pickup Path for the 6 Pending

Reviewer can verify the full v2 path on a docker-enabled host:

```bash
make v2-pickup-checklist  # See full procedure
make v2-up-all            # bring up dify + n8n + langfuse
bash scripts/verify_infra.sh  # marks F2 done
# then 4 short manual UI steps for N4/N5/N6/N7
# then npx playwright test  # marks F3 done
```

## Risk Assessment

- **Low**: All changes are additive. Nothing existing breaks.
- **Medium for T22 migration**: Adds NOT NULL column with DEFAULT, idempotent, downgrade tested.
- **Pending validation**: Docker stacks not yet run end-to-end on this host (env limitation). All YAMLs/JSONs syntax-validated.

## Commits in This PR

```
de5ffde  Loosen quality-dashboard contract: endpoint may not exist on master
37e0648  Strip TEI Makefile targets — orphaned by cherry-pick onto master
3c0862f  Wire CI gates and pickup automation for v2 framework migration
ebea80e  Document framework selection and stage prompt-regression test suite
654b94a  Add /writer/* route group with editor-first UI for Writer Studio MVP
48fd59c  Self-host Dify, n8n, Langfuse for framework-first commercialization
d57bcf9  Freeze imitation session_* schema and stop further field accumulation
2eb30c1  Scope library tables by owner_user_id for internal multi-user dogfood
22c21e0  Reserve a request-scoped trace context shape for future middleware
f208b0b  Lock current WSGI contract before any framework migration
```

