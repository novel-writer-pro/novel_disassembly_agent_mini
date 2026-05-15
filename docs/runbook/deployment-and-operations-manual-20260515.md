# Deployment & Operations Manual — 2026-05-15

> **Purpose**: Single comprehensive guide to take a fresh machine to a working novel-analyzer deployment, plus daily operations cookbook. Pulls together the 5 scattered runbooks into one ordered narrative.
> **Audience**: New operator picking up the project; experienced operator looking for a specific command.
> **Companion runbooks** (still valid for symptom-specific deep dives):
> - [bm25-jieba-reindex.md](./bm25-jieba-reindex.md) — BM25 dictionary refresh
> - [helicone-enable.md](./helicone-enable.md) — Helicone proxy enable
> - [loom-ab-experiment.md](./loom-ab-experiment.md) — Loom carry-over A/B
> - [business-loop.md](./business-loop.md) — symptom-driven debugging
> - [v3-pickup-checklist.md](./v3-pickup-checklist.md) — v3-specific pickup
> - [docs/foundation-optimization/pg-jieba-userdict-ops.md](../foundation-optimization/pg-jieba-userdict-ops.md) — pg_jieba ops detail

---

## 0. TL;DR for impatient operators

If you just want to verify the existing deployment works:

```bash
cd /home/user/ai-books
source .venv/bin/activate

# 1. Sanity check the DB
PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d novel_analyzer -tA -c "SELECT count(*) FROM run_branches;"

# 2. Bring up the API (terminal 1, leave running)
make api-dev

# 3. Bring up the frontend (terminal 2, leave running)
cd apps/web && pnpm dev

# 4. Sanity check via HTTP (terminal 3)
curl -fsS http://127.0.0.1:8011/health && echo OK
curl -fsS http://127.0.0.1:8011/api/library | jq '.items | length'

# 5. Run the full unit test suite
pytest tests/test_ai_trace_signal_service.py tests/test_slop_scorer_service.py \
       tests/test_elo_tournament_service.py tests/test_factscore_lite_service.py \
       tests/test_persona_correlation_service.py tests/test_loom_ab_comparison_service.py \
       tests/test_retrieval_service.py tests/test_domain_dictionary_service.py \
       tests/test_imitation_harness_service.py tests/test_chapter_imitation_service.py \
       tests/test_loom_phase2.py -q
```

If all pass, the kernel is healthy. Skip to §6 for the integration matrix or §10 for daily ops.

---

## 1. System topology

```
┌────────────────────────────────────────────────────────────────┐
│                     User-facing surfaces                        │
├────────────────────────────────────────────────────────────────┤
│  Writer Studio (apps/web /writer)  :4173                        │
│  Reader Studio (apps/web /reader)  :4173                        │
│  Workbench     (apps/web /control) :4173                        │
└──────────┬──────────────────┬──────────────────┬───────────────┘
           │                  │                  │
           │ REST + SSE       │ Dify iframe      │ Dify Tools
           ▼                  ▼                  ▼
┌────────────────────────────────────────────────────────────────┐
│               apps/api (uvicorn FastAPI :8011)                  │
│  - IdentityMiddleware (X-User-Id)                              │
│  - 11 routers (loom/writer/quality/library/chapters/...)       │
│  - 1 WSGI fallback path (/api/review-batch-execute)            │
└──────────┬──────────────────┬──────────────────┬───────────────┘
           │                  │                  │
           │ services/*       │ llm/client       │ runtime/notify
           ▼                  ▼                  ▼
┌──────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│ novel_analyzer   │  │ LLM provider    │  │ n8n webhook         │
│ services/* (60)  │  │ (DeepSeek)      │  │ (fire-and-forget)   │
└────┬─────────────┘  │ via Helicone    │  └─────────────────────┘
     │                │ proxy (optional)│
     ▼                └─────────────────┘
┌──────────────────┐  ┌─────────────────┐
│ PostgreSQL 17    │  │ Embedding/Rerank│
│ + pg_trgm        │  │ ONNX local OR   │
│ + pgvector       │  │ TEI HTTP        │
│ + pg_jieba       │  └─────────────────┘
│ :5432            │
└──────────────────┘
```

**Port allocation (changing these requires updating multiple env files):**

| Port | Service | Owner |
|---|---|---|
| 5432 | PostgreSQL | DB container or host PG |
| 8011 | apps/api uvicorn | Always |
| 4173 | apps/web Next.js dev | Dev only |
| 3000 | apps/web Next.js prod | Prod only |
| 8082 | TEI embedding | Optional |
| 8083 | TEI reranker | Optional |
| 8080 | Dify | Stage 1 integration |
| 5678 | n8n | Stage 1 integration |
| 8585 | Helicone Jawn proxy | Stage 1 integration |
| 3000 | Helicone Web UI | Stage 1 integration (collides with apps/web prod — pick one) |
| 3030 | Langfuse Web | Stage 1 integration |

