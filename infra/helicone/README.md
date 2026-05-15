# Helicone Self-Host (Local Dev)

> Transparent LLM proxy. Sits in front of OpenAI-compatible API.
> v3 plan T5/T6 — used by `novel_analyzer/llm/client.py` to gain trace
> + cost coverage of the imitation main flow without touching business
> code.

## 一次性安装

```bash
cd infra/helicone
git clone --depth 1 https://github.com/Helicone/helicone.git upstream
# Note: branch is `main` — there is no `v1` branch on the upstream repo
cd upstream
cp .env.example .env

# Sanity-check the .env (look for DOCKER_HOST_IP, JAWN_PORT, JAWN_PUBLIC_URL).
# JAWN_PORT defaults to 8585 (no collision with Dify 8080 / n8n 5678).
# Web UI defaults to port 3000 — IF Langfuse also uses 3000, change one.
```

## 启动 / 停止

Use the upstream-provided helper script — it handles compose-profile flags:

```bash
cd infra/helicone/upstream/docker

# Bring up the full Helicone stack (Postgres + ClickHouse + MinIO + Jawn + Web UI):
./helicone-compose.sh helicone up
docker compose -p helicone-self-host ps

curl -fsS http://localhost:8585/healthcheck && echo OK    # Jawn proxy
curl -fsS http://localhost:3000 -o /dev/null && echo OK   # Web UI

./helicone-compose.sh helicone down       # Stop
./helicone-compose.sh helicone down -v    # Stop and drop ClickHouse + PG volumes
```

Available profiles:

| Profile | Brings up |
|---|---|
| `infra` | DB + ClickHouse + MinIO + MailHog (no Helicone app) |
| `helicone` | infra + Jawn (8585) + Web UI (3000) — **what we want** |
| `dev` | infra + Jawn-dev + Web-dev (hot reload, upstream contributors only) |
| `workers` | infra + 5 worker services |
| `kafka` | infra + Kafka + Zookeeper |
| `all` | everything |

## 接入（v3 T6 已就位的 env 切换）

1. Helicone console (`:3000`) → create org → Settings → API Keys → Create
2. ai-books 业务进程的 env 加：
   ```bash
   export NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE='http://localhost:8585/v1/openai'
   # 或在 docker-compose 启动 ai-books 时通过 -e 注入
   ```
3. 业务代码 0 行改动 — `build_chat_model()` 读 `llm_base_url_override` 优先于
   `resolved_llm_base_url`
4. 重启 ai-books（或重新读 settings；视部署而定）
5. 跑一次 imitation → Helicone 控制台 Requests 页可见 trace

## 降级路径

Proxy 挂了或想直连：
```bash
unset NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE
# 业务进程重启后回退到 resolved_llm_base_url
```

## 注意

- 仅 localhost 监听
- Helicone v1 / v2 的 docker-compose 字段命名差异较大；若官方 compose
  不再用 `OPENAI_PROXY_PORT` / `WEB_PORT`，按当前 docs 调整
- Trace 默认存 ClickHouse 自带表；同步到 Langfuse 是另一个开关，v3 不做
- 与 Dify/n8n/Langfuse 不共享 docker network
