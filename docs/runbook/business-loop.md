# Business Loop Runbook (v3)

> 验证作家用户的端到端体验：上传 → 仿写 → 通知 → trace 可见。
> 前置：v2 PR 已 merge（master 已含 owner_user_id 列）+ Dify/n8n/Langfuse/Helicone 全部 up。

## 前置 checklist

```bash
make v2-pickup-checklist        # 看 v2 docker stacks 怎么起
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'dify|n8n|langfuse|helicone'
```

需要看到至少：dify-nginx / n8n / langfuse-web / helicone（任何一个挂的就跑不出 v3 闭环）。

## 启动顺序

1. **DB 迁移就位**：master 上的 alembic 已经把 owner_user_id 列加好了。`alembic upgrade head` 一次确认。
2. **Helicone proxy**：
   ```bash
   cd infra/helicone/upstream && docker compose up -d
   curl http://localhost:8585/healthcheck   # 200
   ```
3. **ai-books 后端（v3 env 配置）**：
   ```bash
   export NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE='http://localhost:8585/v1/openai'
   export N8N_WEBHOOK_PIPELINE_COMPLETE_URL='http://localhost:5678/webhook/pipeline-complete'
   make api-dev &  # FastAPI on :8011 (uvicorn)
   ```
4. **前端**（如需 Dify iframe 验证）：
   ```bash
   cd apps/web && npm run dev   # :4173
   ```

## 5 分钟端到端 smoke

### Step 1 — alice 上传一本书
```bash
curl -X POST -H "X-User-Id: alice" -F file=@samples/alice-book.txt \
  http://localhost:8011/api/import
# 期望：返回 run_id / branch_id
```

### Step 2 — 验证 alice 的 library 只属于 alice
```bash
curl -H "X-User-Id: alice" 'http://localhost:8011/api/library' \
  | jq '.items | length'   # ≥ 1
curl -H "X-User-Id: bob"   'http://localhost:8011/api/library' \
  | jq '.items | length'   # 0（前提是 bob 没上传过）
```

### Step 3 — alice 跑一次 imitation
```bash
curl -X POST -H "X-User-Id: alice" -H "Content-Type: application/json" \
  -d '{"branch_id":"<branch_id>","chapter_index":1,"goal":"测试仿写"}' \
  http://localhost:8011/api/whole-book-imitation-run
# 期望：响应 200，含 contract_version
```

### Step 4 — n8n 收到完成通知
```bash
curl -u admin:novel_n8n_dev \
  'http://localhost:5678/api/v1/executions?workflowId=pipeline-complete-notify' \
  | jq '.data[0] | {status, startedAt}'
# 期望：最近 1 条 status="success"
```

### Step 5 — Langfuse 看到 imitation trace
```bash
curl -u <PUB>:<SEC> \
  'http://localhost:3030/api/public/traces?userId=alice&limit=5' \
  | jq '.data | length'
# 期望：≥ 1
```

### Step 6 — Dify 里发问，后端日志可见 user_id
```bash
# 在浏览器 :8080 → Writer Copilot → 以 user_id=alice 发问 "第一章的伏笔有哪些？"
# 后端日志：
tail -f /tmp/ai-books-api.log | grep "X-User-Id"
# 期望：每条 tool 调用 log 含 X-User-Id: alice
```

## 故障定位 — 5 个常见症状

### 症状 1：n8n executions 是空的（imitation 跑完但 hook 没触发）

排查顺序：
1. 后端进程 env 是否设了？
   ```bash
   echo $N8N_WEBHOOK_PIPELINE_COMPLETE_URL
   ```
2. 后端日志找 "n8n notify"：
   ```bash
   grep "n8n notify" /tmp/ai-books-api.log
   ```
   - 没记录 = env 没生效（重启 api process）
   - "timed out" = n8n 启动慢或 URL 错
   - "HTTP error" = n8n 拒接（看 n8n 容器 log）
3. 直接 curl 验证 webhook：
   ```bash
   curl -X POST http://localhost:5678/webhook/pipeline-complete \
     -d '{"branch_id":"x","status":"test"}' -H "Content-Type: application/json"
   ```

### 症状 2：Langfuse 看不到 imitation trace

1. `NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE` 是否设？
2. Helicone 控制台（:8586）能看到 request？看不到 = override 没生效。
3. Dify 是否 wire 了 Langfuse？Dify Settings → Monitoring → Langfuse → 显示 connected。
4. 注意：Helicone 的 trace 默认进 Helicone 自己的 ClickHouse，不直接进 Langfuse。
   两套 UI 是分开的；v3 不做同步。

### 症状 3：Dify Custom Tool 调后端 401 / 403

ai-books 当前不验签，401/403 来自 Dify 自身。检查：
1. Custom Tool 的 Authorization 设的是 None
2. URL 用 `host.docker.internal:8011`（不是 `localhost:8011`，容器内访问主机）

### 症状 4：alice 的隔离失效（看到 bob 的书）

1. 后端日志确认 X-User-Id header 透传到了：
   ```bash
   grep "HTTP_X_USER_ID" /tmp/ai-books-api.log
   ```
2. Dify Custom Tool 的 Headers 配置里 X-User-Id 映射对了吗？
3. 数据库里 owner_user_id 列真的有值吗？
   ```bash
   psql -d novel_analyzer -c "SELECT DISTINCT owner_user_id FROM novel_sources"
   ```
   全是 `local-default` = ingest 时没传 user_id；查 IngestService 调用方有没有 patch。

### 症状 5：Helicone proxy 挂了导致 imitation 全失败

紧急降级：
```bash
unset NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE
# 重启 api process
# imitation 直连 LLM provider，trace 暂时丢失但业务恢复
```

之后排查 Helicone：
```bash
docker compose -f infra/helicone/upstream/docker-compose.yml logs --tail 50
```

## 一键 smoke

```bash
make v3-smoke        # 跑 e2e 测试套件 + 打印 runbook 链接
```

## 已知限制

- **trace 覆盖只到 build_chat_model() 调用**：直接调 OpenAI SDK 的代码不被覆盖。grep 全仓库确认无 `from openai import` 直接调用。
- **Langfuse 和 Helicone 是两套 trace UI**：Dify 走 Langfuse；imitation 直连走 Helicone。同步合并是 v4 候选。
- **owner_user_id scoping 只覆盖 /api/library**：其他 endpoint（run-snapshot、chapter-bundle 等）当前不按 user_id 过滤。等 FastAPI surface 落地后用 IdentityMiddleware 全面接入。