---

## 2. System requirements

| Component | Minimum | Recommended |
|---|---|---|
| OS | Linux x86_64 (Ubuntu 22.04+) | Same |
| Python | 3.11.x exactly | 3.11.x |
| Node | 18.x for apps/web | 20.x |
| pnpm | 8.x | 9.x |
| PostgreSQL | 17.x with extensions: `pg_trgm`, `pgvector`, `pg_jieba` | Same |
| Disk | 20 GB | 50 GB (more if Loom A/B runs accumulate output) |
| Memory | 8 GB | 16 GB (32 GB if running Helicone + Dify locally) |
| GPU | Optional | NVIDIA 8GB+ for TEI |
| Docker | 20.10+ for integrations | 24.x |

**Verify your environment:**

```bash
python3.11 --version       # 3.11.x
node --version             # v18+ or v20+
pnpm --version             # 8+
docker --version           # 20.10+
psql --version             # PostgreSQL 17.x
```

---

## 3. From-zero install (10 phases, ~60 min)

### Phase 1: Clone + Python venv (5 min)

```bash
git clone <repo-url> ai-books
cd ai-books

python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
pip install -r requirements-dev.txt 2>/dev/null || pip install pytest pytest-cov
```

Verify the venv is wired correctly:

```bash
which python    # Should print .../ai-books/.venv/bin/python
python -c "import novel_analyzer; print(novel_analyzer.__file__)"
```

### Phase 2: PostgreSQL (10 min)

Two options. Pick one and stick with it.

**Option A: Docker container (simpler, our standard)**

```bash
docker run -d --name novel-pg \
  -p 5432:5432 \
  -e POSTGRES_USER=d2 \
  -e POSTGRES_PASSWORD=d2pass \
  -e POSTGRES_DB=novel_analyzer \
  -v novel-pg-data:/var/lib/postgresql/data \
  wangqiru/pg_jieba:latest

# Verify (will fail until container fully boots ~10s)
sleep 15
PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d novel_analyzer -c "SELECT version();"
```

**Option B: Host PG with pg_jieba compiled in** — see [pg-jieba-userdict-ops.md §1.2](../foundation-optimization/pg-jieba-userdict-ops.md). More work; only do this if you control the host PG.

Either way, install required extensions:

```bash
PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d novel_analyzer <<SQL
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector
CREATE EXTENSION IF NOT EXISTS pg_jieba;
SELECT extname, extversion FROM pg_extension
WHERE extname IN ('pg_trgm','vector','pg_jieba');
SQL
```

Should print 3 rows.

### Phase 3: env config (5 min)

```bash
cp .env.example .env.local
$EDITOR .env.local
```

Required edits — replace `replace-me`:

```bash
NOVEL_ANALYZER_DB_PASSWORD=d2pass
NOVEL_ANALYZER_LLM_API_KEY=sk-<your-deepseek-key>
NOVEL_ANALYZER_EMBEDDING_MODEL_PATH=/absolute/path/to/bge-m3-onnx
```

Do NOT commit `.env.local` — it's already in `.gitignore`.

### Phase 4: Embedding model (15 min)

DeepSeek doesn't supply embeddings. Two paths.

**Path A: ONNX local (default, no GPU required)**

```bash
mkdir -p .cache/embeddings
huggingface-cli download BAAI/bge-m3 --local-dir /opt/models/bge-m3
huggingface-cli download onnx-community/bge-m3-ONNX --local-dir /opt/models/bge-m3-onnx

# Set the path in .env.local:
sed -i 's|/absolute/path/to/bge-m3-onnx|/opt/models/bge-m3-onnx|' .env.local
```

Smoke test:

```bash
python -m novel_analyzer.cli.app test-embedding
# Expected: prints first few elements of a 1024-dim vector
```

**Path B: TEI HTTP backend (faster, GPU-friendly)**

```bash
make tei-prefetch     # Downloads bge-m3 + bge-reranker-v2-m3 to .cache/tei/
make tei-up           # Starts ghcr.io/huggingface/text-embeddings-inference:cpu containers
make tei-doctor       # 11-check diagnostic; should exit 0
```

Then in `.env.local`:

```bash
NOVEL_ANALYZER_EMBEDDING_BACKEND=http
NOVEL_ANALYZER_EMBEDDING_API_BASE=http://localhost:8082
NOVEL_ANALYZER_EMBEDDING_API_FORMAT=tei
NOVEL_ANALYZER_RERANK_BACKEND=http
NOVEL_ANALYZER_RERANK_API_BASE=http://localhost:8083
NOVEL_ANALYZER_RERANK_API_FORMAT=tei
```

### Phase 5: DB schema (3 min)

```bash
source .venv/bin/activate
python -m novel_analyzer.cli.app init-db
python -m novel_analyzer.cli.app db-health
python -m novel_analyzer.cli.app db-capabilities
```

