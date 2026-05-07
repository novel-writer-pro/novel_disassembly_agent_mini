# CLI Standard Workflow Manual

本手册面向实际操作，描述从导入小说到导出拆书结果、问答上下文、专题导航的标准 CLI 路径。

---

## 0. PostgreSQL 前置要求

当前运行时已收口为 **PostgreSQL-only**。

在执行 CLI 前，请先准备：
- PostgreSQL 数据库实例
- 用户与数据库
- 必要扩展能力检查

建议先运行：
```bash
python3 scripts/check_postgres.py
```

或：
```bash
poetry run novel-analyzer db-capabilities
```

如果你打算使用 Web 工作台原型，建议同时准备：
- 一个可连接的 PostgreSQL 库
- `run_id / branch_id` 可供前端读取
- `apps/api` 原型后端
- `apps/web` Next.js 前端运行环境

### 0.1 Web 工作台前端依赖
前端当前使用：
- Next.js
- React
- Ant Design

建议 Node.js 20+，并先设置 npm 源：

```bash
npm config set registry https://registry.npmmirror.com/
```


## 0.2 当前推荐 LLM 配置

当前工作台与真实拆书默认建议使用：
- provider: `vip1129`
- base_url: `https://api.vip1129.cc/v1`
- model: `gpt-5.4-mini`

例如：
```bash
export NOVEL_ANALYZER_LLM_PROVIDER_NAME=vip1129
export NOVEL_ANALYZER_LLM_BASE_URL=https://api.vip1129.cc/v1
export NOVEL_ANALYZER_LLM_API_KEY='your-key'
export NOVEL_ANALYZER_LLM_MODEL_NAME=gpt-5.4-mini
export NOVEL_ANALYZER_LLM_STAGE_MODEL_NAME=gpt-5.4-mini
export NOVEL_ANALYZER_LLM_QA_MODEL_NAME=gpt-5.4-mini
export NOVEL_ANALYZER_LLM_FALLBACK_MODEL_NAME=gpt-5.4-mini
```

## 0.3 自动重试说明

章节拆书失败时：
- 系统会先自动重试
- 当前自动重试上限为 **5 次**
- 达到 5 次后仍失败，才进入人工恢复（`needs_recovery` / 工作台恢复页）

## 1. Python3 安装（不使用 Poetry）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

如果你不使用 `poetry run`，下面所有命令都可以改写为：

```bash
python3 -m novel_analyzer.cli.app <command> ...
```

例如：

```bash
python3 -m novel_analyzer.cli.app init-db
python3 -m novel_analyzer.cli.app ingest /path/to/novel.txt --title '样例小说'
python3 -m novel_analyzer.cli.app start-run <novel_id> <manifest_id>
```

---

## 2. 初始化环境

```bash
poetry install
poetry run novel-analyzer init-db
poetry run novel-analyzer db-health
poetry run novel-analyzer test-embedding
```

建议在 `.env.local` 中先准备：
- 数据库连接
- LLM provider / model
- ONNX embedding 路径

---

## 3. 导入小说并创建分支

### 2.0 一键高层入口（新）
如果你想减少手工步骤，可以直接用：
```bash
poetry run novel-analyzer auto-run /path/to/novel.txt --max-chapters 0
```

这条命令会：
- 导入小说
- 创建 manifest
- 创建 run / branch
- 输出 `novel_id / manifest_id / run_id / branch_id`

当 `--max-chapters > 0` 时，它还会继续自动推进指定数量的章节。


### 2.1 导入前先做切章预检
```bash
poetry run novel-analyzer inspect-novel /path/to/novel.txt
```

重点看：
- `raw_heading_count`
- `normalized_chapter_count`
- `duplicate_heading_count`

如果 `normalized_chapter_count=0`，说明当前标题格式没有被识别；这时建议先看：
- `docs/novel-ingest-chapter-standard.md`
- 或改用 `ingest-chapter-list` / API `chapters` list 方式导入

### 2.1b chapter list 导入（逐章 / 多章）
```bash
poetry run novel-analyzer ingest-chapter-list /path/to/chapters.json --title '样例小说'
```

支持：
- JSON list
- `{ "chapters": [...] }` object

每章兼容字段：
- 标题：`raw_heading` / `title` / `chapter_title` / `normalized_title`
- 正文：`content` / `text` / `body`

### 2.2 导入文本
```bash
poetry run novel-analyzer ingest /path/to/novel.txt --title '样例小说'
```

