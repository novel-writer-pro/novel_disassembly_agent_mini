#!/usr/bin/env bash
# Restore novel_analyzer dump into a PG instance.
# Usage: restore.sh <dump_file> [host] [port] [user] [db]
set -euo pipefail

DUMP="${1:?usage: restore.sh <dump_file> [host] [port] [user] [db]}"
HOST="${2:-127.0.0.1}"
PORT="${3:-5432}"
USER="${4:-d2}"
DB="${5:-novel_analyzer}"

export PGPASSWORD="${PGPASSWORD:-d2pass}"

echo "[restore] target ${USER}@${HOST}:${PORT}/${DB}"

psql -h "$HOST" -p "$PORT" -U postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname='${DB}'" | grep -q 1 \
  || psql -h "$HOST" -p "$PORT" -U postgres -c "CREATE DATABASE ${DB} OWNER ${USER};"

psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_jieba;
CREATE EXTENSION IF NOT EXISTS pg_textsearch;
SQL

pg_restore \
  -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" \
  --no-owner --no-privileges --clean --if-exists \
  -j 4 \
  "$DUMP"

echo "[restore] verifying"
psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -c "
  SELECT relname, n_live_tup
  FROM pg_stat_user_tables
  WHERE relname IN ('novel_sources','analysis_runs','run_branches','chapter_artifacts','chunk_embeddings')
  ORDER BY relname;"
