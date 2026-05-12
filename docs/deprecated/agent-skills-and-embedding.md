# Internal Agent Pipeline, Skills Assets, and BGE ONNX Embedding

## Goal
This project keeps the **execution logic** inside the repo's own book-deconstruction agent while using `skills_dir/` as a prompt/schema asset layer.

## Internal execution ownership
The primary runtime chain is:

1. `chapter_intake`
2. `fact_extractor`
3. `evidence_binder`
4. `analysis_generator`
5. `writer_learning_lens`
6. `anti_fabrication_guard`

These stages are orchestrated by `novel_analyzer/agent/pipeline.py` and executed from `novel_analyzer/services/analysis_service.py`.

## Asset-backed prompts
The internal stage names map to repo-local prompt assets in `skills_dir/`:

- `chapter_intake` -> `skills_dir/chapter-intake/`
- `fact_extractor` -> `skills_dir/chapter-fact-extractor/`
- `evidence_binder` -> `skills_dir/evidence-binder/`
- `analysis_generator` -> `skills_dir/chapter-analysis-generator/`
- `writer_learning_lens` -> `skills_dir/writer-learning-lens/`
- `anti_fabrication_guard` -> `skills_dir/anti-fabrication-guard/`

This reduces prompt drift while keeping execution fully agent-owned.

## Fallback behavior
If the staged small-model pipeline fails or produces a sparse result, the agent falls back to a monolithic chapter-analysis prompt.

## BGE ONNX backend
The embedding layer supports two backends:

- `stub` (default)
- `onnx`

When `embedding_backend=onnx`, the provider attempts to load `BAAI/bge-m3` style assets, preferring:

- `onnx/model.onnx`
- tokenizer files from the same Hugging Face snapshot
- pooling mode from `1_Pooling/config.json`

### Configuration
Use environment variables in `.env.local`:

```bash
NOVEL_ANALYZER_EMBEDDING_BACKEND=onnx
NOVEL_ANALYZER_EMBEDDING_MODEL_NAME=BAAI/bge-m3
NOVEL_ANALYZER_EMBEDDING_MODEL_PATH=
NOVEL_ANALYZER_EMBEDDING_CACHE_DIR=.cache/embeddings
NOVEL_ANALYZER_EMBEDDING_MAX_LENGTH=2048
```

### Notes
- If `NOVEL_ANALYZER_EMBEDDING_MODEL_PATH` points to a local exported ONNX model directory, it is used directly.
- Otherwise the provider downloads a filtered snapshot from Hugging Face Hub.
- For `BAAI/bge-m3`, the official repo contains an `onnx/model.onnx` file and `1_Pooling/config.json` that indicates CLS pooling.

## Why this design works for small models
- prompt responsibilities are narrow
- schema validation is strict
- sparse outputs get minimum safe backfills
- failed/sparse stage chains do not block the system because fallback remains available

## Remaining work
- switch retrieval embeddings from stub to real ONNX in live runs
- install and integrate `pg_jieba` for improved Chinese tokenization in PostgreSQL retrieval
- continue refining few-shot examples in stage prompts for denser fact extraction

## Environment blocker observed in live testing

The ONNX backend code path works, but this environment currently cannot reach `huggingface.co`, so automatic model download fails. To use live ONNX embeddings now, place an exported local ONNX model directory on disk and set:

```bash
NOVEL_ANALYZER_EMBEDDING_BACKEND=onnx
NOVEL_ANALYZER_EMBEDDING_MODEL_PATH=/absolute/path/to/bge-m3-onnx
```

Then verify with:

```bash
poetry run novel-analyzer test-embedding
```