记录输出：
- `novel_id`
- `manifest_id`
- `chapter_count`

### 2.3 创建 run / branch
```bash
poetry run novel-analyzer start-run <novel_id> <manifest_id>
```

记录输出：
- `run_id`
- `branch_id`

---

## 4. 标准拆书推进路径

### 3.1 单章推进（推荐）
```bash
poetry run novel-analyzer analyze-next <run_id> <branch_id>
```

### 3.2 小区间推进
```bash
poetry run novel-analyzer analyze-range <run_id> <branch_id> 1 3
```

### 3.3 串行恢复推进
```bash
poetry run novel-analyzer resume-run <run_id> <branch_id> --max-chapters 3
```

推荐策略：
- 长文本优先 `analyze-next`
- 或每次只推进 1~3 章
- 不建议一次性大批量长跑

---

## 5. 运行状态与审计

### 4.1 查看 branch / run 状态
```bash
poetry run novel-analyzer show-branch <branch_id>
poetry run novel-analyzer show-run-status <run_id> <branch_id>
poetry run novel-analyzer list-chapters <branch_id>
```

### 4.2 查看单章结果
```bash
poetry run novel-analyzer show-chapter <branch_id> <chapter_index>
poetry run novel-analyzer export-chapter-bundle <branch_id> <chapter_index> ./chapter.json
poetry run novel-analyzer export-markdown <branch_id> <chapter_index> ./chapter.md
```

### 4.3 查看上下文 / 原始输出
```bash
poetry run novel-analyzer show-context <branch_id> <chapter_index>
poetry run novel-analyzer export-context <branch_id> <chapter_index> ./context.json
poetry run novel-analyzer show-raw-output <branch_id> <chapter_index>
poetry run novel-analyzer export-raw-output <branch_id> <chapter_index> ./raw.json
```

### 4.4 章节原文回看
当前前端工作台原型已经支持按章节查看原始正文片段。

CLI 下若需要回看，可结合：
- `show-chapter`
- `show-context`
- `export-chapter-bundle`

以及数据库中的 `chapter_segments.start_offset/end_offset` 与原始文本源文件进行定位。

---

## 6. 图谱、状态机与专题导航

### 5.1 图谱概览
```bash
poetry run novel-analyzer summarize-graph <branch_id>
poetry run novel-analyzer show-graph <branch_id>
poetry run novel-analyzer show-reasoning-graph <branch_id>
```

### 5.2 facts / windows
```bash
poetry run novel-analyzer show-facts <branch_id> --chapter-index 1
poetry run novel-analyzer search-facts <branch_id> '卫图 命格'
poetry run novel-analyzer show-window <branch_id> 1 5
```

### 5.3 branch report
```bash
poetry run novel-analyzer export-branch-report <run_id> <branch_id> ./branch.md
```

当前 branch report 会包含：
- Graph Overview
- State Summary
- Chapter Output Summary
- Reasoning Graph
- Foreshadow / Conflict / Relation / World Rule States

---

## 7. 小说问答与 QA Context

### 6.1 直接问答
```bash
poetry run novel-analyzer ask-branch <branch_id> '命格线在前两章是如何推进的？'
```

当前问答会返回：
- answer
- used_chapters
- evidence
- reasoning_path
- graph_signal

### 6.2 导出 Chapter QA Context
```bash
poetry run novel-analyzer export-chapter-qa-context <branch_id> <chapter_index> ./chapter-qa.json
```

适合：
- 单章问答
- 单章细节追问
- 写作者针对单章复盘

### 6.3 导出 Branch QA Context
```bash
poetry run novel-analyzer export-branch-qa-context <run_id> <branch_id> ./branch-qa.json
```

适合：
- 整条主线问答
- 主题导航
- 下游 agent 长上下文输入

### 6.4 thematic contexts
当前 branch QA context 中包含：
- `character_arc`
- `conflict_arc`
- `foreshadow_arc`
- `world_rule_arc`

每个主题当前已包含：
- `recommended_questions`
- `question_sequence`
- `related_chapters`
- `evidence_summaries`
- `reasoning_paths`
- `state_signals`
- `supporting_facts`
- `node_refs`
- `edge_refs`
- `timeline_points`

---

## 8. Package 导出标准路径

```bash
poetry run novel-analyzer export-branch-package <run_id> <branch_id> ./branch_pkg
```

