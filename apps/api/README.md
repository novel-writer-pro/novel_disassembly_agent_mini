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
- `GET /api/library`
- `GET /api/branch-exports?run_id=...&branch_id=...`
- `GET /api/download?path=...`
- `POST /api/ask-branch-stream`

说明：
- 当前仍是轻量原型后端，不是完整生产 API
- 已足够驱动本地工作台进行真实导入、章节查看、恢复与下载操作
- 默认不考虑用户认证，按本地 / 内网单人使用场景设计
- 问答接口当前分为两层：
  - `POST /api/ask-branch`：返回完整 JSON 结果
  - `POST /api/ask-branch-stream`：返回 `text/event-stream`，适合前端聊天式流式展示
- 当前本地 WSGI 服务已改为**并发处理请求**，因此某个长拆书 / 问答请求运行时，其他读取型请求不再必然一起被卡死

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
