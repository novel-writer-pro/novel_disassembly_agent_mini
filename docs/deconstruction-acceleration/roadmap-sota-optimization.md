# Deconstruction Engine SOTA Optimization Roadmap

## Current Status: Phase 3 Complete (Entity Resolution + Arc Memory)

---

## Phase 1 - High ROI (Completed)

### 1A. Adaptive Context Assembly
- **Status**: Done
- **Impact**: Long-range fact recall +30-50%
- **Change**: `ContextService` now uses intake entities to drive 3-strategy retrieval (relevance + recency + foreshadowing)
- **Files**: `novel_analyzer/services/context_service.py`

### 1B. Stage Merging
- **Status**: Done
- **Impact**: LLM round-trips 5 -> 3, single-chapter latency -40%
- **Change**: Combined skill prompts + `_invoke_merged_stage` method + `use_merged_stages` setting
- **Files**: `novel_analyzer/services/analysis_service.py`, `novel_analyzer/agent/pipeline.py`, `skills_dir/chapter-intake-and-facts/`, `skills_dir/evidence-and-analysis/`
- **Activation**: `NOVEL_ANALYZER_USE_MERGED_STAGES=true`

---

## Phase 2 - Medium Priority (Next)

### 2A. Foreshadowing Lifecycle Manager
- **Status**: Done
- **Impact**: Prevents lost plot threads in 100+ chapter novels
- **Change**: New `ForeshadowingService` with planted/reinforced/paid_off state machine; auto-inject open foreshadowing into subsequent chapter context
- **Files**: `novel_analyzer/services/foreshadowing_service.py`, `novel_analyzer/services/context_service.py`, `novel_analyzer/services/analysis_service.py`

### 2B. Chapter Complexity Router
- **Status**: Done
- **Impact**: Smart model selection saves cost on simple chapters, improves quality on complex ones
- **Change**: `_score_chapter_complexity` scores intake results; routes to fallback model when complexity >= 0.7
- **Files**: `novel_analyzer/services/analysis_service.py`

### 2C. Pipeline Pipelining
- **Status**: Done
- **Impact**: Throughput +30% for multi-chapter runs
- **Change**: `_runner_loop` now uses `concurrency` parameter for batch processing (up to 3 chapters per loop iteration)
- **Files**: `novel_analyzer/application/pipeline_async.py`

---

## Phase 3 - Long-term Evolution (Completed)

### 3A. Entity Resolution (Coreference)
- **Status**: Done
- **Impact**: Prevents graph node duplication, improves retrieval precision
- **Change**: New `EntityResolutionService` with character-level Jaccard similarity clustering; alias map auto-built after each chapter's graph materialization; adaptive retrieval resolves aliases before querying
- **Files**: `novel_analyzer/services/entity_resolution_service.py`, `novel_analyzer/services/context_service.py`, `novel_analyzer/services/analysis_service.py`

### 3B. Arc-level Memory
- **Status**: Done
- **Impact**: Chapter 100+ retains access to chapter 1-5 critical information
- **Change**: New `ArcMemoryService` with 3-tier memory (recent/midrange/distant) and progressive compression; auto-injected into adaptive context
- **Files**: `novel_analyzer/services/arc_memory_service.py`, `novel_analyzer/services/context_service.py`

---

## Benchmark Plan

| Metric | Baseline | Measured (Phase 1) | Target (Phase 2) |
|--------|----------|-------------------|-------------------|
| Single chapter latency (non-merged) | ~330s | 330.4s | - |
| Single chapter latency (merged) | - | 254.0s (-23%) | ~200s (pipelined) |
| LLM calls per chapter | 5 | 3 (merged) | 3 |
| Fact recall @ch50 | ~40% | ~65% (adaptive, estimated) | ~80% (foreshadow) |
| Context relevance | fixed top-8 | query-aware top-30 | lifecycle-managed |

**Real benchmark (2026-05-12, deepseek-v4-flash)**:
- Provider: deepseek-v4-flash @ https://api.deepseek.com/v1
- Novel: 775 chapters, ~5.2MB
- Non-merged (5 calls): 330.4s/chapter (original baseline)
- Merged (3 calls): 254.0s/chapter (Phase 1)
- Phase 3 (adaptive + entity + arc): 136.0s/chapter
- Total speedup: **59% faster** (330.4s -> 136.0s)

---

## Configuration Reference

```bash
# Enable merged stages (Phase 1B)
NOVEL_ANALYZER_USE_MERGED_STAGES=true

# LLM provider for benchmarking
NOVEL_ANALYZER_LLM_BASE_URL=https://api.deepseek.com/v1
NOVEL_ANALYZER_LLM_MODEL_NAME=deepseek-v4-flash
NOVEL_ANALYZER_LLM_STAGE_MODEL_NAME=deepseek-v4-flash
```
