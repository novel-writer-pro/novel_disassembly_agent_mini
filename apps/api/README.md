# apps/api

独立 Web backend 目录。

当前阶段：
- 已完成 shared application seam
- 当前由这里承接 HTTP 路由、章节读取、恢复动作、导出下载
- 当前实现契约以 `docs/api-current-surface.md` 为准；未来目标契约仍参考 `docs/api-contract.md`

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
- `GET /api/chapter-jobs?branch_id=...&limit=200`
- `GET /api/chapter-job-events?branch_id=...&chapter_index=...&limit=100`
- `GET /api/review-clusters?run_id=...&branch_id=...`
- `GET /api/review-cluster-summary?run_id=...&branch_id=...`
- `GET /api/review-cluster-history?branch_id=...&cluster_key=...`
- `POST /api/review-cluster-update`
- `POST /api/review-batch-execute`
- `GET /api/review-batch-history?branch_id=...`
- `GET /api/library`
- `GET /api/job-events?branch_id=...&limit=100`
- `POST /api/pipeline/start-range`
- `GET /api/pipeline/status?pipeline_run_id=...`
- `GET /api/pipeline/runs?branch_id=...`
- `GET /api/runtime-health`
- `GET /api/provider-health`
- `GET /api/whole-book-imitation-readiness`
- `POST /api/whole-book-imitation-run`
- `POST /api/search-branch`
- `POST /api/ask-branch`
- `POST /api/ask-branch-stream`
- `GET /api/branch-exports?run_id=...&branch_id=...`
- `GET /api/download?path=...`

说明：
- 当前仍是轻量原型后端，不是完整生产 API
- 已足够驱动本地工作台进行真实导入、章节查看、恢复与下载操作
- 默认不考虑用户认证，按本地 / 内网单人使用场景设计
- 问答接口当前分为两层：
  - `POST /api/ask-branch`：返回完整 JSON 结果
  - `POST /api/ask-branch-stream`：返回 `text/event-stream`，适合前端聊天式流式展示
- 当前本地 WSGI 服务已改为**并发处理请求**，因此某个长拆书 / 问答请求运行时，其他读取型请求不再必然一起被卡死
- `GET /api/meta` 当前除了兼容字段 `available_endpoints` 外，还返回 `available_endpoint_specs`（`{method, path}` 清单），自动接入或契约校验建议优先消费该字段。
- `POST /api/whole-book-imitation-run` 当前返回显式版本标记：
  - `contract_version=whole-book-imitation.v1`
  - `stable_contract_version=whole-book-imitation-pre-v1`
  - 请求样例：`docs/examples/whole-book-imitation-run.request.sample.json`
  - 成功响应样例：`docs/examples/whole-book-imitation-run.sample.json`
  - 错误响应样例：`docs/examples/whole-book-imitation-run.error.provider-billing.sample.json`
- whole-book imitation 最短接入建议：
  - quickstart：`docs/whole-book-imitation-integration-quickstart.md`
  - readiness 样例：`docs/examples/whole-book-imitation-readiness.sample.json`
  - sample coverage：`docs/whole-book-imitation-sample-coverage-matrix.md`
  - provider recovery：`docs/whole-book-imitation-provider-recovery-checklist.md`

### whole-book integration quick path

推荐顺序：
1. 先调 `GET /api/whole-book-imitation-readiness`
2. 确认：
   - `provider.api_key_present=true`
   - `branch_candidate.chapter_analysis_count >= 2`
   - `provider.provider_health.last_status` 不是明显异常
3. 再调 `POST /api/whole-book-imitation-run`
4. 成功时读：
   - `policy_summary.next_stage_focus`
   - `dashboard_summary.book_handoff_summary`
5. 失败时读：
   - `error_code`
   - `retryable`

最小示例：

```bash
curl "http://127.0.0.1:8000/api/whole-book-imitation-readiness?branch_id=<branch_id>&database_url=<database_url>"
```

```bash
curl -X POST "http://127.0.0.1:8000/api/whole-book-imitation-run" \
  -H "Content-Type: application/json" \
  -d @docs/examples/whole-book-imitation-run.request.sample.json
```

## 多作品说明

当前后端数据模型本身就支持：
- 多个 `novel_sources`
- 多个 `analysis_runs`
- 多个 `run_branches`

新增：
- `GET /api/library`：返回最近作品 / run / branch 列表，供前端做多作品切换或总览
- `GET /api/library` 当前也会返回：
  - `failed_jobs`
  - `running_jobs`
  - `setup_status`
  便于小说空间 / 多作品管理页直接显示每本书的运行状态
- `GET /api/runtime-health`：返回 `.cache/novel-analyzer/` 与历史 `.omx/` 运行时文件的数量与迁移状态，便于排查重启后文件问题
- `GET /api/provider-health`：返回最近一次 ask/ask-stream 使用的 provider 状态，便于前端系统健康面板展示 503 / 降级情况
- `GET /api/whole-book-imitation-readiness`：返回 whole-book freeze 检查所需的 contract/provider/branch readiness 信息
- `GET /api/job-events?branch_id=...&limit=100`：返回章节任务事件流，供后续任务控制台或排障流程查看章节级执行过程
- `POST /api/pipeline/start-range`：以后台异步方式启动一段连续拆书任务（当前最小版本要求从 `next_chapter` 开始）
- `GET /api/pipeline/status?pipeline_run_id=...`：查看某个后台 pipeline run 状态
- `GET /api/pipeline/runs?branch_id=...`：查看某个 branch 最近的后台 pipeline run 历史
- 后台 pipeline run 的 pause / resume / cancel 控制能力仍属于后续增量 productization 范围，当前 WSGI 原型未单独暴露对应 HTTP 路由。
- `GET /api/chapter-jobs?branch_id=...&limit=200`：返回章节级任务表，用于 pipeline 控制台展示当前 stage / 进度 / 尝试次数 / 心跳 / 失败分类
- 当前后端会在若干读取路径中顺手扫描长时间无 heartbeat 的 running job，并将其标记为 `failure_class=stalled`，避免控制台长期看到“假 running”
- `GET /api/chapter-job-events?branch_id=...&chapter_index=...&limit=100`：返回单章任务事件链，适合 pipeline 控制台详情抽屉查看

注意：
- 目前“并行”仍主要是 **HTTP 请求层面的并发可处理**
- 拆书任务本身仍是按 branch 串行推进
- 如果要做到真正的后台多任务调度，还需要单独的 job queue / worker 层


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

- 导出下载链接现在写入项目内 `.cache/novel-analyzer/runtime-exports/` 持久目录，避免 `/tmp` 临时路径失效导致前端下载失败。

- `POST /api/import` 上传的原始小说文件现在持久化写入 `.cache/novel-analyzer/uploads/`，避免后续章节原文回看时因为 `/tmp` 被清理而报错。
- 对旧的 `.omx/uploads/` 路径读取增加了兼容解析，便于平滑过渡到 `.cache/`。
- 后端启动时会自动尝试把历史 `.omx/uploads/` 与 `.omx/runtime-exports/` 复制迁移到 `.cache/novel-analyzer/` 下。

## 问答流式事件格式

`POST /api/ask-branch-stream` 当前会按 SSE 连续发送：

- `status`：当前阶段提示
- `retrieval`：命中的章节检索结果
- `delta`：逐段追加的回答文本
- `final`：最终结构化问答结果
- `error`：错误信息

前端可以优先消费 `delta` 做实时聊天输出，再在 `final` 事件里渲染：
- `used_chapters`
- `evidence`
- `reasoning_paths`
- `graph_signals`