`db-health` should report HEALTHY. `db-capabilities` should list `pg_trgm`, `pgvector`, `pg_jieba`.

### Phase 6: pg_jieba userdict (5 min)

The userdict gets generated from analysis runs, but you need an initial seed to enable BM25. If you have an existing `output/` directory or pre-analyzed branches:

```bash
python -m novel_analyzer.cli.app domain-dict-rebuild
# Total new: N  dict_size: M
```

Then push the dict into the PG container — see [bm25-jieba-reindex.md §2](./bm25-jieba-reindex.md) for the exact `cp` + `bm25-reindex --confirm` cycle.

If you have NO data yet, skip this — first analysis run will populate the dict.

### Phase 7: Backend (2 min)

```bash
make api-dev
# Listening on http://127.0.0.1:8011

# In another terminal:
curl -fsS http://127.0.0.1:8011/health
curl -fsS http://127.0.0.1:8011/api/meta | jq .
```

If `/health` returns `{"ok": true}`, the kernel is up.

### Phase 8: Frontend (5 min)

```bash
cd apps/web
pnpm install
cp .env.local.example .env.local 2>/dev/null || cat > .env.local <<EOF
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8011
EOF
pnpm dev
# Listening on http://127.0.0.1:4173
```

Open browser → `http://127.0.0.1:4173/` → should see the workbench page.

### Phase 9: First import + analysis (10 min)

You need a sample novel text file. Use any plain-text Chinese novel
(e.g. download from Project Gutenberg-zh, copy a public-domain wuxia
chapter, or use your own draft):

```bash
mkdir -p tmp
cat > tmp/sample-novel.txt <<'EOF'
第1章 觉醒

卫图睁开眼睛，看到的是一个完全陌生的世界...

（接续约 2000 字的章节内容）
EOF
```

Then ingest and analyze:

```bash
python -m novel_analyzer.cli.app ingest tmp/sample-novel.txt --title "测试小说"
# Output: novel_id=...  manifest_id=...

python -m novel_analyzer.cli.app start-run <novel_id> <manifest_id>
# Output: run_id=...  branch_id=...

python -m novel_analyzer.cli.app analyze-range <branch_id> 1 1
# Runs analysis on chapter 1
```

Verify:

```bash
PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d novel_analyzer -tA -c \
  "SELECT count(*) FROM chapter_artifacts WHERE branch_id = '<branch_id>';"
# Expected: 1
```

### Phase 10: Smoke test the full pipeline (5 min)

```bash
# Run the full in-scope test suite
pytest tests/test_ai_trace_signal_service.py \
       tests/test_slop_scorer_service.py \
       tests/test_elo_tournament_service.py \
       tests/test_factscore_lite_service.py \
       tests/test_persona_correlation_service.py \
       tests/test_loom_ab_comparison_service.py \
       tests/test_retrieval_service.py \
       tests/test_domain_dictionary_service.py \
       tests/test_imitation_harness_service.py \
       tests/test_chapter_imitation_service.py \
       tests/test_loom_phase2.py \
       tests/test_scaffold_carry_over_filter.py \
       tests/test_loom_signal_scaffold_filter.py \
       tests/contract/ \
       tests/e2e/test_llm_base_url_override.py \
       -q
```

Expected: all pass in ~3 minutes. If any fail, see §11 troubleshooting.

---

## 4. Daily operations cookbook

### Start the stack

```bash
cd /home/user/ai-books
source .venv/bin/activate

# Backend (terminal 1)
make api-dev

# Frontend (terminal 2)
cd apps/web && pnpm dev

# Watch backend logs (terminal 3)
tail -f /tmp/ai-books-api.log    # if you redirected output
# OR just watch terminal 1 directly
```

### Stop the stack

```bash
# Find and kill any uvicorn / next-dev processes
pkill -f 'uvicorn.*apps.api'
pkill -f 'next dev'

# DB container stays up; only stop if explicitly tearing down
docker stop novel-pg
```

### Health check

```bash
curl -fsS http://127.0.0.1:8011/health           # Backend
curl -fsS http://127.0.0.1:8011/api/runtime-health | jq .
curl -fsS http://127.0.0.1:8011/api/provider-health | jq .  # LLM/embedding probes
```

### Common CLI commands

