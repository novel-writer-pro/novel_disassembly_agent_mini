# HTTP Backend for Embedding & Rerank - Production Guide

## Overview

The embedding and rerank services support pluggable backends through a unified Protocol interface. You can switch between local ONNX models and remote HTTP services without changing downstream code.

**Architecture**: `Settings → Factory → Protocol → HTTP/ONNX Provider`

This guide covers production-ready deployment of TEI (Text Embeddings Inference) as the HTTP backend, including all known gotchas, troubleshooting procedures, and operational runbooks.

## Quick Start

```bash
# 1. Pre-download models (required for China networks)
make tei-prefetch

# 2. Start TEI services
make tei-up

# 3. Verify everything works
make tei-doctor

# 4. Configure application
cp .env.example .env.local
# Edit .env.local to set embedding_backend=http
```

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

**Step 1: Pre-download models**
```bash
# Required before first run, especially in China
make tei-prefetch
```

**Step 2: Start services**
```bash
make tei-up
```

**Step 3: Configure application** (`.env.local`):
```bash
NOVEL_ANALYZER_EMBEDDING_BACKEND=http
NOVEL_ANALYZER_EMBEDDING_API_BASE=http://localhost:8080
NOVEL_ANALYZER_EMBEDDING_API_FORMAT=tei
NOVEL_ANALYZER_EMBEDDING_MODEL_NAME=BAAI/bge-m3
NOVEL_ANALYZER_EMBEDDING_HTTP_BATCH_SIZE=32

NOVEL_ANALYZER_RERANK_BACKEND=http
NOVEL_ANALYZER_RERANK_API_BASE=http://localhost:8081
NOVEL_ANALYZER_RERANK_API_FORMAT=tei
NOVEL_ANALYZER_RERANK_MODEL_NAME=BAAI/bge-reranker-v2-m3
NOVEL_ANALYZER_RERANK_HTTP_BATCH_SIZE=32
```

**Step 4: Verify**
```bash
make tei-doctor
```

### OpenAI-Compatible Services

```bash
NOVEL_ANALYZER_EMBEDDING_BACKEND=openai
NOVEL_ANALYZER_EMBEDDING_API_BASE=https://api.openai.com
NOVEL_ANALYZER_EMBEDDING_API_KEY=sk-...
NOVEL_ANALYZER_EMBEDDING_API_FORMAT=openai
NOVEL_ANALYZER_EMBEDDING_MODEL_NAME=text-embedding-3-large
NOVEL_ANALYZER_EMBEDDING_HTTP_BATCH_SIZE=2048
```

### Fallback Configuration (Optional)

Enable automatic fallback to ONNX when HTTP fails:

```bash
NOVEL_ANALYZER_EMBEDDING_FALLBACK_BACKEND=onnx
NOVEL_ANALYZER_EMBEDDING_FALLBACK_AFTER_FAILURES=3
```

After 3 consecutive HTTP failures, the provider automatically switches to local ONNX. It checks HTTP health every 60 seconds and switches back when recovered.

## Known Issues & Solutions

### Issue 1: Docker Pull Hangs in China

**Symptom**: `docker pull ghcr.io/huggingface/text-embeddings-inference:cpu-1.6` times out or hangs indefinitely.

**Root Cause**: GitHub Container Registry (ghcr.io) is blocked or throttled in China.

**Solution**:
```bash
# Configure Docker daemon proxy (requires sudo/admin)
# Edit /etc/docker/daemon.json:
{
  "proxies": {
    "http-proxy": "http://127.0.0.1:54321",
    "https-proxy": "http://127.0.0.1:54321"
  }
}

# Restart Docker daemon
sudo systemctl restart docker

# Then pull image
docker pull ghcr.io/huggingface/text-embeddings-inference:cpu-1.6
```

### Issue 2: Container Model Download Fails Despite Daemon Proxy

**Symptom**: Container starts but TEI logs show "failed to download model" even though daemon proxy is configured.

**Root Cause**: Docker daemon proxy only affects `docker pull`. Container outbound traffic is NOT proxied.

**Solution**: Use host-side pre-download + HF_ENDPOINT fallback:
```bash
# 1. Download on host (uses system proxy)
make tei-prefetch

# 2. Mount cache into container (tei-up.sh does this automatically)
# 3. Set HF_ENDPOINT for container fallback (tei-up.sh sets this)
```

### Issue 3: HF_HUB_OFFLINE=1 Doesn't Prevent Network Access

**Symptom**: Setting `HF_HUB_OFFLINE=1` still causes 2-minute timeout during TEI startup.

**Root Cause**: TEI's ONNX loading stage bypasses HF_HUB_OFFLINE and attempts network access anyway.

**Solution**: Always pre-download models with `make tei-prefetch`. Do NOT rely on `HF_HUB_OFFLINE=1` for true offline operation.

### Issue 4: hf-mirror.com Content-Range Header Issue

**Symptom**: `huggingface_hub` downloads work, but TEI container fails with "content-range header missing".

**Root Cause**: hf-mirror.com proxy doesn't fully implement HTTP range requests. Python's `huggingface_hub` tolerates this, but TEI's Rust downloader doesn't.

