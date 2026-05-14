# Dify Self-Host (Local Dev)

> 用 git submodule + 我们的 .env 覆盖，避免复制官方 compose 导致版本漂移。

## 一次性安装

```bash
cd infra/dify
git clone --depth 1 --branch 1.0.0 https://github.com/langgenius/dify.git upstream
cd upstream/docker
cp .env.example .env

# 改端口避免与 Workbench (4173) / 现有 API (8001) 冲突
sed -i 's/^EXPOSE_NGINX_PORT=80$/EXPOSE_NGINX_PORT=8080/' .env
```

## 启动 / 停止

```bash
cd infra/dify/upstream/docker
docker compose up -d
docker compose ps   # 12 个容器全 Up
# 浏览器打开 http://localhost:8080 完成 admin 注册

docker compose down       # 停止
docker compose down -v    # 停止并删除卷（慎用）
```

## 接入我们已有 API（Custom Tool）

- `search_chapter` → POST http://host.docker.internal:8001/api/search-branch
- `ask_branch`     → POST http://host.docker.internal:8001/api/ask-branch
- `get_chapter`    → GET  http://host.docker.internal:8001/api/chapter-source

应用配置导出的 DSL 文件保存到 `infra/dify/apps/`。

## 接入 Langfuse（在 Dify UI 中）

1. 启动 `infra/langfuse/upstream`
2. Langfuse UI 创建 project，记录 Public/Secret Key
3. Dify UI → 选某个 App → Monitoring → Tracing app performance → Langfuse → 粘贴

## 注意

- 仅 localhost 监听，不公网暴露
- 与 ai-books 现有服务不共享 docker network
- Linux 下 host.docker.internal 需 `--add-host=host.docker.internal:host-gateway`
