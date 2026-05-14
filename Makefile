.PHONY: help v2-test v2-build v2-audit v2-lint v2-snapshot v2-status \
	v2-up-all v2-down-all v2-pickup-checklist

help:
	@echo "Writer Studio v2 Targets:"
	@echo "  make v3-smoke      - Run v3 e2e suite (no docker required)"
	@echo "  make v2-test       - Run all in-scope backend tests (contract + runtime + scoping)"
	@echo "  make v2-build      - Frontend Next.js production build"
	@echo "  make v2-audit      - Re-run imitation session_* field audit"
	@echo "  make v2-lint       - Lint: assert no new session_* fields"
	@echo "  make v2-snapshot   - Regenerate tests/contract/baseline.snapshot.json"
	@echo "  make v2-status     - Show plan progress"
	@echo "  make v2-up-all     - (needs docker) bring up dify + n8n + langfuse"
	@echo "  make v2-down-all   - (needs docker) tear down dify + n8n + langfuse"
	@echo "  make v2-pickup-checklist - Step-by-step pickup guide for next session"

# --- Writer Studio v2 ---

v2-test:
	.venv/bin/pytest tests/contract/ tests/runtime/ tests/test_owner_scoping.py -v --tb=short

v2-build:
	cd apps/web && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/next build

v2-audit:
	.venv/bin/python scripts/audit_imitation_fields.py

v2-lint:
	.venv/bin/python scripts/check_no_new_session_fields.py

v2-snapshot:
	.venv/bin/python scripts/capture_contract_snapshot.py

v3-smoke:
	@echo "Running v3 e2e suite (no docker required)..."
	.venv/bin/pytest tests/e2e/ tests/api/middleware/ tests/runtime/test_notify.py -v --tb=short
	@echo ""
	@echo "For end-to-end verification with running infra, see:"
	@echo "  docs/runbook/business-loop.md"

v2-status:
	@echo "=== Plan progress ==="
	@grep -c '^- \[x\] \*\*[NTF][0-9]' .sisyphus/plans/writer-studio-v2-framework-first.md | xargs -I{} echo "  Completed: {}"
	@grep -c '^- \[ \] \*\*[NTF][0-9]' .sisyphus/plans/writer-studio-v2-framework-first.md | xargs -I{} echo "  Remaining: {}"
	@echo ""
	@echo "Remaining tasks:"
	@grep '^- \[ \] \*\*[NTF][0-9]' .sisyphus/plans/writer-studio-v2-framework-first.md

v2-pickup-checklist:
	@echo "=========================================================="
	@echo "Writer Studio v2 — Pickup Checklist (run on docker-enabled host)"
	@echo "=========================================================="
	@echo ""
	@echo "PREREQUISITES:"
	@echo "  - docker compose v2 (docker compose --version)"
	@echo "  - User in docker group (groups | grep docker) OR rootless podman"
	@echo "  - ~10 GB disk space"
	@echo "  - Network access (langgenius/dify and langfuse/langfuse repos)"
	@echo ""
	@echo "STEP 1: Bring up infra (handles git clones automatically)"
	@echo "  $$ make v2-up-all"
	@echo ""
	@echo "STEP 2: Verify all stacks healthy (writes evidence file)"
	@echo "  $$ bash scripts/verify_infra.sh"
	@echo "  -> Marks F2 done"
	@echo ""
	@echo "STEP 3: Configure Dify Writer Copilot (manual UI, ~10 min)"
	@echo "  Open http://localhost:8080"
	@echo "  Studio -> Apps -> Import DSL -> infra/dify/apps/writer-copilot.dsl.yml"
	@echo "  Tools -> Custom -> Import OpenAPI -> infra/dify/apps/novel-analyzer-tools.openapi.yaml"
	@echo "  Publish -> Copy token -> apps/web/.env.local"
	@echo "  -> Marks N4 done"
	@echo ""
	@echo "STEP 4: Wire Langfuse to Dify (manual UI, ~5 min)"
	@echo "  Open http://localhost:3030 -> create org/project -> get keys"
	@echo "  Open http://localhost:8080 -> Writer Copilot -> Monitoring -> Langfuse -> paste keys"
	@echo "  -> Marks N5 done"
	@echo ""
	@echo "STEP 5: Import n8n workflows (~3 min)"
	@echo "  Open http://localhost:5678 (admin / novel_n8n_dev)"
	@echo "  Workflows -> Import -> infra/n8n/workflows/pipeline-complete-notify.json -> Activate"
	@echo "  Workflows -> Import -> infra/n8n/workflows/daily-eval-report.json -> Activate"
	@echo "  -> Marks N6 + N7 done"
	@echo ""
	@echo "STEP 6: E2E test (Playwright)"
	@echo "  $$ npx --yes playwright@latest install --with-deps chromium"
	@echo "  $$ cd apps/web && npm run dev &"
	@echo "  $$ npx playwright test tests/playwright/writer-studio.spec.ts"
	@echo "  -> Marks F3 done"
	@echo ""
	@echo "After all 6: open .sisyphus/plans/writer-studio-v2-framework-first.md"
	@echo "             and check the remaining 6 boxes."
	@echo "             Plan completion: 23/23"

v2-up-all:
	@if [ ! -d infra/dify/upstream ]; then \
	  cd infra/dify && git clone --depth 1 --branch 1.0.0 https://github.com/langgenius/dify.git upstream && \
	  cd upstream/docker && cp .env.example .env && \
	  sed -i 's/^EXPOSE_NGINX_PORT=80$$/EXPOSE_NGINX_PORT=8080/' .env; \
	fi
	@if [ ! -d infra/langfuse/upstream ]; then \
	  cd infra/langfuse && git clone --depth 1 --branch v3.0.0 https://github.com/langfuse/langfuse.git upstream && \
	  cd upstream && cp .env.dev.example .env 2>/dev/null || cp .env.example .env; \
	fi
	docker compose -f infra/dify/upstream/docker/docker-compose.yaml up -d
	docker compose -f infra/n8n/docker-compose.yml up -d
	docker compose -f infra/langfuse/upstream/docker-compose.yml up -d
	bash scripts/verify_infra.sh

v2-down-all:
	-docker compose -f infra/dify/upstream/docker/docker-compose.yaml down 2>/dev/null
	-docker compose -f infra/n8n/docker-compose.yml down
	-docker compose -f infra/langfuse/upstream/docker-compose.yml down 2>/dev/null
