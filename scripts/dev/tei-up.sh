#!/usr/bin/env bash
# Start TEI embedding and rerank containers with proper readiness checks.
#
# IMPORTANT: Run scripts/dev/tei-prefetch.py FIRST to download models.
# This script expects models to be cached in .cache/tei/ on the host.
#
# Environment variables:
#   TEI_IMAGE: Docker image (default: ghcr.io/huggingface/text-embeddings-inference:cpu-1.6)
#   TEI_CACHE_DIR: Host cache directory (default: $PWD/.cache/tei)
#   TEI_HF_ENDPOINT: HF mirror for container fallback (default: https://hf-mirror.com)
#   TEI_EMBED_MODEL: Embedding model ID (default: BAAI/bge-m3)
#   TEI_RERANK_MODEL: Rerank model ID (default: BAAI/bge-reranker-v2-m3)
#   TEI_EMBED_PORT: Host port for embedding (default: 8080)
#   TEI_RERANK_PORT: Host port for rerank (default: 8081)

set -euo pipefail

# Detect docker command with sudo if needed
DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
  if sudo -n docker info >/dev/null 2>&1; then
    DOCKER="sudo docker"
    echo "Using 'sudo docker' (passwordless sudo detected)"
  else
    echo "ERROR: docker not accessible. Add yourself to docker group or configure passwordless sudo." >&2
    exit 1
  fi
fi

# Configuration
TEI_IMAGE="${TEI_IMAGE:-ghcr.io/huggingface/text-embeddings-inference:cpu-1.6}"
TEI_CACHE_DIR="${TEI_CACHE_DIR:-$PWD/.cache/tei}"
TEI_HF_ENDPOINT="${TEI_HF_ENDPOINT:-https://hf-mirror.com}"
TEI_EMBED_MODEL="${TEI_EMBED_MODEL:-BAAI/bge-m3}"
TEI_RERANK_MODEL="${TEI_RERANK_MODEL:-BAAI/bge-reranker-v2-m3}"
TEI_EMBED_PORT="${TEI_EMBED_PORT:-8080}"
TEI_RERANK_PORT="${TEI_RERANK_PORT:-8081}"

echo "TEI Startup Configuration:"
echo "  Image: $TEI_IMAGE"
echo "  Cache: $TEI_CACHE_DIR"
echo "  HF Endpoint: $TEI_HF_ENDPOINT"
echo "  Embed: $TEI_EMBED_MODEL (port $TEI_EMBED_PORT)"
echo "  Rerank: $TEI_RERANK_MODEL (port $TEI_RERANK_PORT)"
echo ""

# Pre-flight checks
echo "Pre-flight checks..."

# Check cache directory exists
if [[ ! -d "$TEI_CACHE_DIR" ]]; then
  echo "ERROR: Cache directory not found: $TEI_CACHE_DIR" >&2
  echo "Run: python scripts/dev/tei-prefetch.py" >&2
  exit 1
fi

# Check embed model cache
EMBED_CACHE="$TEI_CACHE_DIR/models--${TEI_EMBED_MODEL//\//--}"
if [[ ! -d "$EMBED_CACHE" ]]; then
  echo "ERROR: Embed model not cached: $EMBED_CACHE" >&2
  echo "Run: python scripts/dev/tei-prefetch.py" >&2
  exit 1
fi

EMBED_SIZE=$(du -sb "$EMBED_CACHE" 2>/dev/null | cut -f1)
if [[ "$EMBED_SIZE" -lt 1000000000 ]]; then
  echo "ERROR: Embed model cache too small: $EMBED_SIZE bytes (expected >1GB)" >&2
  echo "Run: python scripts/dev/tei-prefetch.py" >&2
  exit 1
fi
echo "✓ Embed model cached: $(du -sh "$EMBED_CACHE" | cut -f1)"

# Check rerank model cache
RERANK_CACHE="$TEI_CACHE_DIR/models--${TEI_RERANK_MODEL//\//--}"
if [[ ! -d "$RERANK_CACHE" ]]; then
  echo "ERROR: Rerank model not cached: $RERANK_CACHE" >&2
  echo "Run: python scripts/dev/tei-prefetch.py" >&2
  exit 1
