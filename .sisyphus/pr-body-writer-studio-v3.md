## Summary

Closes the v2 retro gaps: imitation main flow now has trace coverage, n8n actually receives completion events, owner_user_id finally filters something, and Dify forwards user identity to the backend. Six commits, all atomic, all behind feature flags or env switches — zero behavior change for callers that don't opt in.

## What Changed

| Commit | Effect |
|--------|--------|
| ffcfa9b — IdentityMiddleware | ASGI middleware that reads `X-User-Id` / `X-Request-Id` headers into v2's `RequestContext`. Self-contained module — wires into a FastAPI surface when one lands. |
| f5d8168 — owner_user_id wiring | `RunService.create_run`, `IngestService.ingest_text_file/list` accept `owner_user_id` (default "local-default"). `_library_payload` filters by it. `/api/library` reads `HTTP_X_USER_ID` from WSGI environ. |
| 6535845 — Dify Custom Tool header | OpenAPI for the 3 tools declares `X-User-Id` header parameter; DSL pre_prompt reminds the model to forward it; README walks through the Dify Studio UI mapping step. |
| eb02fdc — n8n fire-and-forget hook | `notify_pipeline_complete()` posts run metadata to `$N8N_WEBHOOK_PIPELINE_COMPLETE_URL`; 2s timeout, all errors swallowed. Wired into `WholeBookImitationService.run_in_sandbox()` final return. |
| e70caf7 — Helicone via env override | `Settings.llm_base_url_override` (env: `NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE`) wins over `resolved_llm_base_url` in `build_chat_model()`. Zero business-code Helicone imports. |
| 9459733 — Runbook + smoke target | `docs/runbook/business-loop.md` with 6-step manual smoke + 5 troubleshooting symptoms. `make v3-smoke` runs the docker-free portion (21 tests in 11s). |

## Zero-Regression Guarantees

- `apps/api/app/main.py` dispatch table: **0 lines changed** (only `_library_payload` helper + 1 line inside the `/api/library` branch)
- `apps/api/app/main.py` total: 2497 → 2503 (+6 lines, well under the +10 ceiling)
- `novel_analyzer/llm/prompts.py`: **0 lines changed**
- `novel_analyzer/workflows/run_graph.py`: **0 lines changed**
- `novel_analyzer/services/whole_book_imitation_service.py`: 18 lines (+/-) — exactly the 2-import + 12-line hook block at the function tail
- Business code Langfuse/Dify/Helicone import count: **0**

## Test Plan

```bash
make v3-smoke        # runs docker-free e2e (21 tests / 11s)
make v2-test         # full v2 suite still 46/46
.venv/bin/pytest tests/contract/ tests/runtime/ tests/test_owner_scoping.py \
  tests/api/ tests/e2e/ tests/test_run_service.py \
  tests/test_application_layer.py tests/test_whole_book_imitation_service.py
# 92 passed, 0 failed
```

Manual end-to-end (gated on docker stacks): see `docs/runbook/business-loop.md` step 1-6.

## Rejected Alternatives

- ~~Move imitation prompts into Dify Prompt Studio~~ — user explicitly chose "代码里保留" in v3 interview
- ~~Wrap ChatOpenAI with Langfuse callback handler~~ — adds SDK to client.py, breaks zero-import rule
- ~~Async background task for n8n notify~~ — gratuitous event-loop coupling for a fire-and-forget POST
- ~~Skip the runbook and rely on architectural prose~~ — v2 retro showed prose alone doesn't help operators verify

## Pre-conditions for Manual Verification (deferred to operator)

- v2 PR (#8) merged into master ✅ (already done)
- Dify / n8n / Langfuse / Helicone stacks running on operator host
- N4-N7 manual UI configurations completed (per v2 pickup-checklist)
- `apps/web/.env.local` has `NEXT_PUBLIC_DIFY_WRITER_COPILOT_TOKEN` set

When all four are true, the 6-step smoke in `docs/runbook/business-loop.md` walks through the closed loop and reports on each subsystem.

## Limitations Documented in Runbook

- `owner_user_id` scoping currently applies only to `/api/library`; other endpoints still return data to any caller. Closing this gap requires the FastAPI surface and Depends-based identity injection — deferred to a future PR.
- Helicone trace and Langfuse trace are two separate UIs; merging into one feed is a v4 candidate.
- `trace` coverage is gated on callers using `build_chat_model()`. Direct `from openai import` would bypass the proxy. Grep across the repo confirms no such direct imports exist today.

## Commits

```
9459733  Document end-to-end business loop with troubleshooting runbook
e70caf7  Allow LLM base_url override via env so Helicone proxy can intercept
eb02fdc  Fire-and-forget n8n notification when imitation pipeline completes
6535845  Forward X-User-Id header from Dify tools to ai-books backend
f5d8168  Wire owner_user_id from X-User-Id header through library listing
ffcfa9b  Add ASGI identity middleware reading X-User-Id into RequestContext
```

22 files changed, +854 / -5
