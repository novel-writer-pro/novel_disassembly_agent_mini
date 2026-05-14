# Helicone Proxy Enable Runbook

> **Goal**: Enable transparent LLM trace for `novel_analyzer/llm/client.py` direct calls
> (imitation, analysis, QA — the bulk of LLM traffic that Dify-internal Langfuse never sees).
> **Effort**: ~30 min including container boot + UI walkthrough.
> **Reversibility**: Clean — `unset NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE` + restart.

---

## 0. Pre-flight

```bash
source .venv/bin/activate
python scripts/dev/helicone-doctor.py
```

This prints exactly which boxes are unchecked. Re-run after each step.

---

## 1. Bring up the stack

Helicone v1 self-host has its own docker-compose under `infra/helicone/upstream/`.

```bash
cd infra/helicone

# First time only:
git clone --depth 1 --branch v1 https://github.com/Helicone/helicone.git upstream
cp upstream/.env.example upstream/.env

# Lock ports so they don't collide with Dify (8080) / n8n (5678) / Langfuse (3000)
# Field names vary across Helicone releases — open .env, find the proxy/web port keys
# and set them to 8585 / 8586 manually (or via sed if the keys are stable in your version).

cd upstream
docker compose up -d
docker compose ps  # all services should be healthy or starting
```

Wait ~30s, then:

```bash
curl -fsS http://localhost:8585/healthcheck && echo OK
curl -fsS http://localhost:8586 -o /dev/null && echo "web ok"
```

Both should succeed.

---

## 2. Create org + API key in Helicone UI

1. Open `http://localhost:8586` in the browser.
2. Sign up locally (the dev image typically allows `admin@local` / any password).
3. Settings → API Keys → Create. Save the key (you won't need it for the **default** transparent proxy mode unless your Helicone version requires `Helicone-Auth` header — see step 4).

---

## 3. Configure the override

Add to `.env.local` (or shell session):

```bash
NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE=http://localhost:8585/v1/openai
```

The path-suffix `/v1/openai` is Helicone's "I want OpenAI-compatible upstream" target. The actual upstream URL stays in `NOVEL_ANALYZER_LLM_BASE_URL` (configured per provider) — Helicone forwards there.

If your Helicone version requires authenticated proxy mode, also set:

```bash
HELICONE_API_KEY=<the_key_from_step_2>
```

Then update `novel_analyzer/llm/client.py` to add `Helicone-Auth: Bearer ${HELICONE_API_KEY}` to default headers — this is **optional** and only needed if your install rejects unauthenticated proxy traffic. The default v1 image does not.

---

## 4. Restart the API process

The setting is read at startup via `pydantic-settings`. Whichever process is running:

```bash
# foreground dev:
make api-dev  # uvicorn :8011, reads new .env.local

# OR background-managed:
pkill -f 'uvicorn.*apps.api' && make api-dev
```

---

## 5. Generate one trace

```bash
# Smallest possible smoke — single chapter analysis or a CLI ask
python -m novel_analyzer.cli.app --help  # confirm CLI works
# pick any branch_id with chapters and run a single analysis stage
# (the imitation / analysis pipeline calls build_chat_model() under the hood)
```

Visit `http://localhost:8586` → Requests → expect at least one row with the upstream model name + token counts.

---

## 6. Verify with helicone-doctor

```bash
python scripts/dev/helicone-doctor.py
```

All 7 checks should pass.

---

## 7. Rollback

Single env unset is sufficient — `build_chat_model()` falls back to `resolved_llm_base_url`:

```bash
unset NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE
# OR comment out the line in .env.local
pkill -f 'uvicorn.*apps.api' && make api-dev
```

For full teardown:

```bash
cd infra/helicone/upstream
docker compose down       # stop, keep data
docker compose down -v    # stop, drop ClickHouse + PG volumes
```

---

## 8. Known limits + caveats

- **Latency** — proxy adds 30-80ms P50 typically. If imitation latency P95 jumps > 200ms, fall back via §7.
- **Trace persistence** — Helicone v1 stores in its own ClickHouse. Disk growth can be material on imitation-heavy days; monitor `docker stats helicone-clickhouse-1` and prune old rows monthly.
- **No prompt redaction by default** — full prompt text lands in ClickHouse. If your branches contain real-name PII, enable Helicone request sanitization rules in Settings → Properties before exposing the UI to anyone outside the dev box.
- **Dify trace overlap** — Helicone catches direct LLM calls; Dify's internal Langfuse catches Dify-app calls. The two paths don't intersect, so the same prompt won't be double-counted.

---

## 9. Boundary contract

The proxy is intentionally a thin wrapper:

| Boundary | Owned by |
|---|---|
| Outbound HTTP from `llm/client.py` | Application (`build_chat_model`) |
| Where that traffic lands | env (`*_BASE_URL_OVERRIDE`) |
| Trace storage / dashboard | Helicone container |
| Upstream LLM provider auth | unchanged — `LLM_API_KEY` still flows untouched through the proxy |

The application code knows nothing about Helicone. Removing the env var is the only rollback action.

---

## 10. Companion docs

- [docs/observability/helicone-vs-langfuse.md](../observability/helicone-vs-langfuse.md) — design rationale
- [docs/strategy/external-integration-roadmap-20260514.md](../strategy/external-integration-roadmap-20260514.md) §4 — observability stack decision
- [docs/strategy/external-integration-checklist-20260514.md](../strategy/external-integration-checklist-20260514.md) S1.1 — Stage 1 task tracker
- `infra/helicone/README.md` — bare-bones install notes (this runbook supersedes it for the enable path)
- `scripts/dev/helicone-doctor.py` — diagnostic, run anytime
