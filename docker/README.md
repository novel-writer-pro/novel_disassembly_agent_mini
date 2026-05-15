# Docker 一体化部署

把 FastAPI 后端 (`:8011`) 和 Next.js 前端 (`:4173`) 打进同一个镜像，由 supervisord 一起拉起。PostgreSQL 走外部容器（compose 里已编排）。

## 资源清单

镜像内置：
- Python 3.11 + 项目依赖（`requirements.txt`）+ `uvicorn[standard]`
- Node.js 20 + 已构建的 Next.js（`apps/web/.next` 复制自 builder stage）
- supervisor、tini、postgresql-client（用于 `pg_isready` 健康等待 + alembic）

镜像外部依赖（必须挂卷或独立服务）：
- PostgreSQL 17（启动 `pg_trgm` / `pgvector` / `pg_jieba` / `pg_textsearch` 扩展）
- BGE-M3 ONNX 模型目录 → 挂到 `/models/bge-m3-onnx`
- 持久数据 → 挂到 `/data`（embeddings cache、runs、output、logs）

## 构建

```bash
cd /home/user/ai-books
docker build -f docker/Dockerfile -t novel-analyzer:latest .
```

## 启动 (compose)

```bash
cd docker
cp ../.env.example .env  # 改成你自己的 LLM key + DB 密码
BGE_M3_ONNX_PATH=/home/user/huggingface/bge-m3-onnx-int8 \
  docker compose up -d
```

第一次启动 `entrypoint.sh` 会等 PG 就绪，然后跑 `alembic upgrade head`，再交给 supervisord 拉 `api` + `web` 两个进程。

## 端口

| 服务 | 容器内 | 宿主 |
|------|--------|------|
| FastAPI | 8011 | 8011 |
| Next.js | 4173 | 4173 |
| Postgres | 5432 | 5432 |

## 单进程调试

```bash
docker exec -it novel-analyzer-app supervisorctl status
docker exec -it novel-analyzer-app supervisorctl restart api
docker exec -it novel-analyzer-app supervisorctl tail -f web stderr
```

## 跳过迁移（已经手动迁移过）

```bash
docker run -e NOVEL_ANALYZER_RUN_MIGRATIONS=0 ...
```

## 自定义 PG 扩展

`pg_jieba` / `pg_textsearch` 不在官方 `postgres:17` 镜像里。生产环境推荐：
1. 自己 build 一个带这些扩展的 PG 镜像，替换 compose 里的 `postgres:17`
2. 或者直连一个外部已配置好的 PG 实例，只跑 `app` 服务（`docker compose up app` 并把 `NOVEL_ANALYZER_DB_HOST` 指过去）