```bash
source .venv/bin/activate
python -m novel_analyzer.cli.app --help    # Lists all 80+ commands

# Library
python -m novel_analyzer.cli.app list-novels
python -m novel_analyzer.cli.app list-runs <novel_id>
python -m novel_analyzer.cli.app list-branches <run_id>

# Ingest + analysis
python -m novel_analyzer.cli.app ingest <path-to-novel.txt> --title "..."
python -m novel_analyzer.cli.app start-run <novel_id> <manifest_id>
python -m novel_analyzer.cli.app analyze-range <branch_id> <start_ch> <end_ch>

# Imitation
python -m novel_analyzer.cli.app writer-imitate-range <branch_id> "1:目标1" "2:目标2" \
    --output-dir output/my-run --use-llm --max-rounds 3

# Loom
python -m novel_analyzer.cli.app loom-status <branch_id>
python -m novel_analyzer.cli.app loom-consolidate <branch_id> --chapter <n>
python -m novel_analyzer.cli.app loom-assemble <branch_id> --chapter <n>
python -m novel_analyzer.cli.app loom-collect-pairs <branch_id>

# Retrieval
python -m novel_analyzer.cli.app retrieval-benchmark <branch_id> \
    --max-queries 50 --output-file .sisyphus/reports/bm25-$(date +%F).json
python -m novel_analyzer.cli.app domain-dict-rebuild

# QA / search (programmatic)
python -m novel_analyzer.cli.app ask-branch <branch_id> "question text"
```

### Heuristic scorer benchmark (validate B1/B4 distribution)

```bash
python scripts/dev/heuristic-scorer-benchmark.py
python scripts/dev/heuristic-scorer-benchmark.py --top 20
python scripts/dev/heuristic-scorer-benchmark.py --include-scaffold   # Audit scaffold drafts
```

### Diagnostic scripts

```bash
python scripts/dev/tei-doctor.py             # TEI embedding/rerank readiness
python scripts/dev/helicone-doctor.py        # Helicone proxy readiness
bash scripts/verify_infra.sh                 # All Stage 1 docker stacks
```

### Database operations

```bash
# Clear cache & re-run benchmark
PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d novel_analyzer <<SQL
SELECT count(*) FROM run_branches;
SELECT count(*) FROM chapter_artifacts;
SELECT count(*) FROM retrieval_documents;
SELECT count(*) FROM fact_records;
SQL

# BM25 reindex (DESTRUCTIVE — see runbook §3.2 pre-flight first!)
python -m novel_analyzer.cli.app bm25-reindex --confirm

# Backup
PGPASSWORD=d2pass pg_dump -h 127.0.0.1 -U d2 -d novel_analyzer \
  -F c -f backup-$(date +%F).dump

# Restore
PGPASSWORD=d2pass pg_restore -h 127.0.0.1 -U d2 -d novel_analyzer \
  --clean --if-exists -F c backup-2026-05-15.dump
```

---

## 5. Stage 1 external integrations

Each integration is **optional and independent**. Skip whichever you don't need. See [docs/strategy/external-integration-checklist-20260514.md](../strategy/external-integration-checklist-20260514.md) for the full Stage 1 acceptance criteria.

### 5.1 Helicone (LLM proxy + trace)

Bring up:

```bash
cd infra/helicone
git clone --depth 1 https://github.com/Helicone/helicone.git upstream
cp upstream/.env.example upstream/.env
cd upstream/docker
./helicone-compose.sh helicone up
```

Configure backend to use it:

```bash
# Add to .env.local:
NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE=http://localhost:8585/v1/openai

# Restart api:
pkill -f 'uvicorn.*apps.api' && make api-dev
```

Verify:

```bash
python scripts/dev/helicone-doctor.py     # Should exit 0
# Open http://localhost:3000 → Requests → see traces appear
```

Tear down:

```bash
cd infra/helicone/upstream/docker
./helicone-compose.sh helicone down -v
```

Full detail: [helicone-enable.md](./helicone-enable.md).

### 5.2 n8n (workflow notifications)

Bring up:

```bash
cd infra/n8n
docker compose up -d
# http://localhost:5678 — admin / novel_n8n_dev
```

Import workflows via UI:

1. Workflows → Import → `infra/n8n/workflows/pipeline-complete-notify.json` → Activate
2. Workflows → Import → `infra/n8n/workflows/daily-eval-report.json` → Activate

Configure backend:

```bash
# Add to .env.local:
N8N_WEBHOOK_PIPELINE_COMPLETE_URL=http://localhost:5678/webhook/pipeline-complete

# Restart api
```

Test:

```bash
# Trigger a pipeline run; n8n executions page should show success
# OR manual webhook test:
curl -X POST http://localhost:5678/webhook/pipeline-complete \
  -H 'Content-Type: application/json' \
  -d '{"branch_id":"test","status":"complete"}'
```

Tear down:

```bash
cd infra/n8n
docker compose down       # Keep data
docker compose down -v    # Drop everything
```

### 5.3 Dify (Writer Copilot)

Bring up:

```bash
cd infra/dify
git clone --depth 1 https://github.com/langgenius/dify.git upstream
cd upstream/docker
cp .env.example .env
docker compose up -d
# http://localhost:8080
```

UI setup:

1. Sign up locally at `http://localhost:8080`
2. Import: Studio → Create App → Import DSL → upload `infra/dify/apps/writer-copilot.dsl.yml`
3. Tools → Custom → Import → upload `infra/dify/apps/novel-analyzer-tools.openapi.yaml`
   - Set API Base = `http://host.docker.internal:8011`
