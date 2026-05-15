#!/usr/bin/env bash
# Usage: dump.sh [output_path]
# Dumps novel_analyzer DB from the running compose pg container into MIGRATE_DIR.
set -euo pipefail

OUT="${1:-/migrate/novel_analyzer.dump}"
CONTAINER="${PG_CONTAINER:-novel-analyzer-pg}"

docker exec "$CONTAINER" pg_dump \
  -U "${NOVEL_ANALYZER_DB_USER:-d2}" \
  -d "${NOVEL_ANALYZER_DB_NAME:-novel_analyzer}" \
  --format=custom --no-owner --no-privileges \
  -f "$OUT"

echo "[dump] wrote ${OUT} (inside ${CONTAINER}; host path = MIGRATE_DIR)"
docker exec "$CONTAINER" ls -lh "$OUT"
