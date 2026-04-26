# apps/api

独立 Web backend 目录。

当前阶段：
- 已完成 shared application seam
- 当前由这里承接 HTTP 路由、章节读取、恢复动作、导出下载
- 契约以 `docs/api-contract.md` 为准

当前可以直接运行一个轻量 WSGI 原型后端：

```bash
.venv/bin/python -m apps.api.app.main
```

提供：
- `GET /health`
- `GET /api/meta`
- `GET /api/mock/import?profile=auto-lite`
- `POST /api/import`
- `POST /api/start`
- `POST /api/recovery`
- `GET /api/run-snapshot?run_id=...&branch_id=...`
- `GET /api/branch-snapshot?run_id=...&branch_id=...`
- `GET /api/chapter-bundle?branch_id=...&chapter_index=...`
- `GET /api/chapter-qa-context?branch_id=...&chapter_index=...`
- `GET /api/chapter-source?branch_id=...&chapter_index=...`
- `GET /api/branch-exports?run_id=...&branch_id=...`
- `GET /api/download?path=...`

说明：
- 当前仍是轻量原型后端，不是完整生产 API
- 已足够驱动本地工作台进行真实导入、章节查看、恢复与下载操作
- 默认不考虑用户认证，按本地 / 内网单人使用场景设计


## 推荐启动方式（当前）

建议在启动前明确加载当前运行配置，避免误用旧 provider：

```bash
cd /home/user/ai-books
set -a
source .env.local
set +a
.venv/bin/python -m apps.api.app.main
```

当前推荐配置：
- provider: `vip1129`
- base_url: `https://api.vip1129.cc/v1`
- model: `gpt-5.4-mini`

## 恢复机制说明

章节失败时，后端默认会先自动重试：
- 自动重试上限：**5 次**
- 超过 5 次仍失败：才进入人工恢复态
- 前端工作台中的“导出与恢复”页只负责处理已经超过自动恢复阈值的章节
