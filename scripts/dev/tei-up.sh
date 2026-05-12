#!/usr/bin/env bash
set -euo pipefail

CACHE_DIR="${TEI_CACHE_DIR:-$PWD/.cache/tei}"
mkdir -p "$CACHE_DIR"

EMBED_IMAGE="ghcr.io/huggingface/text-embeddings-inference:cpu-1.6"
EMBED_MODEL="${TEI_EMBED_MODEL:-BAAI/bge-m3}"
EMBED_PORT="${TEI_EMBED_PORT:-8080}"

RERANK_IMAGE="ghcr.io/huggingface/text-embeddings-inference:cpu-1.6"
RERANK_MODEL="${TEI_RERANK_MODEL:-BAAI/bge-reranker-v2-m3}"
RERANK_PORT="${TEI_RERANK_PORT:-8081}"

sudo docker rm -f tei-embed tei-rerank 2>/dev/null || true

sudo docker run -d --name tei-embed \
  -p "${EMBED_PORT}:80" \
  -v "${CACHE_DIR}:/data" \
  "${EMBED_IMAGE}" \
  --model-id "${EMBED_MODEL}" \
  --max-client-batch-size 32

sudo docker run -d --name tei-rerank \
  -p "${RERANK_PORT}:80" \
  -v "${CACHE_DIR}:/data" \
  "${RERANK_IMAGE}" \
  --model-id "${RERANK_MODEL}" \
  --max-client-batch-size 32

echo "Waiting for servers (up to 180s)..."
for _ in $(seq 1 60); do
  if curl -sf "http://localhost:${EMBED_PORT}/health" >/dev/null && \
     curl -sf "http://localhost:${RERANK_PORT}/health" >/dev/null; then
    echo "TEI up: embed=${EMBED_PORT}, rerank=${RERANK_PORT}"
    exit 0
  fi
  sleep 3
done
echo "Timed out waiting for TEI servers"
exit 1
