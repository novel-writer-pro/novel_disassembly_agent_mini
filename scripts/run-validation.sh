#!/usr/bin/env bash
# Pre-prod validation suite — runs §7 of deployment-and-operations-manual-20260515.md
#
# Usage:
#   bash scripts/run-validation.sh                       # full suite
#   bash scripts/run-validation.sh --quick               # skip slow tests (e2e + bm25)
#   bash scripts/run-validation.sh --branch <branch_id>  # also run BM25 sanity benchmark
#
# Exit 0 if all sections pass, 1 otherwise.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

QUICK=0
BRANCH=""
while [ $# -gt 0 ]; do
    case "$1" in
        --quick) QUICK=1 ;;
        --branch) BRANCH="$2"; shift ;;
        --help)
            sed -n '1,11p' "$0" | grep -E '^#' | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 2 ;;
    esac
    shift
done

if [ ! -f .venv/bin/activate ]; then
    echo "ERR: .venv not found. Run \`python3.11 -m venv .venv && pip install -e .\` first."
    exit 1
fi
source .venv/bin/activate

FAIL=0
section() { echo; echo "============================================="; echo "  $1"; echo "============================================="; }
ok() { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

section "Section 1: heuristic scorer regression"
if pytest tests/test_ai_trace_signal_service.py tests/test_slop_scorer_service.py \
          tests/test_elo_tournament_service.py tests/test_factscore_lite_service.py \
          tests/test_persona_correlation_service.py tests/test_loom_ab_comparison_service.py \
          -q --tb=no 2>&1 | tail -3 | grep -qE "passed"; then
    ok "B1+B4+B5+T7+T8+T5 scoring helpers all green"
else
    fail "scoring helpers failed"
fi

section "Section 2: scaffold cascade regression"
if pytest tests/test_loom_signal_scaffold_filter.py tests/test_scaffold_carry_over_filter.py \
          -q --tb=no 2>&1 | tail -3 | grep -qE "passed"; then
    ok "scaffold filter regressions hold"
else
    fail "scaffold cascade test failures"
fi

section "Section 3: kernel service tests"
if pytest tests/test_retrieval_service.py tests/test_domain_dictionary_service.py \
          tests/test_imitation_harness_service.py tests/test_chapter_imitation_service.py \
          tests/test_loom_phase2.py \
          -q --tb=no 2>&1 | tail -3 | grep -qE "passed"; then
    ok "retrieval / dict / imitation / loom kernel tests green"
else
    fail "kernel test failure"
fi

section "Section 4: contract tests (FastAPI canonical surface)"
if pytest tests/contract/ -q --tb=no 2>&1 | tail -3 | grep -qE "passed"; then
    ok "FastAPI contract intact"
else
    fail "contract drift detected"
fi

if [ "$QUICK" -eq 0 ]; then
    section "Section 5: e2e LLM override + owner scoping + anti-spoiler"
    if pytest tests/e2e/test_llm_base_url_override.py tests/e2e/test_owner_scoping_e2e.py \
              tests/e2e/test_anti_spoiler.py -q --tb=no 2>&1 | tail -3 | grep -qE "passed"; then
        ok "e2e suite green"
    else
        fail "e2e regression"
    fi

    if [ -n "$BRANCH" ]; then
        section "Section 6: BM25 jiebacfg vs simple sanity (--branch $BRANCH)"
        OUT=".sisyphus/reports/bm25-validation-$(date +%F).json"
        mkdir -p "$(dirname "$OUT")"
        if python -m novel_analyzer.cli.app retrieval-benchmark "$BRANCH" \
                  --max-queries 20 --output-file "$OUT" >/dev/null 2>&1 && [ -s "$OUT" ]; then
            JIEBA=$(jq '.results[] | select(.config=="jiebacfg") | .mrr' "$OUT")
            SIMPLE=$(jq '.results[] | select(.config=="simple") | .mrr' "$OUT")
            if awk "BEGIN { exit !($JIEBA >= $SIMPLE) }"; then
                ok "jiebacfg MRR ($JIEBA) >= simple MRR ($SIMPLE) — pg_jieba healthy"
            else
                fail "jiebacfg MRR ($JIEBA) < simple ($SIMPLE) — investigate userdict (run: python -m novel_analyzer.cli.app domain-dict-rebuild)"
            fi
        else
            fail "retrieval-benchmark did not produce a report (check provider-health + DB)"
        fi
    else
        echo
        echo "  (skipped) BM25 benchmark — pass --branch <branch_id> to enable"
    fi
else
    echo
    echo "  (skipped sections 5-6 in --quick mode)"
fi

echo
echo "============================================="
if [ $FAIL -eq 0 ]; then
    echo "  ALL SECTIONS PASSED"
    exit 0
else
    echo "  $FAIL SECTION(S) FAILED — see output above"
    exit 1
fi
