#!/usr/bin/env bash
# Usage: supervisor.sh <book_label> <run_id> <branch_id> <start> <end>
set -u
LABEL="$1"
RUN_ID="$2"
BRANCH_ID="$3"
START="$4"
END="$5"

PROJECT_DIR="${PROJECT_DIR:-/home/user/ai-books}"
LOG_DIR="${LOG_DIR:-/tmp/booklogs}"
mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"
set -a; source .env.local; set +a

PSQL="env PGPASSWORD=${NOVEL_ANALYZER_DB_PASSWORD:-d2pass} psql -h ${NOVEL_ANALYZER_DB_HOST:-127.0.0.1} -p ${NOVEL_ANALYZER_DB_PORT:-5432} -U ${NOVEL_ANALYZER_DB_USER:-d2} -d ${NOVEL_ANALYZER_DB_NAME:-novel_analyzer} -tA"

log() { echo "[$LABEL $(date +%H:%M:%S)] $*"; }

CONSEC_FAIL=0
for ch in $(seq "$START" "$END"); do
  state=$($PSQL -c "SELECT status FROM chapter_jobs WHERE branch_id='$BRANCH_ID' AND chapter_index=$ch;" 2>/dev/null)
  if [ "$state" = "validated" ]; then
    continue
  fi
  if [ "$state" = "failed" ] || [ "$state" = "running" ]; then
    $PSQL -c "UPDATE chapter_jobs SET status='pending', started_at=NULL, finished_at=NULL, last_error=NULL, attempts=0 WHERE branch_id='$BRANCH_ID' AND chapter_index=$ch;" >/dev/null
  fi

  log "ch$ch start"
  start_ts=$(date +%s)
  if timeout 600 .venv/bin/python -m novel_analyzer.cli.app analyze-range \
        "$RUN_ID" "$BRANCH_ID" "$ch" "$ch" >"$LOG_DIR/${LABEL}-ch${ch}.log" 2>&1; then
    elapsed=$(( $(date +%s) - start_ts ))
    log "ch$ch OK (${elapsed}s)"
    CONSEC_FAIL=0
    rm -f "$LOG_DIR/${LABEL}-ch${ch}.log"
  else
    elapsed=$(( $(date +%s) - start_ts ))
    err=$(tail -3 "$LOG_DIR/${LABEL}-ch${ch}.log" 2>/dev/null | tr '\n' ' ' | head -c 240)
    log "ch$ch FAIL (${elapsed}s) :: $err"
    $PSQL -c "UPDATE chapter_jobs SET status='failed', last_error='supervisor: parse/timeout', finished_at=now() WHERE branch_id='$BRANCH_ID' AND chapter_index=$ch AND status IN ('pending','running');" >/dev/null
    CONSEC_FAIL=$((CONSEC_FAIL+1))
    if [ "$CONSEC_FAIL" -ge 5 ]; then
      log "5 consecutive failures, sleeping 120s"
      sleep 120
      CONSEC_FAIL=0
    else
      sleep 5
    fi
  fi
done
log "DONE range $START-$END"
