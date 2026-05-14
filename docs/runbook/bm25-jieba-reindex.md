# pg_jieba userdict + bm25_reindex Operations

> **Scope**: Step-by-step runbook for activating domain-specific tokenization in BM25 retrieval.
> **Audience**: Operator (you / on-call) — assumes you have sudo + container access.
> **Companion docs**:
> - [docs/foundation-optimization/pg-jieba-userdict-ops.md](../foundation-optimization/pg-jieba-userdict-ops.md) — full background
> - [docs/strategy/kernel-sota-gap-assessment-20260514.md](../strategy/kernel-sota-gap-assessment-20260514.md) §10 T1

---

## 0. Health probe (do this first, every time)

```bash
# Confirm extension + configs exist
PGPASSWORD=... PGUSER=... PGHOST=... PGDATABASE=novel_analyzer \
  psql -tA -c "SELECT cfgname FROM pg_ts_config WHERE cfgname IN ('jiebacfg','jiebaqry','simple');"
# Expect: simple, jiebacfg, jiebaqry
```

```bash
# Confirm bm25_vector column uses jiebacfg
psql -tA -c "
SELECT pg_get_expr(d.adbin, d.adrelid)
FROM pg_attribute a
JOIN pg_attrdef d ON a.attrelid = d.adrelid AND a.attnum = d.adnum
WHERE a.attrelid='retrieval_documents'::regclass
  AND a.attname='bm25_vector';"
# Expect: to_tsvector('jiebacfg'::regconfig, COALESCE(bm25_text, ''::text))
```

If either fails, follow [pg-jieba-userdict-ops.md §1-2](../foundation-optimization/pg-jieba-userdict-ops.md) before continuing.

---

## 1. Refresh userdict from current branch state

```bash
source .venv/bin/activate
python -m novel_analyzer.cli.app domain-dict-rebuild
```

This regenerates `.cache/novel-analyzer/{domain-dict.txt, jieba-user-dict.txt}` from `fact_records` + `graph_nodes`. The `_is_valid_term` filter (length 2-12, no sentence punctuation) prevents long fact summaries from being added as userdict entries (which would collapse entire sentences into single BM25 tokens — see test `test_sentence_like_labels_are_rejected`).

Expected output footer:

```
total new=N dict_size=M
plain dict: .cache/novel-analyzer/domain-dict.txt
jieba dict: .cache/novel-analyzer/jieba-user-dict.txt
```

---

## 2. Push userdict to PG container

PG runs in container `pid=<PG_PID>` (typically dnsmasq-owned `postgres -D /var/lib/postgresql/data`). Find it:

```bash
ps aux | grep '[p]ostgres -D /var/lib/postgresql/data' | head -1
```

Copy via `/proc/<pid>/root` (works without docker socket access):

```bash
PG_PID=$(pgrep -f 'postgres -D /var/lib/postgresql/data' | head -1)
sudo cp /home/user/ai-books/.cache/novel-analyzer/jieba-user-dict.txt \
  /proc/${PG_PID}/root/opt/postgresql/share/tsearch_data/jieba_user.dict

# Verify
sudo wc -l /proc/${PG_PID}/root/opt/postgresql/share/tsearch_data/jieba_user.dict
```

**Verify fresh-backend tokenization sees new terms** (does NOT need PG restart for SELECT-only verification — each new psql backend reads userdict on first call):

```bash
psql -tA -c "SELECT to_tsvector('jiebacfg', '<sample_proper_noun>')::text;"
```

---

## 3. Rebuild bm25_vector (the deferred step) — REQUIRES low-traffic window

### 3.1 Why this is hazardous

`bm25_vector` is `GENERATED ALWAYS AS (to_tsvector('jiebacfg', bm25_text)) STORED`. Existing rows hold tokens computed under the **old** userdict. The only reliable way to force re-tokenization with the new userdict is `ALTER TABLE DROP COLUMN bm25_vector` followed by `ADD COLUMN ... GENERATED ALWAYS AS (...) STORED` — this rewrites the entire table.

**The hazard**: `ALTER TABLE DROP COLUMN` requires `AccessExclusiveLock`. Any concurrent transaction holding `AccessShareLock` (every SELECT) blocks it. Worse, once the ALTER queues for the lock, all subsequent SELECTs queue behind it — the table effectively goes read-locked.

### 3.2 Pre-flight

