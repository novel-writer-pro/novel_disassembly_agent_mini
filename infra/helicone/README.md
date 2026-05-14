# Helicone Self-Host (Local Dev)

> Transparent LLM proxy. Sits in front of OpenAI-compatible API.
> v3 plan T5/T6 — used by `novel_analyzer/llm/client.py` to gain trace
> + cost coverage of the imitation main flow without touching business
> code.

## 一次性安装

```bash
cd infra/helicone
git clone --depth 1 --branch v1 https://github.com/Helicone/helicone.git upstream
cd upstream
cp .env.example .env

# 改端口避开 8080 (Dify) / 5678 (n8n) / 3030 (Langfuse) / 8001 (ai-books) / 4173 (web)
# 注意：Helicone 不同版本的 env 字段名可能不同，按 .env.example 里实际名称改
sed -i 's/^OPENAI_PROXY_PORT=.*$/OPENAI_PROXY_PORT=8585/' .env || true
sed -i 's/^WEB_PORT=.*$/WEB_PORT=8586/' .env || true
```

## 启动 / 停止

```bash
cd infra/helicone/upstream
docker compose up -d
docker compose ps
curl http://localhost:8585/healthcheck    # 200
# 控制台 http://localhost:8586

docker compose down
docker compose down -v   # 删除全部数据
```

## 接入（v3 T6 已就位的 env 切换）

1. Helicone console (`:8586`) → create org → Settings → API Keys → Create
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
