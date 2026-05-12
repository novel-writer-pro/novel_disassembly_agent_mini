# HTTP Backend for Embedding & Rerank

## Overview

The embedding and rerank services support pluggable backends through a unified Protocol interface. You can switch between local ONNX models and remote HTTP services without changing downstream code.

**Architecture**: `Settings → Factory → Protocol → HTTP/ONNX Provider`

## When to Use HTTP vs ONNX

### Use HTTP Backend When:
- You want to offload compute to a dedicated inference server
- You need GPU acceleration but don't have local GPU
- You're using a managed embedding service (OpenAI, Jina, Voyage, etc.)
- You want to share inference infrastructure across multiple clients
- You need to scale embedding/rerank independently

### Use ONNX Backend When:
- You need fully offline operation
- You want minimal latency (no network overhead)
- You have sufficient local CPU/RAM
- You want deterministic, reproducible results
- You're in a security-sensitive environment

## Configuration

### Local TEI (Text Embeddings Inference)

Start local TEI containers:
```bash
bash scripts/dev/tei-up.sh
```

Configure in `.env.local`:
```bash
NOVEL_ANALYZER_EMBEDDING_BACKEND=http
NOVEL_ANALYZER_EMBEDDING_API_BASE=http://localhost:8080
NOVEL_ANALYZER_EMBEDDING_API_FORMAT=tei
NOVEL_ANALYZER_EMBEDDING_MODEL_NAME=BAAI/bge-m3

NOVEL_ANALYZER_RERANK_BACKEND=http
NOVEL_ANALYZER_RERANK_API_BASE=http://localhost:8081
NOVEL_ANALYZER_RERANK_API_FORMAT=tei
NOVEL_ANALYZER_RERANK_MODEL_NAME=BAAI/bge-reranker-v2-m3
```

Stop containers:
```bash
bash scripts/dev/tei-down.sh
```

### OpenAI-Compatible Services

For OpenAI or OpenAI-compatible endpoints:
```bash
NOVEL_ANALYZER_EMBEDDING_BACKEND=openai
NOVEL_ANALYZER_EMBEDDING_API_BASE=https://api.openai.com
NOVEL_ANALYZER_EMBEDDING_API_KEY=sk-...
NOVEL_ANALYZER_EMBEDDING_API_FORMAT=openai
NOVEL_ANALYZER_EMBEDDING_MODEL_NAME=text-embedding-3-large
```

### Other Services

**Jina AI**:
```bash
NOVEL_ANALYZER_EMBEDDING_BACKEND=http
NOVEL_ANALYZER_EMBEDDING_API_BASE=https://api.jina.ai/v1
NOVEL_ANALYZER_EMBEDDING_API_KEY=jina_...
NOVEL_ANALYZER_EMBEDDING_API_FORMAT=openai
```

**Voyage AI**:
```bash
NOVEL_ANALYZER_EMBEDDING_BACKEND=http
NOVEL_ANALYZER_EMBEDDING_API_BASE=https://api.voyageai.com/v1
NOVEL_ANALYZER_EMBEDDING_API_KEY=pa-...
NOVEL_ANALYZER_EMBEDDING_API_FORMAT=openai
```

## Supported Formats

### Embedding

**OpenAI Format** (`api_format=openai`):
- Endpoint: `POST {api_base}/v1/embeddings`
- Request: `{"input": ["text1", "text2"], "model": "...", "encoding_format": "float"}`
- Response: `{"data": [{"index": 0, "embedding": [...]}, ...]}`
- Auth: `Authorization: Bearer {api_key}` (if api_key set)

**TEI Format** (`api_format=tei`):
- Endpoint: `POST {api_base}/embed`
- Request: `{"inputs": ["text1", "text2"], "truncate": true}`
- Response: `[[...], [...]]` (direct 2D array)
- Auth: Optional Bearer token

### Rerank

**TEI Format** (`api_format=tei`):
- Endpoint: `POST {api_base}/rerank`
- Request: `{"query": "...", "texts": ["doc1", "doc2"], "raw_scores": false, "truncate": true}`
- Response: `[{"index": 0, "score": 0.9}, {"index": 1, "score": 0.3}]`

**Cohere Format** (future):
- Not yet implemented
- Endpoint: `POST {api_base}/v2/rerank`

## Testing

### Unit Tests
Run mocked HTTP provider tests:
```bash
.venv/bin/python -m pytest tests/test_embedding_service.py tests/test_rerank_service.py -v
```

### Integration Tests
Start TEI containers and run integration tests:
```bash
bash scripts/dev/tei-up.sh
.venv/bin/python -m pytest tests/integration/test_tei_integration.py -m integration -v
bash scripts/dev/tei-down.sh
```

Integration tests verify:
- OpenAI and TEI format compatibility
- Embedding dimension (1024 for bge-m3)
- Determinism (same input → same output)
- Batch consistency
- Rerank relevance scoring

## Error Handling

### Retry Logic
- **5xx errors**: Exponential backoff retry (default: 2 retries, starting at 0.5s)
- **4xx errors**: Immediate failure (no retry)
- **Timeout**: Retry with backoff
- **Connection errors**: Retry with backoff

### Timeout Configuration
Default: 30 seconds per request
```bash
NOVEL_ANALYZER_EMBEDDING_HTTP_TIMEOUT=60.0
NOVEL_ANALYZER_RERANK_HTTP_TIMEOUT=60.0
```

### SSL Verification
Default: enabled
```bash
NOVEL_ANALYZER_EMBEDDING_HTTP_VERIFY_SSL=false  # Only for testing
```

## Rollback

To revert to ONNX backend:
```bash
NOVEL_ANALYZER_EMBEDDING_BACKEND=onnx
NOVEL_ANALYZER_RERANK_BACKEND=onnx
```

No code changes required. The factory automatically routes to the ONNX provider.

## Known Limitations

1. **Dimension mismatch**: HTTP backend must return 1024-dim vectors to match existing pgvector columns (for bge-m3)
2. **No streaming**: Batch requests only, no streaming support
3. **Cohere rerank**: Not yet implemented (TEI only)
4. **No async**: Synchronous HTTP calls (blocking)

## Performance Considerations

**Local TEI (CPU)**:
- First request: slow (model loading)
- Subsequent requests: ~100-500ms for small batches
- Memory: ~2GB per model

**Remote API**:
- Latency: network RTT + inference time
- Rate limits: check provider documentation
- Cost: per-token pricing for commercial APIs

## Troubleshooting

**"Connection refused"**:
- Check if TEI containers are running: `sudo docker ps | grep tei`
- Verify health: `curl http://localhost:8080/health`

**"HTTP 400"**:
- Check model name matches TEI model
- Verify request format (openai vs tei)

**"Timeout"**:
- Increase timeout: `NOVEL_ANALYZER_EMBEDDING_HTTP_TIMEOUT=120.0`
- Check server logs: `sudo docker logs tei-embed`

**Dimension mismatch**:
- Ensure HTTP backend returns 1024-dim vectors
- Use bge-m3 or compatible model
