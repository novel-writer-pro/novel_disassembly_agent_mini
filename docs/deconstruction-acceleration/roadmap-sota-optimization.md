# Deconstruction Engine SOTA Optimization Roadmap

## Current Status: Phase 1 Complete (Adaptive Context + Stage Merging)

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
- **Status**: Pending
- **Impact**: Prevents lost plot threads in 100+ chapter novels
- **Design**: New `ForeshadowingService` with planted/reinforced/paid_off state machine; auto-inject open foreshadowing into subsequent chapter context
- **Files to create**: `novel_analyzer/services/foreshadowing_service.py`
- **Integration**: `ContextService.adaptive_fact_context_json` + `GraphService`

### 2B. Chapter Complexity Router
- **Status**: Pending
- **Impact**: Smart model selection saves cost on simple chapters, improves quality on complex ones
- **Design**: After intake, score chapter complexity (character_count * scene_switches * thread_density); route to small/large model accordingly
- **Files to modify**: `novel_analyzer/services/analysis_service.py`

### 2C. Pipeline Pipelining
- **Status**: Pending
- **Impact**: Throughput +30% for multi-chapter runs
- **Design**: Start chapter N+1 intake while chapter N materialization runs
- **Files to modify**: `novel_analyzer/application/pipeline_async.py`

---

## Phase 3 - Long-term Evolution

### 3A. Entity Resolution (Coreference)
- Auto-merge "小明" = "明哥" = "那个少年"
- Requires NER + coreference model or LLM-based resolution

### 3B. Causal Graph
- Extend GraphService with typed causal edges (X causes Y)
- Enables logic-break detection

### 3C. Arc-level Memory
- Organize memory by story arcs instead of chapters
- One arc can span 50+ chapters

---

## Benchmark Plan

| Metric | Baseline | Target (Phase 1) | Target (Phase 2) |
|--------|----------|-------------------|-------------------|
| Single chapter latency | ~60s | ~36s (merged) | ~25s (pipelined) |
| LLM calls per chapter | 5 | 3 (merged) | 3 |
| Fact recall @ch50 | ~40% | ~65% (adaptive) | ~80% (foreshadow) |
| Context relevance | fixed top-8 | query-aware top-30 | lifecycle-managed |

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