```bash
# Check active sessions on the DB
psql -tA -c "
SELECT pid, state, age(now(), xact_start) AS tx_age, left(query, 60)
FROM pg_stat_activity
WHERE datname='novel_analyzer' AND pid != pg_backend_pid()
ORDER BY xact_start NULLS LAST;"
```

**Abort if you see**:
- A `writer-imitate-*` / `imitation-harness` / `pipeline-run` query (these hold long open transactions)
- An idle-in-transaction with non-trivial age (these block forever)
- A running `bm25-reindex` from an earlier attempt

If any present, wait for completion or coordinate a maintenance window.

### 3.3 Execute

```bash
source .venv/bin/activate
python -m novel_analyzer.cli.app bm25-reindex --confirm
```

The CLI:
1. Opens a fresh psycopg connection (new backend = sees new userdict)
2. Validates tokenizer with `'路朝歌养生功龟息养气功'` sample
3. `DROP COLUMN bm25_vector`
4. `ADD COLUMN bm25_vector tsvector GENERATED ALWAYS AS (to_tsvector('jiebacfg', ...)) STORED`
5. Reports row count

Total time: O(rows) full-table rewrite — ~10s per 1k rows on local hardware.

### 3.4 If it hangs

```bash
# Inspect lock holders
psql -tA -c "
SELECT pid, mode, granted FROM pg_locks
WHERE relation = 'retrieval_documents'::regclass;"

# Cancel YOUR own ALTER (NOT the user-business queries)
psql -tA -c "SELECT pg_cancel_backend(<your_alter_pid>);"
```

After cancel, the column definition is intact — no data loss, just a no-op.

### 3.5 Verify reindex took effect

```bash
psql -tA -c "
SELECT left(bm25_vector::text, 200)
FROM retrieval_documents
WHERE bm25_text LIKE '%<sample_proper_noun>%' LIMIT 1;"
```

Look for the proper noun appearing as a single token (e.g. `'路朝歌':1`) instead of being split.

---

## 4. Validation: BM25 recall benchmark

After reindex, run the benchmark to quantify the gain:

```bash
python -m novel_analyzer.cli.app retrieval-benchmark \
  --branch-id <test_branch> \
  --configs simple,jiebacfg
```

Target deltas (from kernel-sota assessment):
- Proper-noun query recall: **+20% or better**
- Top-5 hit rate: **+15% or better**
- Non-proper-noun queries: **±2% (no regression)**

Record the report in [.sisyphus/reports/](../../.sisyphus/reports/) for tracking.

---

## 5. Known limits

- pg_jieba has **no hot reload**. Adding new terms to userdict requires a fresh PG backend (which most clients give automatically) for query-time tokenization, but `bm25_vector` rewrite still requires the ALTER+full-rewrite cycle.
- Generated-stored columns evaluate at INSERT/UPDATE time using the writing backend's jieba state. New documents inserted by an old long-lived backend may use stale tokenizer.
- `pg_cancel_backend()` of the ALTER is always safe — the DDL hasn't started rewriting yet.
- **DO NOT** use `pg_terminate_backend()` to force the lock; it can leave the column in a half-defined state if the ALTER had already started moving rows.

---

## 6. Audit trail

Each invocation should leave evidence:

| Artifact | Location |
|---|---|
| Userdict snapshot | `.cache/novel-analyzer/jieba-user-dict.txt` (git-ignored, take a `wc -l` for the log) |
| In-container userdict | `/proc/<pg_pid>/root/opt/postgresql/share/tsearch_data/jieba_user.dict` |
| Sample tokenization | `psql -c "SELECT to_tsvector('jiebacfg', '<phrase>');"` |
| Benchmark report | `.sisyphus/reports/bm25-jieba-<date>.md` |

---

## 7. Quick reference

```bash
# All-in-one (run during low traffic)
source .venv/bin/activate
python -m novel_analyzer.cli.app domain-dict-rebuild

PG_PID=$(pgrep -f 'postgres -D /var/lib/postgresql/data' | head -1)
sudo cp /home/user/ai-books/.cache/novel-analyzer/jieba-user-dict.txt \
  /proc/${PG_PID}/root/opt/postgresql/share/tsearch_data/jieba_user.dict

python -m novel_analyzer.cli.app bm25-reindex --confirm
python -m novel_analyzer.cli.app retrieval-benchmark --branch-id <id> --configs simple,jiebacfg
```
