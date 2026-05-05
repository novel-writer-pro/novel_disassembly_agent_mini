# Real Xianxia Sample — Stage Summary (2026-05-06)

## Sample
- Source: `.cache/novel-analyzer/uploads/c495a0a263b947058a19dad743dab8a1-novel.txt`
- Genre: Chinese xianxia / male-oriented cultivation-adjacent opening
- Real-text issue found first: original headings use `第一节/第二节/第三节`, so direct ingest produced `chapter_count=0`

## Real compatibility findings
1. **Raw ingest compatibility gap**
   - Direct ingest on original text returned:
     - `raw_heading_count=0`
     - `normalized_chapter_count=0`
     - `chapter_count=0`
   - This is a real Chinese novel formatting compatibility problem, not a synthetic test artifact.

2. **Normalized ingest succeeds**
   - After minimal title normalization (`第一节 -> 第1章`, etc.), inspect succeeded with:
     - `raw_heading_count=3`
     - `normalized_chapter_count=3`
   - Run/branch:
     - `run_id=b0fb667b-ce1e-47a0-8346-92e3dbc6d3bc`
     - `branch_id=86ce179e-475a-42b9-ade3-a81a8626dc5f`

3. **Pipeline robustness finding on chapter 2**
   - `small_model_pipeline` failed schema validation on `dialogue_candidates` object payloads and missing `normalized_title`
   - System automatically recovered through `monolithic_fallback`
   - Result: chapter 2 still completed and persisted

## Current progress snapshot
- Chapter 1: completed, retrieval materialized, hook=`4.5`
- Chapter 2: completed via fallback, retrieval materialized, hook=`4.0`
- Chapter 3: running

## Early content quality signal
- Chapter 1 summary is concise but a bit generic: `少年持黑牌感受神秘振动。`
- Chapter 1 worldbuilding / foreshadowing extraction is strong and evidence-backed.
- Chapter 2 captured interpersonal tone, emotional curve, and xianxia-world references reasonably well.

## Immediate next steps
1. Wait for chapter 3 completion and export final branch artifacts.
2. Record original-heading incompatibility as a concrete parser/ingest improvement item.
3. Record chapter-2 dialogue schema mismatch as a structured pipeline compatibility bug.
