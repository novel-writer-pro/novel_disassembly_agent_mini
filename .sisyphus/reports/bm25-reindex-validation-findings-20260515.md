# BM25 Reindex Validation Findings — 2026-05-15

> **Headline result**: Post-reindex MRR is **byte-identical** to pre-reindex
> across all 3 sample branches. The kernel-sota assessment's "+20-30% recall
> on proper-noun queries" claim was unfounded for the imitation-domain query
> distribution we have. The +9.1pp avg jiebacfg-vs-simple delta is real but
> existed PRE-reindex; T1's userdict cleanup made the system more CORRECT
> (no more 600-char sentence-as-token), not more performant on this benchmark.

> **Source of truth**: 6 JSON benchmark reports in `.sisyphus/reports/`
> (3 pre-reindex + 3 post-reindex), all with same query set + k-values.

---

## Numbers

| Branch | Stage | jiebacfg MRR | simple MRR | Δ |
|---|---|---|---|---|
| `2cd9c1ff` | pre  | 0.7167 | 0.6167 | **+0.100** |
| `2cd9c1ff` | post | 0.7167 | 0.6167 | +0.100 |
| `e5becabd` | pre  | 0.8033 | 0.6567 | **+0.147** |
| `e5becabd` | post | 0.8033 | 0.6567 | +0.147 |
| `8af4f620` | pre  | 0.5350 | 0.5100 | **+0.025** |
| `8af4f620` | post | 0.5350 | 0.5100 | +0.025 |

**No row changed.** Same 50 queries, same scores.

## Why

T1 cleanup at commit `ae16931` removed `_TERM_MAX_LEN > 12` entries from
`jieba-user-dict.txt`. Those rejected entries were sentence-shaped narrative
fact summaries (e.g. *"本章延续了前文兽妖围攻青云山的大规模战斗场景..."* —
669 chars as a single "term"). They were causing pg_jieba to glue entire
paragraphs into single BM25 tokens — the "vocabulary loop" pathology this
session was set up to detect.

But the **proper-noun entries** (≤12 chars: `路朝歌`, `卫图`, `养生功`, etc.)
were ALREADY in the dirty userdict before cleanup, AND they're still in the
clean userdict after cleanup. Identical proper-noun tokenization → identical
BM25 vector for proper-noun query terms → identical Recall@k.

The 50-query benchmark exercises proper-noun lookups (auto-generated from
chapter `summary_text`). It does NOT generate long-paragraph queries. So the
exact failure mode T1 fixed (paragraph-as-token) wasn't being measured.

## What was actually fixed

Verified by direct PG inspection post-reindex:

```sql
SELECT left(bm25_vector::text, 200) FROM retrieval_documents WHERE bm25_text LIKE '%卫图%' LIMIT 1;
-- Returns: '主线':23 '养生功':11 '卫图去找二姑':5,15 ...
```

`卫图去找二姑` is a fact label — still in userdict because it's ≤12 chars,
still treated as one token. But the truly pathological 600-char entries
(*"本章延续了前文兽妖围攻青云山的大规模战斗场景，具体聚焦于年轻一代弟子的战场表现..."*)
no longer collapse entire paragraphs. **You won't see that in MRR**, but
you'd see it if you queried for any sub-string within those long entries.

The fix is **correctness on tail cases**, not **performance on common queries**.

## Lesson (third time this session)

1. **B1 ai_trace** was claimed as a quality gate; data showed it inverted
   against verdict.
2. **B4 slop scorer** was claimed as helpful; data showed effect size below
   noise floor on harness output.
3. **T1 reindex** was claimed to deliver +20-30% recall; data shows 0pp delta
   on the proper-noun benchmark.

Pattern: **claim source was always "inspired by N-star repo X" or "from
heuristic intuition" without a measured baseline.** The thing the claim
referenced WAS real (in their corpus); ours is different. Always run a
baseline before promising a delta.

## Adjusted T1 description

T1 should be re-described as a **correctness fix**, not a **recall-boost
optimization**:

> Cleanup of `jieba-user-dict.txt` removes long sentence-shaped fact labels
> that were causing pg_jieba to glue entire paragraphs into single BM25
> tokens. This prevents a tail failure mode (queries containing those
> sentence fragments would match 0 documents OR match wrong documents) but
> does NOT improve Recall@k on the typical proper-noun query distribution.

The kernel-sota assessment doc should be updated to reflect this once
multiple findings accumulate (this is the third one).

## Reproducibility

```bash
source .venv/bin/activate

# Pre-reindex baseline (already saved):
.sisyphus/reports/bm25-baseline-pre-reindex-20260515.json
.sisyphus/reports/bm25-baseline-pre-reindex-20260515-e5becabd.json
.sisyphus/reports/bm25-baseline-pre-reindex-20260515-8af4f620.json

# Reindex command (run when DB is quiet — see runbook §3.2 pre-flight):
python -m novel_analyzer.cli.app bm25-reindex --confirm

# Post-reindex (saved):
.sisyphus/reports/bm25-post-reindex-20260515-2cd9c1ff.json
.sisyphus/reports/bm25-post-reindex-20260515-e5becabd.json
.sisyphus/reports/bm25-post-reindex-20260515-8af4f620.json
```

Diff command for verification:

```bash
for b in 2cd9c1ff e5becabd 8af4f620; do
  diff <(jq '.results' .sisyphus/reports/bm25-baseline-pre-reindex-20260515*-$b.json) \
       <(jq '.results' .sisyphus/reports/bm25-post-reindex-20260515-$b.json)
done
# Expected: empty diff for all 3 branches
```

## Status

T1.5 is **complete** — the reindex ran, the benchmark ran, and the
finding is documented honestly. The +20-30% claim is closed as
**unsubstantiated**; the +9.1pp jiebacfg-vs-simple delta is the real
gain of having pg_jieba at all (independent of dict cleanup).