4. Get the App API Token

Configure frontend:

```bash
# Add to apps/web/.env.local:
NEXT_PUBLIC_DIFY_BASE_URL=http://localhost:8080
NEXT_PUBLIC_DIFY_WRITER_COPILOT_TOKEN=app-xxxxxxx
```

Restart `pnpm dev`. Visit `/writer/<branch_id>` → Copilot iframe should load.

Tear down:

```bash
cd infra/dify/upstream/docker
docker compose down -v
```

### 5.4 Langfuse (observability for Dify-app traffic)

Bring up:

```bash
cd infra/langfuse
git clone --depth 1 --branch v3.0.0 https://github.com/langfuse/langfuse.git upstream
cd upstream
cp .env.dev.example .env
docker compose up -d
# http://localhost:3030
```

UI setup:

1. Sign up
2. Create org → project
3. Settings → API Keys → Create → save PUBLIC + SECRET

Wire to Dify:

1. Dify Settings → Monitoring → Langfuse
2. Paste keys + base URL `http://host.docker.internal:3030`
3. Save → status should show connected

Tear down:

```bash
cd infra/langfuse/upstream
docker compose down -v
```

---

## 6. End-to-end smoke test (after integrations are up)

This validates the full Stage 1 chain: alice/bob isolation + Dify + Helicone + n8n + Langfuse.

```bash
# 1. Two-user library isolation
curl -X POST -H "X-User-Id: alice" -F file=@tmp/alice-book.txt http://127.0.0.1:8011/api/import
curl -H "X-User-Id: alice" 'http://127.0.0.1:8011/api/library' | jq '.items | length'   # >=1
curl -H "X-User-Id: bob"   'http://127.0.0.1:8011/api/library' | jq '.items | length'   # 0

# (uses tmp/alice-book.txt from Phase 9 above; create another tmp/bob-book.txt for the bob side if needed)

# 2. Imitation run (will fan trace to Helicone if proxy is on)
curl -X POST -H "X-User-Id: alice" -H "Content-Type: application/json" \
  -d '{"branch_id":"<branch_id>","chapter_index":1,"goal":"测试仿写"}' \
  http://127.0.0.1:8011/api/whole-book-imitation-run

# 3. Verify n8n got the webhook
curl -u admin:novel_n8n_dev \
  'http://localhost:5678/api/v1/executions?workflowId=pipeline-complete-notify' \
  | jq '.data[0] | {status, startedAt}'

# 4. Verify Helicone trace
curl -fsS http://localhost:8585/healthcheck && echo Helicone healthy
# Open http://localhost:3000 → Requests → at least 1 row

# 5. Verify Langfuse received Dify trace (after using Dify Writer Copilot in browser)
curl -u <PUB>:<SEC> 'http://localhost:3030/api/public/traces?userId=alice&limit=5' | jq .
```

Full procedure: [business-loop.md](./business-loop.md).

---

## 7. Validation suite (pre-prod sanity)

Run before any major change or after pulling new commits. The
`scripts/run-validation.sh` helper bundles the 6 sections below
into one command:

```bash
bash scripts/run-validation.sh                          # full suite (~10 min)
bash scripts/run-validation.sh --quick                  # sections 1-4 only (~3 min)
bash scripts/run-validation.sh --branch <branch_id>     # adds BM25 sanity check
```

Equivalent manual sequence (each section is independent):

```bash
source .venv/bin/activate

# 1. Heuristic scorer regression (B1/B4/B5/T7/T8/T5)
pytest tests/test_ai_trace_signal_service.py tests/test_slop_scorer_service.py \
       tests/test_elo_tournament_service.py tests/test_factscore_lite_service.py \
       tests/test_persona_correlation_service.py tests/test_loom_ab_comparison_service.py -q

# 2. Scaffold cascade regression
pytest tests/test_loom_signal_scaffold_filter.py tests/test_scaffold_carry_over_filter.py -q

# 3. Kernel service tests
pytest tests/test_retrieval_service.py tests/test_domain_dictionary_service.py \
       tests/test_imitation_harness_service.py tests/test_chapter_imitation_service.py \
       tests/test_loom_phase2.py -q

# 4. Contract tests (FastAPI canonical surface)
pytest tests/contract/ -q

# 5. E2E tests
pytest tests/e2e/test_llm_base_url_override.py tests/e2e/test_owner_scoping_e2e.py \
       tests/e2e/test_anti_spoiler.py -q

# 6. BM25 jiebacfg vs simple distribution sanity
python -m novel_analyzer.cli.app retrieval-benchmark <any_branch_with_data> \
    --max-queries 20 --output-file /tmp/bm25-sanity.json
# Inspect: jiebacfg MRR should be > simple MRR
```

