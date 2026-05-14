# Writer Studio Playwright Tests

> v2 plan F3 verification scaffold. Runs against `/writer/*` route group.

## Setup

```bash
cd /home/user/ai-books
npx --yes playwright@latest install --with-deps chromium
```

## Run

```bash
# Default: tests against http://localhost:4173 (next dev server)
cd apps/web && npm run dev &      # start frontend
cd /home/user/ai-books
npx playwright test tests/playwright/writer-studio.spec.ts

# Different base URL
WRITER_STUDIO_BASE=http://localhost:3000 npx playwright test ...
```

## What's tested

| Scenario | Verifies |
|----------|----------|
| empty branch CTA | T4 empty state |
| three-pane layout | T4 layout shell |
| editor input + autosave | T13 EditorCanvas |
| Loom + Copilot tabs | T14 + N8 right sider |
| no Workbench leak | T4 isolation guarantee |

## Acceptance for F3

All 5 specs pass = F3 APPROVE.

If `AI 副驾` tab shows the token-warning placeholder (because N4 not done), that still counts as PASS — the iframe is correctly attempting to render but env not configured. The warning element is part of the assertion (`copilotIframe.or(tokenWarning)`).
