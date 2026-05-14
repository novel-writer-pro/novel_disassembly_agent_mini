# n8n Self-Host (Local Dev)

> 给 novel-analyzer 做外围编排：完成通知、定时报表、第三方集成。
> 不承接核心 pipeline 流量。

## 启动 / 停止

```bash
cd infra/n8n
mkdir -p workflows
docker compose up -d
docker compose ps    # postgres + n8n 都 healthy

# 浏览器打开 http://localhost:5678
# basic auth: admin / novel_n8n_dev

docker compose down       # 停止
docker compose down -v    # 停止并删除卷
```

## 调我们的 API

在 n8n 的 HTTP Request 节点里用：

```
http://host.docker.internal:8001/api/quality-dashboard?branch_id=...
http://host.docker.internal:8001/api/library
```

（compose 已配 `extra_hosts: host.docker.internal:host-gateway`，Linux 直接可用）

## 计划要建的 workflow

| 名称 | 触发 | 作用 | 状态 |
|------|-----|------|----|
| `pipeline-complete-notify` | Webhook POST /pipeline-complete | 解析 → echo/Slack/邮件 | 待建（N6） |
| `daily-eval-report` | Schedule (9am) | GET /api/quality-dashboard → Markdown → 通知 | 待建（N7） |

workflow JSON 模板见 v2 plan 的 N6/N7 段落。

## 注意

- 仅 localhost 监听
- basic auth 凭据已 hardcode 在 compose（dev only，不要进 prod）
- 后端不主动调 n8n（先手动 curl 触发验证；prod hook 后续）
