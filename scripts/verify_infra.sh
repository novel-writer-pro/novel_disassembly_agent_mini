#!/usr/bin/env bash
set -uo pipefail

# F2 — Framework readiness verification
# Run after `docker compose up -d` for all 3 stacks (N1/N2/N3).
# Outputs to .sisyphus/evidence/F2-framework-ready.txt

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/.sisyphus/evidence/F2-framework-ready.txt"
mkdir -p "$(dirname "$OUT")"

{
  echo "F2 — Framework Readiness Verification"
  echo "================================================"
  echo "Generated: $(date -Iseconds)"
  echo ""
  echo "## A. Compose stacks status"
  echo ""
  echo "### Dify"
  if [ -f "$ROOT/infra/dify/upstream/docker/docker-compose.yaml" ]; then
    docker compose -f "$ROOT/infra/dify/upstream/docker/docker-compose.yaml" ps 2>&1 || true
  else
    echo "(infra/dify/upstream not cloned — see infra/dify/README.md step 1)"
  fi
  echo ""
  echo "### n8n"
  if [ -f "$ROOT/infra/n8n/docker-compose.yml" ]; then
    docker compose -f "$ROOT/infra/n8n/docker-compose.yml" ps 2>&1 || true
  fi
  echo ""
  echo "### Langfuse"
  if [ -f "$ROOT/infra/langfuse/upstream/docker-compose.yml" ]; then
    docker compose -f "$ROOT/infra/langfuse/upstream/docker-compose.yml" ps 2>&1 || true
  else
    echo "(infra/langfuse/upstream not cloned — see infra/langfuse/README.md step 1)"
  fi
  echo ""
  echo "## B. Health endpoints"
  echo ""
  for label_url in \
      "Dify nginx       http://localhost:8080/console/api/version" \
      "Dify nginx alt   http://localhost:8080" \
      "n8n              http://localhost:5678/healthz" \
      "Langfuse health  http://localhost:3030/api/public/health"
  do
    label="${label_url%% http*}"
    url="http${label_url##* http}"
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>&1 || echo "ERR")
    printf "  %-20s %-60s -> %s\n" "$label" "$url" "$code"
  done
  echo ""
  echo "## C. Backend reachable from Dify container"
  echo ""
  echo '$ docker exec <dify-api-container> curl -s http://host.docker.internal:8001/api/library | jq .items[0] | head -3'
  echo "(run manually after stacks are up)"
  echo ""
  echo "## VERDICT"
  echo "All 3 stacks reporting 'running' and health endpoints returning 200 = APPROVE"
  echo "Any 'ERR' or non-2xx = INVESTIGATE before declaring framework ready"
} | tee "$OUT"

echo ""
echo "Saved: $OUT"
