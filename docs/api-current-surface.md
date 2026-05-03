# API Current Surface / 当前实现契约（WSGI 原型）

> 本文件描述 `apps/api/app/main.py` 当前已经实现并可调用的 WSGI API surface。
> 如果你要对接**现在能用的后端接口**，以本文件和 `/api/meta` 为准。
>
> 对应的未来目标契约仍保留在 `docs/api-contract.md`，但那份文档描述的是长期演进目标，不等于当前实现清单。

## 1. 当前实现路由

### 基础
- `GET /health`
- `GET /api/meta`
- `GET /api/mock/import?profile=auto-lite`

### 导入 / 启动 / 恢复
- `POST /api/import`
- `POST /api/start`
- `POST /api/recovery`

### 运行 / 分支 / 章节读取
- `GET /api/run-snapshot?run_id=...&branch_id=...`
- `GET /api/branch-snapshot?run_id=...&branch_id=...`
- `GET /api/chapter-bundle?branch_id=...&chapter_index=...`
- `GET /api/chapter-qa-context?branch_id=...&chapter_index=...`
- `GET /api/chapter-source?branch_id=...&chapter_index=...`
- `GET /api/chapter-jobs?branch_id=...&limit=...`
- `GET /api/chapter-job-events?branch_id=...&chapter_index=...&limit=...`
- `GET /api/job-events?branch_id=...&limit=...`

### Review workflow
- `GET /api/review-clusters?run_id=...&branch_id=...`
- `GET /api/review-cluster-summary?run_id=...&branch_id=...`
- `GET /api/review-cluster-history?branch_id=...&cluster_key=...`
- `POST /api/review-cluster-update`
- `POST /api/review-batch-execute`
- `GET /api/review-batch-history?branch_id=...`

### Pipeline runtime
- `POST /api/pipeline/start-range`
- `GET /api/pipeline/status?pipeline_run_id=...`
- `GET /api/pipeline/runs?branch_id=...`

### 系统 / 工作台读取
- `GET /api/library`
- `GET /api/runtime-health`
- `GET /api/provider-health`
- `POST /api/whole-book-imitation-run`
- `POST /api/search-branch`
- `POST /api/ask-branch`
- `POST /api/ask-branch-stream`
- `GET /api/branch-exports?run_id=...&branch_id=...`
- `GET /api/download?path=...`

## 2. 当前契约定位

- `/api/meta` 当前同时返回：
  - `available_endpoints`：兼容旧消费者的路径列表
  - `available_endpoint_specs`：面向自动接入/校验的 `{method, path}` 清单（推荐优先消费）

- 这是**实现面对齐文档**，目标是让接入方知道“现在真实可用的是什么”
- `/api/meta` 应与这里保持一致
- `apps/api/README.md` 应把这份文档作为当前实现契约入口
- `docs/api-contract.md` 继续保留，但仅表示未来目标契约，不应被误读为当前实现清单

## 3. 维护规则

当 `apps/api/app/main.py` 增删真实路由时，需要同步更新：
1. 模块级 `_API_ENDPOINT_SPECS`（作为 method+path source-of-truth）
2. `/api/meta` 的 `available_endpoint_specs`
3. `/api/meta` 的 `available_endpoints`（兼容旧消费者）
4. `apps/api/README.md`
5. `docs/api-current-surface.md`
6. 相关契约一致性测试
