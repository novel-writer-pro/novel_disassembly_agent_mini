# apps/api

独立 Web backend 目录。

当前阶段：
- 已完成 shared application seam
- 下一步由这里承接 HTTP 路由、launcher、PostgreSQL-only runtime
- 契约以 `docs/api-contract.md` 为准

当前可以直接运行一个轻量原型后端：

```bash
python3 -m apps.api.app.main
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
- 已足够驱动本地控制台原型进行真实导入、章节查看、恢复与下载操作
