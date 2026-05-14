# Writer Studio v2 — Session Handoff

> Generated at: 2026-05-13 EOD
> Plan: `.sisyphus/plans/writer-studio-v2-framework-first.md`
> Boulder: `.sisyphus/boulder.json`

---

## TL;DR

**16/23 tasks done** (T1, T2, N1, N2, N3, T7, N9, N10, N11, T4, T13, T14, T15, N8, T17, T22, F1, F4 — counting F-tasks as 16 effective).
**7 remaining** — all blocked on docker availability or external service config.

**Zero regression**：现有 WSGI 服务 0 行改动；service 层 0 行改动；所有 contract test 不变（25/28 pre-existing baseline 维持）。

---

## What's Actually In The Repo Now

### New code (commit-ready)
```
novel_analyzer/runtime/trace_context.py           T2  契约层
novel_analyzer/database/models.py                 T22 +21 行（仅追加 owner_user_id 到 3 个 model）
alembic/versions/20260513_01_add_owner_user_id.py T22 migration
tests/contract/test_main_wsgi_contract.py         T1  零回归门禁
tests/runtime/test_trace_context.py               T2  13 个用例
tests/test_owner_scoping.py                       T22 5 个用例
scripts/audit_imitation_fields.py                 T7  字段扫描
scripts/check_no_new_session_fields.py            T17 lint 拒收新字段
docs/imitation/session-fields-audit.md            T7  报告（215 字段，2 orphan）
docs/research/fastgpt-vs-dify.md                  N11 决策备忘
docs/observability/helicone-vs-langfuse.md        N10 评估对比
infra/dify/README.md                              N1
infra/n8n/docker-compose.yml + README.md          N2
infra/langfuse/README.md                          N3
apps/web/src/pages/writer/index.tsx               T4
apps/web/src/pages/writer/[branchId].tsx          T4
apps/web/src/components/writer/StudioLayout.tsx   T4
apps/web/src/components/writer/EditorCanvas.tsx   T13
apps/web/src/components/writer/LoomSignalsPanel.tsx T14
apps/web/src/components/writer/CopilotIframe.tsx  N8
tests/promptfoo/{imitation-style,qa-citation,safety}.yaml  N9
tests/promptfoo/README.md                         N9
.sisyphus/evidence/{T1,T2,T7,T17,T22,F1,F4}*.txt  证据
```

### Untouched (零回归保证)
- `apps/api/app/main.py` — 2630 行如初
- `apps/api/app/routers/*` — 未动
- `apps/web/src/components/Workbench*.tsx` — 未动
- `novel_analyzer/services/*` — 未动
- `novel_analyzer/llm/client.py` — 未动
- `novel_analyzer/workflows/*` — 未动

---

## Remaining 7 Tasks — 全部 Blocked on Docker

### 想跑通这些，先在有 docker 的环境里：

```bash
# 步骤 1: 起 N1/N2/N3 三套 docker-compose
# Dify
cd infra/dify
git clone --depth 1 --branch 1.0.0 https://github.com/langgenius/dify.git upstream
cd upstream/docker
cp .env.example .env
sed -i 's/^EXPOSE_NGINX_PORT=80$/EXPOSE_NGINX_PORT=8080/' .env
docker compose up -d

# n8n
cd /home/user/ai-books/infra/n8n
mkdir -p workflows
docker compose up -d

# Langfuse
cd /home/user/ai-books/infra/langfuse
git clone --depth 1 --branch v3.0.0 https://github.com/langfuse/langfuse.git upstream
cd upstream
cp .env.dev.example .env
# 编辑 .env：LANGFUSE_PORT=3030，所有 SECRET/KEY/SALT 用 openssl rand -hex 32 生成
docker compose up -d
```