当前 package 会包含：
- `branch_bundle.json`
- `branch_report.md`
- `branch_qa_context.json`
- `chapter_index.json`
- `chapters/chapter_XXXX.json`
- `chapters/chapter_XXXX.md`
- `chapters/chapter_XXXX.raw.json`
- `chapters/chapter_XXXX.context.json`
- `chapters/chapter_XXXX.qa-context.json`

### 8.1 Web 工作台下载
当前 `apps/api` 原型还提供：
- `GET /api/branch-exports`
- `GET /api/download`

前端工作台可以直接生成并下载：
- branch bundle
- branch QA context
- branch report

---

## 9. 恢复、修复与回退

### 8.1 查失败任务
```bash
poetry run novel-analyzer list-failed-jobs <branch_id>
```

### 8.2 清理卡住任务
```bash
poetry run novel-analyzer clear-running-jobs <branch_id>
```

### 8.3 重试单章 / 批量失败章
```bash
poetry run novel-analyzer retry-chapter <run_id> <branch_id> <chapter_index>
poetry run novel-analyzer retry-failed-jobs <run_id> <branch_id>
```

### 8.4 逻辑回退分支
```bash
poetry run novel-analyzer fork-branch <branch_id> <keep_through>
```

语义：
- 保留 `<= keep_through` 的章节进度
- 隐藏后续章节进度
- 在新 branch 上重新往后拆

这正是“前几章保留、后面删掉重拆”的标准路径。

### 8.5 修复已有 branch 派生层
```bash
poetry run novel-analyzer validate-branch <branch_id>
poetry run novel-analyzer repair-branch <branch_id>
```

### 9.1 工作台中的恢复动作
当前前端工作台原型已接入：
- `retry-failed`
- `clear-running`
- `repair`

适合在 `needs_recovery` 状态下直接从界面操作。

---

## 9. 推荐的日常操作顺序

### 最稳妥的串行操作
1. `ingest`
2. `start-run`
3. `analyze-next` / `analyze-range`
4. `show-run-status`
5. `export-branch-report`
6. `ask-branch`
7. `export-branch-package`

### 做写作者参考时
1. `export-branch-report`
2. `export-branch-package`
3. 读取 `chapter_XXXX.md`
4. 读取 `chapter_XXXX.qa-context.json`
5. 读取 `branch_qa_context.json`

### 做前端/工具接入时
1. 读 [`./interface-manifest.md`](./interface-manifest.md)
2. 参考 [`./examples/*.sample.json`](./examples/)
3. 接 `branch_qa_context.json`
4. 再接 `thematic_contexts`

---

## 10. 文档导航

- [`./direct-usage-guide.md`](./direct-usage-guide.md)
- [`./interface-manifest.md`](./interface-manifest.md)
- [`./examples/*.sample.json`](./examples/)
- [`./final-handoff.md`](./final-handoff.md)

---

## 11. 当前维护建议（2026-04-28 之后）

如果你接手当前版本，请优先遵守以下原则：

1. **先保可用，再加功能**
   - 优先修复上下文丢失、任务卡死、恢复不顺滑
   - 不急着引入更激进的自动恢复与更复杂的调度

2. **先保单一真相源**
   - chapter job 状态以 `chapter_jobs` 为准
   - 事件链以 `chapter_job_events` 为准
   - 不要在前端再发明第二套任务状态缓存

3. **优先沿现有入口演进**
   - 高阶能力优先收纳在“开始整理”/“导出与恢复”内
   - 不要轻易增加新的一级导航

4. **下一步推荐**
   - pipeline 当前 run 聚焦模式
   - pipeline 排序和错误摘要
   - ops <-> pipeline 回跳联动
   - 最后再做 SSE


### 6.5 Web 工作台中的问答能力
当前阅读页已经直接接入：
- branch 级检索（人物 / 事件 / 冲突 / 关键词）
- 基于小说内容的问答
- 结果中的引用章节跳转、证据摘要、推理路径与图谱信号


## 附：前端构建缓存异常

如果工作台前端在 `npm run build` 时出现页面模块缺失，但源码页面文件实际存在，优先清理：

```bash
cd apps/web
rm -rf .next
npm run build
```

本轮已验证：曾出现 `/ops` 页面缺失于 manifest，但清理 `.next` 后重新构建即可恢复。

- 问答 / 检索台已上移到阅读页前部，默认先于章节详情展示。


## Sample branch smoke

```bash
python -m scripts.check_sample_branch <run_id> <branch_id> ./branch.md
```

这条命令会顺序执行 PostgreSQL 能力检查与 branch report 导出，适合交接和真实环境 smoke。