If anything fails, the change is not ready to ship.

---

## 8. Production readiness checklist

For when you actually deploy this somewhere users will hit it.

### 8.1 Security

- [ ] `.env.local` does NOT contain `replace-me` strings
- [ ] PG password is NOT `d2pass` in production (rotate before exposing the host)
- [ ] n8n basic auth is NOT `admin / novel_n8n_dev`
- [ ] Dify admin password rotated
- [ ] Langfuse admin password rotated
- [ ] Helicone admin password rotated
- [ ] All integration containers bind to `127.0.0.1` only, NOT `0.0.0.0` (verify with `ss -tlnp`)
- [ ] If exposing the API publicly: front it with nginx + TLS + basic auth at minimum
- [ ] `IdentityMiddleware` is wired (verify `apps/api/app/fastapi_app.py` includes it)
- [ ] Sample books removed from any public-facing dir

### 8.2 Resource limits

- [ ] Disk monitoring on the PG volume (alert at 80% full)
- [ ] Helicone ClickHouse pruning policy (kept rows < 30 days for cost)
- [ ] Langfuse PG pruning policy
- [ ] Output dir pruning policy (`output/` can grow 50MB/imitation run)
- [ ] LLM provider rate-limit budget configured
- [ ] DeepSeek API key has billing limits set

### 8.3 Backup

- [ ] `pg_dump` runs nightly via cron, retained 7 days
- [ ] `.cache/novel-analyzer/jieba-user-dict.txt` backed up (regeneratable but slow)
- [ ] LLM provider keys backed up out-of-band
- [ ] DR drill: verify `pg_restore` works on a fresh container

### 8.4 Observability

- [ ] Helicone trace covers ≥80% of LLM calls (run a 1-hour sample, count Helicone rows / `llm/client.py` invocations)
- [ ] Langfuse trace covers Dify Copilot calls
- [ ] API access log captures `X-User-Id` header
- [ ] Slow query log enabled on PG (`log_min_duration_statement = 500`)

### 8.5 Verification before declaring "live"

- [ ] §7 validation suite passes 100%
- [ ] §6 end-to-end smoke executes without error on the prod env
- [ ] At least 1 real user has done 1 chapter ingest + analysis + imitation cycle
- [ ] Rollback path tested: `unset NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE` + restart works
- [ ] CHANGELOG.md updated with deployment date + version

---

## 9. Disaster recovery

### 9.1 PG container died, no backup

If `docker volume ls | grep novel-pg-data` still shows the volume, the data is intact:

```bash
docker rm novel-pg                                  # Remove dead container
docker run -d --name novel-pg -p 5432:5432 ... -v novel-pg-data:/var/lib/postgresql/data wangqiru/pg_jieba:latest
# Same env vars as Phase 2; volume reattaches
```

If the volume is gone:

```bash
PGPASSWORD=d2pass pg_restore -h 127.0.0.1 -U d2 -d novel_analyzer \
  --clean --if-exists -F c .backup/backup-<latest>.dump
```

### 9.2 Helicone proxy crashed, all imitation broken

Emergency fallback (no LLM trace, but business recovers):

```bash
# Edit .env.local, comment out:
# NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE=http://localhost:8585/v1/openai

# Restart api
pkill -f 'uvicorn.*apps.api' && make api-dev
```

LLM calls now go direct to provider. Diagnose Helicone separately:

```bash
docker logs --tail 100 helicone-jawn 2>&1
docker compose -f infra/helicone/upstream/docker/docker-compose.yml ps
```

### 9.3 bm25_vector corrupted

Symptom: BM25 queries return zero results.

```bash
# Verify the column expression
PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d novel_analyzer -tA -c "
SELECT pg_get_expr(d.adbin, d.adrelid)
FROM pg_attribute a
JOIN pg_attrdef d ON a.attrelid = d.adrelid AND a.attnum = d.adnum
WHERE a.attrelid='retrieval_documents'::regclass AND a.attname='bm25_vector';"

# Should return: to_tsvector('jiebacfg'::regconfig, COALESCE(bm25_text, ''::text))

# If wrong, re-run reindex (see runbook §3.2 pre-flight first!):
python -m novel_analyzer.cli.app bm25-reindex --confirm
```

### 9.4 Long-running writer-imitate-range stuck

Symptom: `ALTER TABLE` operations queue forever; `pg_stat_activity` shows `idle in transaction` for >30 min.

```bash
# Identify the holder
PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d novel_analyzer -tA -c "
SELECT pid, age(now(), xact_start) AS tx_age, state, left(query,100)
FROM pg_stat_activity
WHERE datname='novel_analyzer' AND xact_start IS NOT NULL
  AND age(now(), xact_start) > interval '30 minutes';"

# Cancel (gentle):
psql -tA -c "SELECT pg_cancel_backend(<pid>);"

# Terminate (force, last resort):
psql -tA -c "SELECT pg_terminate_backend(<pid>);"
```

