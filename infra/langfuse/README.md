# Langfuse Self-Host (Local Dev)

> Langfuse v3 用了较多组件（PG + ClickHouse + Redis + MinIO + web + worker），
> 用他们仓库 + 我们的 .env 覆盖（避免复制官方 compose 导致版本漂移）。

## 一次性安装

```bash
cd infra/langfuse
git clone --depth 1 --branch v3.0.0 https://github.com/langfuse/langfuse.git upstream
cd upstream
cp .env.dev.example .env

# 编辑 .env：
#   - LANGFUSE_PORT 改成 3030（避免与 Dify nginx 8080 冲突）
#   - 替换所有 SECRET/KEY/SALT 为本地随机值（用 openssl rand -hex 32 生成）
```

## 启动 / 停止

```bash
cd infra/langfuse/upstream
docker compose up -d
docker compose ps    # web/worker/postgres/clickhouse/redis/minio 全 Up

# 浏览器打开 http://localhost:3030 完成 admin 注册

docker compose down
docker compose down -v   # 删除全部数据
```

## 接入 Dify（推荐路径）

1. Langfuse UI → New Organization → New Project (e.g. `novel-analyzer-dev`)
2. Settings → API Keys → Create new API key
3. 记录 Public Key / Secret Key / Host = `http://host.docker.internal:3030`
4. 进 Dify UI → 选某个 App → Monitoring → Tracing app performance → Langfuse → 粘贴

完成后 Dify 里发起的对话会自动产生 trace。

## 不接业务代码（重要）

按 v2 plan：
- 不改 `novel_analyzer/llm/client.py`
- 不给业务代码 `import langfuse`
- 走 Dify 内置集成

如果未来需要给绕过 Dify 的 LLM 调用也加 trace，再考虑 N10 中评估的 Helicone 代理层方案。

## 注意

- 仅 localhost 监听
- 数据敏感度：所有用户 prompt/completion 都会被 trace 保存到 Langfuse 的 PG/ClickHouse
- v3 用 ClickHouse 存 traces，资源占用比 v2 高
- 与 Dify 通信用 `host.docker.internal:3030`