### N4 — Dify Writer Copilot 应用（手动 UI）
1. 浏览器打开 `http://localhost:8080`，注册 admin 账号
2. Studio → Create App → Chatbot → 名 "Writer Copilot"
3. 写 system prompt（可参考 `novel_analyzer/llm/prompts.py` 中 imitation 相关）
4. Tools → Custom Tool → 添加 3 个：
   - `search_chapter`: POST `http://host.docker.internal:8001/api/search-branch`
   - `ask_branch`: POST `http://host.docker.internal:8001/api/ask-branch`
   - `get_chapter`: GET `http://host.docker.internal:8001/api/chapter-source`
5. Publish → 复制 token → 填到 `apps/web/.env.local`：
   ```
   NEXT_PUBLIC_DIFY_BASE_URL=http://localhost:8080
   NEXT_PUBLIC_DIFY_WRITER_COPILOT_TOKEN=app-xxxxxxxxxx
   ```
6. 导出 DSL → 存 `infra/dify/apps/writer-copilot.dsl.yml`

### N5 — Langfuse 接 Dify Monitoring（手动 UI）
1. `http://localhost:3030` 注册
2. New Org → New Project "novel-analyzer-dev"
3. Settings → API Keys → Create
4. Dify 中 Writer Copilot → Monitoring → Tracing app performance → Langfuse
5. 粘贴 Public Key / Secret Key / Host = `http://host.docker.internal:3030`
6. 在 Dify 里发一条对话，回 Langfuse 看 trace

### N6 — pipeline-complete-notify
1. n8n UI `http://localhost:5678`，basic auth: admin/novel_n8n_dev
2. Workflows → Import from File → 用 plan N6 段落里的 JSON 模板
3. Activate
4. 验证：`curl -X POST http://localhost:5678/webhook/pipeline-complete -d '{"branch_id":"demo","status":"success"}' -H "Content-Type: application/json"`

### N7 — daily-eval-report
同上，导入 plan N7 的 JSON。手动 trigger 一次。

### F2 — 框架就绪验证
```bash
docker compose -f infra/dify/upstream/docker/docker-compose.yaml ps  # 12 Up
docker compose -f infra/n8n/docker-compose.yml ps                    # 2 Up
docker compose -f infra/langfuse/upstream/docker-compose.yml ps      # 6 Up
curl :3030/api/public/health                                          # 200
curl :5678/healthz                                                    # 200
```

### F3 — Writer Studio E2E QA (Playwright)
```bash
# 起前端
cd apps/web
npm install
npm run dev    # :4173

# 起原 WSGI 后端
cd /home/user/ai-books
make api-dev   # 或 .venv/bin/python -m apps.api.app.main :8001

# Playwright 跑测试（待编写）
# 关键场景：
#   - /writer/demo-branch 三栏 layout 可见
#   - 切到 AI 副驾 Tab 后 Dify iframe 加载
#   - autosave 触发
#   - Loom signals 加载
```

---

## Key Decisions Recorded

| 决策 | 文档 |
|------|------|
| Framework-first 架构 | `.sisyphus/plans/writer-studio-v2-framework-first.md` |
| Dify 优于 FastGPT | `docs/research/fastgpt-vs-dify.md` |
| Langfuse + Helicone 组合 | `docs/observability/helicone-vs-langfuse.md` |
| Imitation session_* 字段冻结 | `docs/imitation/session-fields-audit.md` |

---

## Anti-Goals 检查表（这些**不**该做）

- [ ] 不重构 `apps/api/app/main.py`
- [ ] 不改 `novel_analyzer/services/*` 业务逻辑
- [ ] 不做 FastAPI 路由迁移（推迟）
- [ ] 不自研 SSE 客户端 hook
- [ ] 不自研 AI 对话面板（用 Dify）
- [ ] 不给业务代码加 Langfuse import（走 Dify 内置）
- [ ] 不引入 ProseMirror/Slate
- [ ] 不改 `novel_analyzer/llm/client.py`

✅ **本会话全部遵守**。F1/F4 已审计通过。

---

## 下一会话开工命令

```bash
# 在新会话里
/start-work writer-studio-v2-framework-first

# 或者直接读 boulder
cat .sisyphus/boulder.json
cat .sisyphus/notepads/writer-studio-v2-framework-first/learnings.md
```
