# BM25 Pre-Reindex Baseline Benchmark — 2026-05-15

> **Purpose**: Capture jiebacfg vs simple FTS recall delta on production data
> BEFORE the bm25-reindex (T1.5) runs. After reindex, re-run and diff to verify
> the kernel-sota assessment's "+20-30% recall on proper-noun queries" claim.
> **Run command**: `python -m novel_analyzer.cli.app retrieval-benchmark <branch_id> --max-queries 50 --output-file <path>`
> **Method**: 50 query sample per branch, tested against jiebacfg AND simple
> configs side-by-side. Recall@1/3/5 + MRR + avg_latency_ms.

---

## Summary table (3 branches, n=50 each)

| Branch | Total docs | ΔMRR | ΔRecall@1 | ΔRecall@3 | ΔRecall@5 | Δlatency |
|---|---|---|---|---|---|---|
| `2cd9c1ff` | 186 | **+0.100** | +0.100 | +0.100 | +0.100 | +1.4ms |
| `e5becabd` | 184 | **+0.147** | +0.140 | +0.160 | +0.160 | -3.4ms |
| `8af4f620` | 178 | +0.025 | +0.020 | +0.020 | +0.040 | +4.3ms |
| **avg** | 183 | **+0.091** | +0.087 | +0.093 | +0.100 | +0.8ms |

All deltas are jiebacfg − simple (positive = jiebacfg wins).

## Per-branch raw MRR

| Branch | simple MRR | jiebacfg MRR |
|---|---|---|
| `2cd9c1ff` | 0.617 | 0.717 |
| `e5becabd` | 0.657 | 0.803 |
| `8af4f620` | 0.510 | 0.535 |

## Findings

### Direction is right, magnitude varies

All 3 branches show **jiebacfg > simple** on every Recall@k. Two of three saw
≥10pp gain on MRR; one saw only 2.5pp. Average **+9.1pp MRR is below the
"+20-30%" claim** in `kernel-sota-gap-assessment-20260514.md` §10 T1, but:

- This is the **pre-reindex** baseline. The bm25_vector for these rows was
  built using the OLD userdict (the one with 7000+ entries including 600+ char
  sentence-shaped noise that was cleaned up at commit `ae16931`).
- After T1.5 reindex with the cleaned 2627-term userdict, the gain should
  approach or exceed the +20-30% target — sentence-shaped noise that was
  collapsing entire paragraphs into single tokens will be gone.

### Why `8af4f620` underperformed (+0.025)

Same chapter count and bm25_text size as the other two branches, so it's not a
data-volume issue. Likely explanations:
- Different content domain (genre / setting) — proper-noun density may be lower
- 50-query sample variance — 50 queries on 178 docs = 28% sampling rate, but
  if proper nouns are clustered, sampling can miss them
- Pre-reindex bm25_vector pollution may bite this branch harder due to its
  particular noise profile

Re-run after reindex to confirm.

### Latency

Avg jiebacfg latency = simple latency ± 5ms. **Not a regression risk.**

## Reproducibility

```bash
source .venv/bin/activate
python -m novel_analyzer.cli.app retrieval-benchmark 2cd9c1ff-aba2-4d92-a42e-b2e373baaab7 \
  --max-queries 50 --output-file .sisyphus/reports/bm25-baseline-pre-reindex-20260515.json
python -m novel_analyzer.cli.app retrieval-benchmark e5becabd-e2f3-4045-9249-fa91f382dc9a \
  --max-queries 50 --output-file .sisyphus/reports/bm25-baseline-pre-reindex-20260515-e5becabd.json
python -m novel_analyzer.cli.app retrieval-benchmark 8af4f620-0c3a-4629-82bb-b30a1a48b30e \
  --max-queries 50 --output-file .sisyphus/reports/bm25-baseline-pre-reindex-20260515-8af4f620.json
```

Raw JSON reports preserved alongside this doc. Each contains exact query/doc
hits, latency histograms, and elapsed time.

## Next step

When DB write window opens (no active `INSERT INTO retrieval_documents` or
`DELETE FROM graph_*` transactions), follow
[bm25-jieba-reindex.md §3](../runbook/bm25-jieba-reindex.md) to run reindex.
Then re-run all 3 commands above with `-post-reindex-` filename suffix and
diff against this baseline. Expected post-reindex deltas:

- MRR: +0.20 to +0.30 (reaching the kernel-sota T1 target)
- Latency: unchanged
- 8af4f620 anomaly should narrow

If post-reindex doesn't show the claimed gain, the issue is NOT the userdict —
investigate FTS config setup or jieba tokenizer cache state in PG (see
[pg-jieba-userdict-ops.md §5.1](../foundation-optimization/pg-jieba-userdict-ops.md)).