If a CLI process owns the transaction:

```bash
ps aux | grep cli.app | grep -v grep
kill -INT <pid>      # SIGINT — allows graceful cleanup
kill -TERM <pid>     # If SIGINT didn't work after 30s
```

### 9.5 Scaffold drafts persisted as final_draft

Symptom: chapters with `final_draft.is_scaffold_only=True` appearing in user-facing surfaces.

```bash
# Find them
find output -name 'writer-imitate-ch*.json' -exec sh -c '
  jq -e ".final_draft.is_scaffold_only == true" "$1" >/dev/null && echo "$1"
' _ {} \;

# Use the cleaner
python scripts/clean_imitation_drafts.py output/<dir-with-scaffolds>
# Produces *.clean.json + contamination report
```

The downstream consumers in `cli/app.py` and the harness already filter scaffold drafts after `db2a179` + `a7d43a3` — these are NOT user-visible problems anymore. The cleaner is for output-artifact hygiene only.

---

## 10. Recurring maintenance schedule

| Frequency | Task | Command |
|---|---|---|
| Daily | PG backup | `pg_dump -F c -f .backup/$(date +%F).dump` (cron) |
| Daily | n8n daily-eval-report | Auto via n8n schedule |
| Weekly | Heuristic scorer benchmark | `python scripts/dev/heuristic-scorer-benchmark.py > .sisyphus/reports/heuristic-$(date +%F).log` |
| Weekly | Run validation suite | `bash scripts/run-validation.sh` (`--quick` skips e2e+bm25; `--branch <id>` includes BM25 sanity) |
| Monthly | Userdict refresh + reindex | `python -m novel_analyzer.cli.app domain-dict-rebuild && python -m novel_analyzer.cli.app bm25-reindex --confirm` |
| Monthly | Helicone ClickHouse prune | `docker exec helicone-clickhouse clickhouse-client -q "ALTER TABLE request_response_log DELETE WHERE created_at < now() - INTERVAL 30 DAY"` |
| Monthly | Output dir prune | `find output -mtime +60 -name '*.json' -delete` (be careful — keeps recent runs) |
| Quarterly | DR drill | Restore latest `pg_dump` to a scratch container; verify `db-health` passes |
| Quarterly | Re-run heuristic correlation check | `python -c "import .../validate.py"` (the B1-style validation; see [heuristic-scorer-validation-findings-20260515.md](../research/heuristic-scorer-validation-findings-20260515.md)) |

---

## 11. Troubleshooting cookbook

### "ImportError: pg_jieba not found"

```bash
PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d novel_analyzer -c "SELECT extname FROM pg_extension;"
# If pg_jieba is missing:
PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d postgres -c "CREATE EXTENSION pg_jieba;"
```

If the container doesn't have pg_jieba compiled in, switch to the `wangqiru/pg_jieba:latest` image (Phase 2 Option A).

### "ConnectionRefusedError on :8011"

```bash
# Backend not running
ps aux | grep uvicorn | grep apps.api | grep -v grep
# If empty:
make api-dev
```

### "TEI 404 on /embed"

```bash
make tei-doctor
# Most likely: container not started, or model not prefetched
make tei-prefetch && make tei-up
```

### "Library returns empty for valid user"

Check `IdentityMiddleware` is wired:

```bash
grep -n IdentityMiddleware apps/api/app/fastapi_app.py
# Should show:
# from apps.api.app.middleware.identity import IdentityMiddleware
# app.add_middleware(IdentityMiddleware)
```

Check `owner_user_id` was written:

```bash
PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d novel_analyzer -c \
  "SELECT DISTINCT owner_user_id FROM novel_sources;"
# All `local-default` = X-User-Id was not propagated through the ingest chain
```

### "Imitation runs but writer-imitate-ch*.json never appears"

```bash
# Check the writer-imitate-range process
ps -p <pid> -o pid,etime,stat,pcpu

# If running but no output:
tail -f /tmp/imitation.log    # If you redirected
# OR check stdout of the CLI directly

# If stuck in DB lock:
# Follow §9.4 disaster recovery
```

### "Helicone trace empty"

```bash
python scripts/dev/helicone-doctor.py
# Will print exactly which check failed and the fix command
```

### "All tests fail with `RuntimeError: Engine has been disposed`"

You have a stale DB connection from a previous test run. Kill all Python processes:

```bash
pkill -9 -f python
# Re-run tests
```

### Symptom-driven deep dives

For more involved diagnostics, see:

- LLM trace not flowing → [helicone-enable.md](./helicone-enable.md) §8
- Dify Copilot 401/403 → [business-loop.md](./business-loop.md) §症状3
- alice/bob isolation broken → [business-loop.md](./business-loop.md) §症状4
- Scaffold drafts polluting output → §9.5 above
- BM25 expected gain not showing → [bm25-reindex-validation-findings-20260515.md](../../.sisyphus/reports/bm25-reindex-validation-findings-20260515.md)