**Solution**: Use host-side pre-download (which uses Python's tolerant downloader):
```bash
HF_ENDPOINT=https://hf-mirror.com make tei-prefetch
```

### Issue 5: bge-m3 Download Incomplete (38MB Instead of 2.3GB)

**Symptom**: `tei-embed` container fails to start, logs show "model file corrupted" or "unexpected EOF".

**Root Cause**: `snapshot_download(allow_patterns=[...])` missing `*.bin` pattern. bge-m3 uses `pytorch_model.bin`, not safetensors.

**Solution**: `tei-prefetch.py` now includes `*.bin` in allow_patterns. If you downloaded before this fix:
```bash
rm -rf .cache/tei/models--BAAI--bge-m3
make tei-prefetch
```

### Issue 6: TEI ONNX Loading Still Downloads Despite Cache

**Symptom**: TEI starts but takes 2+ minutes, logs show "downloading model.onnx_data".

**Root Cause**: bge-m3 ONNX uses external data files (`model.onnx_data`). Missing from allow_patterns causes remote download.

**Solution**: `tei-prefetch.py` now includes `model.onnx_data`. If you see this issue:
```bash
rm -rf .cache/tei/models--BAAI--bge-m3
make tei-prefetch
```

### Issue 7: bge-reranker-v2-m3 Slow Startup (40s)

**Symptom**: `tei-rerank` container takes 40+ seconds to become healthy.

**Root Cause**: bge-reranker-v2-m3 has no ONNX export. TEI automatically falls back to Candle + safetensors, which is slower to load.

**Solution**: This is expected behavior. First rerank request will be slow (~10-30s), subsequent requests are fast. Consider:
- Using a model with ONNX export for faster startup
- Pre-warming with a dummy request after startup
- Accepting the 40s startup time (only happens once)

### Issue 8: sudo docker Permission Errors

**Symptom**: `make tei-up` fails with "permission denied" when accessing Docker socket.

**Root Cause**: User not in `docker` group and no passwordless sudo configured.

**Solution**: `tei-up.sh` auto-detects this. To fix permanently:
```bash
# Option 1: Add user to docker group (requires logout/login)
sudo usermod -aG docker $USER

# Option 2: Configure passwordless sudo for docker
sudo visudo
# Add: your_username ALL=(ALL) NOPASSWD: /usr/bin/docker
```

### Issue 9: Batch Size Limits Cause 413/400 Errors

**Symptom**: Large batch embedding/rerank requests fail with HTTP 413 (Payload Too Large) or 400 (Bad Request).

**Root Cause**: TEI has max-client-batch-size=32, OpenAI has limit of 2048 texts per request.

**Solution**: Automatic chunking is enabled by default. Configure explicitly if needed:
```bash
# TEI format (32 per request)
NOVEL_ANALYZER_EMBEDDING_HTTP_BATCH_SIZE=32
NOVEL_ANALYZER_RERANK_HTTP_BATCH_SIZE=32

# OpenAI format (2048 per request)
NOVEL_ANALYZER_EMBEDDING_HTTP_BATCH_SIZE=2048
```

## Troubleshooting

### Diagnostic Command

```bash
make tei-doctor
```

This runs 16 checks:
1. Python venv exists
2. huggingface_hub installed
3. Docker accessible
4. TEI image pulled
5. Embed model cached (>1GB)
6. Rerank model cached (>1GB)
7. Port 8080 available
8. Port 8081 available
9. tei-embed container healthy
10. tei-rerank container healthy
11. Embed /health endpoint responds
12. Rerank /health endpoint responds
13. Embed inference works (dim=1024)
14. Rerank inference works (correct ordering)
15. Provider integration works
16. Latency sampling (P50/P95)

### Common Failure Patterns

**All checks fail after check 3**: Docker not accessible. See Issue 8.

**Checks 5-6 fail**: Models not cached. Run `make tei-prefetch`.

**Checks 9-10 fail**: Containers not running. Run `make tei-up`.

**Checks 11-14 fail**: Services not ready. Wait 30s and retry, or check logs:
```bash
sudo docker logs tei-embed --tail 50
sudo docker logs tei-rerank --tail 50
```

### Manual Verification

```bash
# Check container status
sudo docker ps | grep tei

# Check embed service
curl http://localhost:8080/health
curl -X POST http://localhost:8080/embed \
  -H "Content-Type: application/json" \
  -d '{"inputs":["hello"]}'

# Check rerank service
curl http://localhost:8081/health
curl -X POST http://localhost:8081/rerank \
  -H "Content-Type: application/json" \
  -d '{"query":"test","texts":["a","b"]}'
```

## Operational Runbooks

### Startup Procedure

```bash
# 1. Verify prerequisites
make tei-doctor  # Should show models cached

# 2. Start services
make tei-up

# 3. Verify readiness
make tei-doctor  # All 16 checks should pass
```

### Shutdown Procedure

```bash
make tei-down
```

### Restart Procedure

```bash
make tei-restart
```

### Model Upgrade

```bash
# 1. Stop services
make tei-down

# 2. Clear old cache
rm -rf .cache/tei/models--BAAI--bge-m3
rm -rf .cache/tei/models--BAAI--bge-reranker-v2-m3

# 3. Update environment variables
# Edit .env.local to change model names

# 4. Download new models
make tei-prefetch

# 5. Start with new models
make tei-up

# 6. Verify
make tei-doctor
```

### Rollback to ONNX

If HTTP backend has persistent issues:

```bash
# 1. Stop TEI services
make tei-down

# 2. Update configuration
# Edit .env.local:
NOVEL_ANALYZER_EMBEDDING_BACKEND=onnx
NOVEL_ANALYZER_RERANK_BACKEND=onnx

# 3. Restart application
# No TEI services needed
```

### Switch Between TEI and OpenAI

```bash
# To OpenAI:
# Edit .env.local:
NOVEL_ANALYZER_EMBEDDING_BACKEND=openai
NOVEL_ANALYZER_EMBEDDING_API_BASE=https://api.openai.com
NOVEL_ANALYZER_EMBEDDING_API_KEY=sk-...
NOVEL_ANALYZER_EMBEDDING_API_FORMAT=openai
NOVEL_ANALYZER_EMBEDDING_MODEL_NAME=text-embedding-3-large

# Stop TEI (optional, saves resources)
make tei-down

# To TEI:
# Edit .env.local:
NOVEL_ANALYZER_EMBEDDING_BACKEND=http
NOVEL_ANALYZER_EMBEDDING_API_BASE=http://localhost:8080
NOVEL_ANALYZER_EMBEDDING_API_FORMAT=tei
NOVEL_ANALYZER_EMBEDDING_MODEL_NAME=BAAI/bge-m3

# Start TEI
make tei-up
```

## Performance Tuning

### Batch Size Optimization

- **TEI**: Default 32 is optimal for CPU inference
- **OpenAI**: Use 2048 for maximum throughput
- **Custom**: Set explicitly if you know your service limits

### Connection Reuse

HTTP providers automatically reuse connections via urllib OpenerDirector. No configuration needed.

### Fallback Cascade

Enable for production resilience:
```bash
NOVEL_ANALYZER_EMBEDDING_FALLBACK_BACKEND=onnx
NOVEL_ANALYZER_EMBEDDING_FALLBACK_AFTER_FAILURES=3
```

Behavior:
- After 3 consecutive HTTP failures, switches to ONNX
- Checks HTTP health every 60 seconds
- Automatically switches back when HTTP recovers
- Logs all transitions at INFO level

## Monitoring

### Health Checks

```bash
# Embed service
curl -f http://localhost:8080/health || echo "Embed service down"

# Rerank service
curl -f http://localhost:8081/health || echo "Rerank service down"
```

### Latency Monitoring

```bash
make tei-doctor  # Check 16 shows P50/P95 latency
```

Expected latency (CPU inference):
- Embed: P50 ~400-600ms, P95 ~700-1000ms
- Rerank: P50 ~500-800ms, P95 ~1000-2000ms (Candle fallback slower)

### Log Monitoring

```bash
# Real-time logs
sudo docker logs -f tei-embed
sudo docker logs -f tei-rerank

# Recent errors
sudo docker logs tei-embed --tail 50 | grep -i error
sudo docker logs tei-rerank --tail 50 | grep -i error
```

## Security Considerations

### Network Exposure

Default configuration binds to `localhost` only. For remote access:

```bash
# In tei-up.sh, change:
-p "${EMBED_PORT}:80"
# To:
-p "0.0.0.0:${EMBED_PORT}:80"
```

**Warning**: This exposes TEI to your network. Add authentication or firewall rules.

### API Keys

TEI doesn't require API keys by default. For production:
- Use reverse proxy (nginx/traefik) with authentication
- Or use managed service (OpenAI/Jina/Voyage) with built-in auth

### Model Integrity

Models are downloaded from Hugging Face. Verify checksums if security-critical:
```bash
# Check model files
ls -lh .cache/tei/models--BAAI--bge-m3/snapshots/*/
```

## FAQ

**Q: Can I use GPU with TEI?**
A: Yes, use `ghcr.io/huggingface/text-embeddings-inference:1.6` (without `-cpu` suffix) and add `--gpus all` to docker run.

**Q: Can I run multiple models simultaneously?**
A: Yes, start multiple containers on different ports with different model IDs.

**Q: Does fallback cascade work for rerank?**
A: No, only embedding supports fallback. Rerank fallback semantics are unclear (different models may have incomparable scores).

**Q: How do I know if chunking is working?**
A: Enable debug logging or check that large batches (>32 for TEI, >2048 for OpenAI) don't fail.

**Q: Can I use docker-compose instead of bash scripts?**
A: Yes, `scripts/dev/docker-compose.tei.yml` is available. Use `docker-compose -f scripts/dev/docker-compose.tei.yml up -d`.

## References

- [TEI Documentation](https://github.com/huggingface/text-embeddings-inference)
- [bge-m3 Model Card](https://huggingface.co/BAAI/bge-m3)
- [bge-reranker-v2-m3 Model Card](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- [OpenAI Embeddings API](https://platform.openai.com/docs/guides/embeddings)
