# Fallback Isolation Plan — 2026-05-13

> ⚠️ **历史设计文档 — 不代表实际实现**
>
> 本文档是 2026-05-13 早期写的设计草稿。在实施过程中发现了几处事实错误
> (例如 retrieval_documents 表用 `branch_id+chapter_index` 关联,没有
> `chapter_artifact_id` 列;Phase 4 最终也没用 SQL DELETE 而是非破坏性 sweep)。
>
> **真实实施记录请看** `entity-extraction-noise-diagnosis-20260513.md`
> §11-§14 + `fallback-isolation-handoff-20260513.md`。本文档保留作历史
> 决策追溯参考。

---

## Recommendation: Hybrid — Option A (primary) + Option C (hardening)

**Decision rationale:**

| Option | Risk | Benefit | Verdict |
|--------|------|---------|---------|
| **A** — add `extraction_source` field to payload_json | Low risk, no schema migration needed (adds key to existing JSON column) | Explicit tag at the artifact level; no JOIN needed; retroactive backfill via continuity_notes heuristic works | **Primary** |
| **B** — detect via `invocation_metadata` JOIN | Med risk — requires JOIN to `chapter_raw_outputs` which may not exist for all artifacts (e.g. re-imported or partial runs) | No payload_json write change | Rejected — fragile JOIN dependency |
| **C** — don't write retrieval_documents for fallback | Med risk — only covers retrieval_service; other consumers still ingest noise | Strongest isolation at write-time | **Secondary** — apply in addition to A where feasible |

**Final choice: Option A as the single source of truth tag, with consumer-side guards.**

---

## Phase 1: Write-Side Tagging (analysis_service.py)

### 1a. Add `extraction_source` to `_build_local_heuristic_analysis`

**File:** `novel_analyzer/services/analysis_service.py:591-633`

In `_build_local_heuristic_analysis`, add `extraction_source='heuristic'` to the returned payload_json dimension data. The clean LLM path (line ~773) should also tag `extraction_source='llm'`.

**Change at line 616** (the return statement — actually it returns a `ChapterAnalysisOutput` Pydantic model, not dict directly). Need to check if `ChapterAnalysisOutput` has a field that maps to payload_json extras.

Let me check the model definition...

### 1b. Add extraction_source to the model

**File:** Check `novel_analyzer/models/` or wherever `ChapterAnalysisOutput` is defined. Add an optional field `extraction_source: str = 'llm'`.

Actually the cleaner route: inject into `payload_json` after the model is dumped. In `analysis_service.py:1344`:

```python
raw_result = result.model_dump(mode='json')
```

Add right after:
```python
if stage_payload.get('fallback') == 'local-heuristic':
    raw_result['extraction_source'] = 'heuristic'
else:
    raw_result['extraction_source'] = 'llm'
```

This avoids changing the Pydantic model.

### 1c. Store payload_json

The raw_result (now with `extraction_source`) is passed to `self.run_service.record_raw_output` which stores it to `chapter_raw_outputs.response_json`. But the artifact payload is stored separately via `_upsert_artifacts`.

Let me find where the artifact payload_json is stored...

---

## Phase 2: Backfill Existing 326 Rows

**Backfill detection marker:** `chapter_artifacts.payload_json.continuity_notes[0]` contains "本地启发式分析保底生成" (the Chinese string in line 607).

**SQL for backfill:**
```sql
UPDATE chapter_artifacts
SET payload_json = jsonb_set(
    payload_json,
    '{extraction_source}',
    '"heuristic"',
    true
)
WHERE payload_json->'continuity_notes'->>0 LIKE '%本地启发式分析保底生成%';
```

**Companion SQL for clean rows:**
```sql
UPDATE chapter_artifacts
SET payload_json = jsonb_set(
    payload_json,
    '{extraction_source}',
    '"llm"',
    true
)
WHERE payload_json->'extraction_source' IS NULL;
```

