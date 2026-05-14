# v3 Pickup Checklist

> 在 docker-enabled 环境从零跑通 v3 业务闭环的步骤清单。
> 配合 `docs/runbook/business-loop.md` 一起用 — 这份是「按顺序勾选」，那份是「症状排查」。

## Pre-flight

- [ ] PR #8 (v2) 已 merge 到 master
- [ ] PR #9 (v3) 已 merge 或 checkout 本地
- [ ] `docker compose version` 返回 v2.24+
- [ ] 当前 user 在 docker group 或有 sudo
- [ ] 至少 10GB 可用磁盘
- [ ] 端口 8011 / 4173 / 8080 / 5678 / 3030 / 8585 / 8586 全部空闲

## Stage 1 — 起 4 套 docker stack

- [ ] `make v2-up-all` 拉起 Dify + n8n + Langfuse（v2 已就位）
  ```bash
  bash scripts/verify_infra.sh   # 三套全 healthy
  ```
- [ ] 起 Helicone（v3 新增）
  ```bash
  cd infra/helicone
  git clone --depth 1 --branch v1 https://github.com/Helicone/helicone.git upstream
  cd upstream && cp .env.example .env
  # 编辑 .env：把 OPENAI_PROXY_PORT 改 8585，WEB_PORT 改 8586
  docker compose up -d
  curl http://localhost:8585/healthcheck   # 200
  ```

## Stage 2 — Dify Studio 配置（手动 UI，约 15 分钟）

- [ ] 浏览器打开 http://localhost:8080，注册 admin
- [ ] Studio → Tools → Custom → Create
  - [ ] Schema 标签页：粘贴 `infra/dify/apps/novel-analyzer-tools.openapi.yaml`
  - [ ] Save → 自动检测出 search_chapter / ask_branch / get_chapter_source
- [ ] 三个 tool 各自的 **Headers** 配置：添加 `X-User-Id` = `{{system.user_id}}`（v3 关键步骤）
- [ ] Studio → Apps → Import DSL → 选 `infra/dify/apps/writer-copilot.dsl.yml`
- [ ] 关联刚配的 3 个 Custom Tool
- [ ] Publish → 复制 token
- [ ] 写入 `apps/web/.env.local`：
  ```
  NEXT_PUBLIC_DIFY_BASE_URL=http://localhost:8080
  NEXT_PUBLIC_DIFY_WRITER_COPILOT_TOKEN=app-xxxxxxxxxx
  ```

## Stage 3 — Langfuse 接 Dify（约 5 分钟）

- [ ] 浏览器打开 http://localhost:3030，注册 admin
- [ ] New Org → New Project `novel-analyzer-dev`
- [ ] Settings → API Keys → Create
- [ ] 记录 Public Key / Secret Key
- [ ] Dify → Writer Copilot → Monitoring → Tracing app performance → Langfuse
- [ ] 粘贴 Public/Secret Key、Host = `http://host.docker.internal:3030`
- [ ] 在 Dify 里发一条对话 → 回 Langfuse Traces 页面看到记录

## Stage 4 — n8n 导入 workflow（约 3 分钟）

- [ ] 浏览器打开 http://localhost:5678，basic auth admin / novel_n8n_dev
- [ ] Workflows → Import → 选 `infra/n8n/workflows/pipeline-complete-notify.json`
- [ ] Activate
- [ ] Workflows → Import → 选 `infra/n8n/workflows/daily-eval-report.json`
- [ ] Activate

## Stage 5 — ai-books backend 配 v3 env（约 2 分钟）

- [ ] 设环境变量：
  ```bash
  export NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE='http://localhost:8585/v1/openai'
  export N8N_WEBHOOK_PIPELINE_COMPLETE_URL='http://localhost:5678/webhook/pipeline-complete'
  ```
- [ ] 跑 alembic upgrade head（v2 的 owner_user_id 列）
- [ ] 起后端：`make api-dev   # FastAPI on :8011 via uvicorn`

## Stage 6 — 端到端 smoke（按 `docs/runbook/business-loop.md` 6 步）

- [ ] Step 1：alice 上传一本书 → 拿到 branch_id
- [ ] Step 2：双 user library 隔离验证（alice 看到，bob 看不到）
- [ ] Step 3：alice 跑 imitation
- [ ] Step 4：n8n executions 出现 success
- [ ] Step 5：Langfuse traces 含 user_id=alice
- [ ] Step 6：Dify 里发问 → 后端日志可见 X-User-Id

## 失败时

→ 翻 `docs/runbook/business-loop.md` 第二部分 5 个症状定位章节。

## 完成后回报

跑通后请把以下信息回填到 PR #9 review comment：
- 哪一步遇到了文档没覆盖的细节？
- Dify systemVariables 模板语法是 `{{system.user_id}}` 还是其他？（不同版本不一样）
- Helicone .env 实际字段名是否与 README 假设一致？

这些信息会进 v4 改进 v2/v3 文档。
