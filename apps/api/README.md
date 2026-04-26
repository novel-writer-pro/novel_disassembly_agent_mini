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
- `GET /api/run-snapshot?run_id=...&branch_id=...`
- `GET /api/branch-snapshot?run_id=...&branch_id=...`