---

## 12. Cross-references

### 12.1 Strategic docs
- [docs/strategy/kernel-sota-gap-assessment-20260514.md](../strategy/kernel-sota-gap-assessment-20260514.md) — kernel optimization plan
- [docs/strategy/external-integration-roadmap-20260514.md](../strategy/external-integration-roadmap-20260514.md)
- [docs/strategy/external-integration-checklist-20260514.md](../strategy/external-integration-checklist-20260514.md)
- [docs/architecture/external-integration-architecture-20260514.md](../architecture/external-integration-architecture-20260514.md)
- [docs/research/competing-novel-ai-projects-20260515.md](../research/competing-novel-ai-projects-20260515.md)

### 12.2 Findings (lessons learned, do NOT delete)
- [docs/research/heuristic-scorer-validation-findings-20260515.md](../research/heuristic-scorer-validation-findings-20260515.md) — B1 inverted, B4 noise floor
- [.sisyphus/reports/bm25-reindex-validation-findings-20260515.md](../../.sisyphus/reports/bm25-reindex-validation-findings-20260515.md) — T1.5 +20-30% claim falsified

### 12.3 Session handoff
- [docs/session-handoff-20260514-kernel-and-integration.md](../session-handoff-20260514-kernel-and-integration.md) — current state of all open items, including which ones are genuinely external-blocked

### 12.4 Specialized runbooks
- [docs/runbook/bm25-jieba-reindex.md](./bm25-jieba-reindex.md) — BM25 dict refresh procedure
- [docs/runbook/helicone-enable.md](./helicone-enable.md) — Helicone enable detail
- [docs/runbook/loom-ab-experiment.md](./loom-ab-experiment.md) — T5 Loom A/B procedure
- [docs/runbook/business-loop.md](./business-loop.md) — symptom-based troubleshooting
- [docs/runbook/v3-pickup-checklist.md](./v3-pickup-checklist.md) — v3-specific pickup
- [docs/foundation-optimization/pg-jieba-userdict-ops.md](../foundation-optimization/pg-jieba-userdict-ops.md) — pg_jieba install + userdict mgmt

---

## 13. Lessons captured this session

These are not optional reading — they explain WHY the current code/tests look the way they do:

1. **Threshold calibration ≠ signal validation.** Always run a correlation against the outcome variable before claiming a heuristic is a quality gate. (B1 ai_trace was inverted; documented in heuristic-scorer-validation-findings.)
2. **Scaffold drafts must be filtered at every consumer.** Producer-side `is_scaffold_only` flag means nothing if downstream consumers don't check it. (Cascade bug fixed in `db2a179` + `a7d43a3` + `d29d771`.)
3. **Run the baseline before promising the delta.** "+20-30% recall" turned out to be 0pp on the proper-noun benchmark. Real gain came from a different mechanism (tail correctness on long-paragraph queries). (See bm25-reindex-validation-findings.)
4. **"Inspired by N-star repo X" doesn't transfer.** Their harness is not your harness. Validate on YOUR data before promoting their idea to a production gate.
5. **Pure-function helpers cost almost nothing; wiring claims are what cost.** Ship as standalone scoring helpers + tests + smoke + runbook. Wire later when data justifies it.
6. **Re-examine "deferred" items aggressively.** Twice this session a "deferred" item turned out partially actionable.

---

## 14. Quick command reference card

Print + tape to your monitor.

```bash
# Start
make api-dev                                                       # Backend :8011
cd apps/web && pnpm dev                                            # Frontend :4173

# Stop
pkill -f 'uvicorn.*apps.api'; pkill -f 'next dev'

# Health
curl http://127.0.0.1:8011/health
python -m novel_analyzer.cli.app db-health

# Test
pytest tests/test_*_service.py -q

# Diagnostic
python scripts/dev/tei-doctor.py
python scripts/dev/helicone-doctor.py
python scripts/dev/heuristic-scorer-benchmark.py

# DB ops
PGPASSWORD=d2pass pg_dump -h 127.0.0.1 -U d2 -F c -f .backup/$(date +%F).dump novel_analyzer
python -m novel_analyzer.cli.app domain-dict-rebuild
python -m novel_analyzer.cli.app bm25-reindex --confirm   # DESTRUCTIVE — pre-flight first

# Imitation run
python -m novel_analyzer.cli.app writer-imitate-range <branch_id> "1:goal" "2:goal" \
    --output-dir output/run-$(date +%F) --use-llm --max-rounds 3

# Loom A/B
# See docs/runbook/loom-ab-experiment.md

# BM25 benchmark
python -m novel_analyzer.cli.app retrieval-benchmark <branch_id> --max-queries 50 \
    --output-file .sisyphus/reports/bm25-$(date +%F).json
```