fi

RERANK_SIZE=$(du -sb "$RERANK_CACHE" 2>/dev/null | cut -f1)
if [[ "$RERANK_SIZE" -lt 1000000000 ]]; then
  echo "ERROR: Rerank model cache too small: $RERANK_SIZE bytes (expected >1GB)" >&2
  echo "Run: python scripts/dev/tei-prefetch.py" >&2
  exit 1
fi
echo "✓ Rerank model cached: $(du -sh "$RERANK_CACHE" | cut -f1)"

# Check ports available
if lsof -Pi :$TEI_EMBED_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "ERROR: Port $TEI_EMBED_PORT already in use" >&2
  exit 1
fi
echo "✓ Port $TEI_EMBED_PORT available"

if lsof -Pi :$TEI_RERANK_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "ERROR: Port $TEI_RERANK_PORT already in use" >&2
  exit 1
fi
echo "✓ Port $TEI_RERANK_PORT available"

echo ""
echo "Starting containers..."

$DOCKER rm -f tei-embed tei-rerank 2>/dev/null || true

$DOCKER run -d --name tei-embed \
  -p "${TEI_EMBED_PORT}:80" \
  -v "${TEI_CACHE_DIR}:/data" \
  -e HF_ENDPOINT="${TEI_HF_ENDPOINT}" \
  "${TEI_IMAGE}" \
  --model-id "${TEI_EMBED_MODEL}" \
  --max-client-batch-size 32

echo "✓ Started tei-embed container"

$DOCKER run -d --name tei-rerank \
  -p "${TEI_RERANK_PORT}:80" \
  -v "${TEI_CACHE_DIR}:/data" \
  -e HF_ENDPOINT="${TEI_HF_ENDPOINT}" \
  "${TEI_IMAGE}" \
  --model-id "${TEI_RERANK_MODEL}" \
  --max-client-batch-size 32

echo "✓ Started tei-rerank container"
echo ""

# Wait for readiness with actual inference test
echo "Waiting for services to be ready (up to 300s)..."

wait_for_service() {
  local name=$1
  local port=$2
  local test_endpoint=$3
  local test_payload=$4
  
  for i in $(seq 1 60); do
    if curl -sf "http://localhost:${port}/health" >/dev/null 2>&1; then
      if curl -sf -X POST "http://localhost:${port}${test_endpoint}" \
           -H "Content-Type: application/json" \
           -d "$test_payload" >/dev/null 2>&1; then
        echo "✓ $name ready (${i}x5s)"
        return 0
      fi
    fi
    sleep 5
  done
  
  echo "ERROR: $name failed to become ready after 300s" >&2
  echo "Last 20 lines of container logs:" >&2
  $DOCKER logs --tail 20 "$name" >&2
  return 1
}

if ! wait_for_service "tei-embed" "$TEI_EMBED_PORT" "/embed" '{"inputs":["test"]}'; then
  exit 1
fi

if ! wait_for_service "tei-rerank" "$TEI_RERANK_PORT" "/rerank" '{"query":"test","texts":["a","b"]}'; then
  exit 1
fi

echo ""
echo "Verification..."

# Verify embed dimension
EMBED_RESPONSE=$(curl -sf -X POST "http://localhost:${TEI_EMBED_PORT}/embed" \
  -H "Content-Type: application/json" \
  -d '{"inputs":["hello world"]}')
EMBED_DIM=$(echo "$EMBED_RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin)[0]))")
echo "✓ Embed dimension: $EMBED_DIM"

# Verify rerank score
RERANK_RESPONSE=$(curl -sf -X POST "http://localhost:${TEI_RERANK_PORT}/rerank" \
  -H "Content-Type: application/json" \
  -d '{"query":"machine learning","texts":["AI and ML","cooking recipes"]}')
RERANK_SCORE=$(echo "$RERANK_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['score'])")
echo "✓ Rerank sample score: $RERANK_SCORE"

echo ""
echo "=========================================="
echo "TEI services ready!"
echo "  Embed:  http://localhost:$TEI_EMBED_PORT"
echo "  Rerank: http://localhost:$TEI_RERANK_PORT"
echo "=========================================="
