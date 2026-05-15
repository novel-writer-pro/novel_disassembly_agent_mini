#!/usr/bin/env bash
set -euo pipefail

log() { printf '[entrypoint] %s\n' "$*"; }

if [ "${NOVEL_ANALYZER_RUN_MIGRATIONS:-1}" = "1" ]; then
  log "waiting for postgres at ${NOVEL_ANALYZER_DB_HOST}:${NOVEL_ANALYZER_DB_PORT}"
  for i in $(seq 1 60); do
    if PGPASSWORD="${NOVEL_ANALYZER_DB_PASSWORD:-}" pg_isready \
        -h "${NOVEL_ANALYZER_DB_HOST}" \
        -p "${NOVEL_ANALYZER_DB_PORT}" \
        -U "${NOVEL_ANALYZER_DB_USER}" >/dev/null 2>&1; then
      break
    fi
    sleep 1
    if [ "$i" = "60" ]; then
      log "postgres unreachable after 60s; continuing anyway"
    fi
  done

  log "running alembic upgrade head"
  if ! alembic upgrade head 2>&1 | sed 's/^/[alembic] /'; then
    log "alembic failed; continuing so app can start in degraded mode"
  fi
fi

exec "$@"