**Alternative (Python via Alembic):** Write a one-shot data migration in a script, not a formal migration revision (since schema doesn't change — only JSON content).

---

## Phase 3: Consumer-Side Guards

### 3a. Shared Utility — `is_heuristic_artifact`

Add to a shared module (e.g. `novel_analyzer/services/_fallback_guard.py`):

```python
_FALLBACK_MARKER = "本地启发式分析保底生成"

def is_heuristic_artifact(payload: dict[str, object]) -> bool:
    extraction_source = payload.get("extraction_source")
    if extraction_source == "heuristic":
        return True
    if extraction_source == "llm":
        return False
    # Fallback detection for legacy rows without the tag
    notes = payload.get("continuity_notes", [])
    if isinstance(notes, list) and len(notes) > 0 and isinstance(notes[0], str):
        return _FALLBACK_MARKER in notes[0]
    return False
```

### 3b. Guard insertion points

| Service | File:Line | Insert guard before |
|---------|-----------|---------------------|
| retrieval_service | `retrieval_service.py:87` | Skip if heuristic → return `[]` for keywords, skip BM25 indexing |
| retrieval_service | `retrieval_service.py:104` | Skip if heuristic → return empty hints |
| fact_service | `fact_service.py:37` | Skip entity extraction if heuristic |
| graph_service | `graph_service.py:280` | Fallback to empty entity list if heuristic |
| tension_service | `tension_service.py:213` | Return empty set if heuristic |
| risk_audit_service | `risk_audit_service.py:469` | Use empty key_entities if heuristic |
| author_knowledge_service | `author_knowledge_service.py:298` | Return empty key_entities if heuristic |

### 3c. Exact code patterns

**retrieval_service.py:85-92**
```python
@staticmethod
def _normalize_keywords(payload: dict[str, Any]) -> list[str]:
    if is_heuristic_artifact(payload):
        return []  # skip heuristic fallback data
    keywords = []
    for item in payload.get("key_entities", []):
        ...
```

**retrieval_service.py:102-107**
```python
@staticmethod
def _query_hints(payload: dict[str, Any], title: str) -> list[str]:
    if is_heuristic_artifact(payload):
        return [f"第{payload.get('chapter_index', '?')}章 {title} 讲了什么"]
    hints = ...
```

**fact_service.py:37-41**
```python
key_entities = cast(list[Any], payload.get('key_entities', []))
if is_heuristic_artifact(payload):
    key_entities = []  # don't create entity FactRecords from fallback
```

**graph_service.py:279-280**
```python
if not entity_items and not is_heuristic_artifact(payload):
    entity_items = self._normalize_note_list(payload.get('key_entities', []))
```

**tension_service.py:212-213**
```python
payload = artifact.payload_json or {}
if is_heuristic_artifact(payload):
    return set()
entities: list[object] = list(payload.get("key_entities", []))
```

---

## Edge Cases

| Case | Handling |
|------|----------|
| **Mixed branches** (some chapters clean, some fallback) | per-chapter tags handle this naturally; guard evaluates per-artifact |
| **Legacy rows before backfill** | `is_heuristic_artifact` falls back to continuity_notes check |
| **Empty continuity_notes** | `is_heuristic_artifact` returns False — safe (treats as unknown/LLM) |
| **fact_service re-runs** (delete + re-insert) | Fresh insert also checks guard; safe |
| **retrieval_documents already written for fallback** | Need a separate purge step (Phase 4) |
| **Graph nodes/edges from fallback entities** | Not automatically cleaned; needs a purge script too |

---

## Phase 4: Purge Already-Contaminated Downstream Data

After guards are deployed, existing fallback data is still in:
- `retrieval_documents` table
- `graph_nodes` / `graph_edges` (from graph_service entity processing)
- `fact_records` (from fact_service entity extraction)

These need targeted deletion:

```sql
-- Delete retrieval_documents for heuristic chapters
DELETE FROM retrieval_documents
WHERE chapter_artifact_id IN (
    SELECT id FROM chapter_artifacts
    WHERE payload_json->>'extraction_source' = 'heuristic'
);
```

```sql
-- Delete fact_records for heuristic chapters
DELETE FROM fact_records
WHERE chapter_artifact_id IN (
    SELECT id FROM chapter_artifacts
    WHERE payload_json->>'extraction_source' = 'heuristic'
);
```

Graph cleanup is trickier because nodes/edges are shared across chapters. Options:
(a) Delete only edges where both endpoints are only in heuristic chapters
(b) Accept graph contamination as low-risk (not query-driven like retrieval) and clean on next full run

**Recommendation:** Purge `retrieval_documents` and `fact_records` immediately. Leave graph nodes/edges for the next full re-run.

---

## Phase 5: Tests

### 5a. Unit tests

Create `tests/test_fallback_guard.py`:
- `test_is_heuristic_artifact_true_with_tag` — payload with `extraction_source: "heuristic"` returns True
- `test_is_heuristic_artifact_true_with_notes` — payload with continuity_notes marker returns True
- `test_is_heuristic_artifact_false_llm` — payload with `extraction_source: "llm"` returns False
- `test_is_heuristic_artifact_false_empty` — empty/minimal payload returns False

### 5b. Guard unit tests per service

Existing test files that need additions:

| Test file | Additions |
|-----------|-----------|
| `tests/test_retrieval_service.py` | Test that `_normalize_keywords` returns `[]` for heuristic payload |
| `tests/test_fact_service.py` | Test that entity rows are skipped for heuristic payload |
| `tests/test_graph_service.py` | Test that key_entities fallback is skipped for heuristic |
| `tests/test_tension_service.py` | Test that set is empty for heuristic payload |

### 5c. Integration test

```python
def test_fallback_artifact_filtered_from_retrieval():
    """Create a fake fallback chapter_artifact, confirm retrieval_service skips it."""
    artifact = ChapterArtifact(
        branch_id="test-branch",
        chapter_index=999,
        payload_json={
            "key_entities": ["第十六章", "汪汪汪", "犬吠声与"],
            "continuity_notes": ["本地启发式分析保底生成"],
            "chapter_index": 999,
        }
    )
    session.add(artifact)
    session.flush()

    # retrieval_service should produce no keywords
    svc = RetrievalService(session)
    keywords = svc._normalize_keywords(artifact.payload_json)
    assert keywords == []
```

---

## Verification

| Check | Method |
|-------|--------|
| Known BAD branch MRR rises | Re-run `retrieval-benchmark-report-20260513.md` on e5becabd; expect MRR >0.164 |
| retrieval_documents empty for heuristic chapters | SQL count: `SELECT COUNT(*) FROM retrieval_documents WHERE chapter_artifact_id IN (SELECT id FROM chapter_artifacts WHERE payload_json->>'extraction_source' = 'heuristic')` → 0 |
| No noisy entities in risk_signals | Manual spot-check: risk_audit for e5becabd ch16 should not contain "汪汪汪" |
| Backfill completeness | `SELECT COUNT(*) FROM chapter_artifacts WHERE payload_json->>'extraction_source' IS NULL` → 0 |

---

## Atomic Commit Phases

| Phase | Files | Description |
|-------|-------|-------------|
| **P1** | `analysis_service.py` | Write-side tagging: add `extraction_source` to both heuristic and LLM paths |
| **P2** | New `_fallback_guard.py` + `models.py` | Shared guard utility |
| **P3** | All 7 consumer services | Consumer-side guards |
| **P4** | Script (Python or SQL) | Backfill 326 existing rows |
| **P5** | Script (SQL) | Purge contaminated retrieval_documents + fact_records |
| **P6** | `tests/` | All unit + integration tests |

**Ordering:** P1 → (P2 + P4) → P3 → P5 → P6
P4 can run in parallel with P2 since it's data-only.

## Non-Goals

- ❌ Re-running 326 chapters of LLM analysis (separate decision, requires quota fix)
- ❌ Changing the heuristic itself (stop_words expansion is §11.6 item 2, secondary priority)
- ❌ Alembic schema migration (no schema change needed)
- ❌ Alerting for LLM failures (separate §11.6 item 3)
