# Changelog

> 约定：后续每次开发更改，都应在本文件追加一条记录，至少说明“做了什么 / 为什么 / 如何验证”。

## 2026-04-25

### 拆书能力与导出层增强
- 增强章节拆书输出：补充 `state_transition_notes`、`evidence_backed_resolutions`、`unresolved_threads`
- 强化 `writer_learning_notes` fallback，使其优先产出“推进 / 解决 / 留悬念”型 lesson
- 压缩 `chapter_summary`，默认使用更短的卡片化摘要
- 增强 JSON 提取与修复逻辑，降低轻微格式漂移导致的解析失败率

### 推理图与问答层增强
- 完整升级 reasoning graph，补充 richer node/edge taxonomy
- 增加 state machine / state summary
- 将图谱与状态摘要接入 QA、thematic contexts、package/export/report
- 增加 visualization-friendly 字段：`node_refs`、`edge_refs`、`timeline_points`

### QA context 与专题导航增强
- 增加 chapter QA context / branch QA context 导出接口
- 增加 `recommended_questions`、`query_hints`
- 增加 thematic contexts：character/conflict/foreshadow/world-rule
- 增加主题证据链：`reasoning_paths`、`state_signals`、`supporting_facts`
- 增加主题导航结构：`related_chapters`、`evidence_summaries`、`question_sequence`

### 文档与交付面增强
- 新增文档：
  - `docs/interface-manifest.md`
  - `docs/cli-operations-manual.md`
  - `docs/final-handoff.md`
  - `docs/release-handoff-brief.md`
  - `docs/real-run-checklist.md`
  - `docs/review-template.md`
  - `docs/model-eval-template.md`
  - `docs/real-run-evaluation-1-12.md`
  - `docs/README.md`
- 新增样例：
  - `docs/examples/chapter-bundle.sample.json`
  - `docs/examples/branch-bundle.sample.json`
  - `docs/examples/chapter-qa-context.sample.json`
  - `docs/examples/branch-qa-context.sample.json`
- 将核心 Markdown 文档中的文档引用逐步改为相对路径超链接 `[]()`

### 真实试跑结论（前 12 章）
- 前 12 章已形成真实可评估结果
- 当前模型 `Qwen/Qwen3.5-122B-A10B`：
  - 适合做质量验证 / 人工盯跑
  - 不适合长程无人值守生产跑批

### 验证
- `ruff check novel_analyzer tests alembic`
- `mypy`
- `pytest -q`（历史验证已通过 56 passed）

## 2026-04-26

### PostgreSQL-only runtime 收口
- 运行时收口为 PostgreSQL-only
- 去除 SQLite 作为正式 runtime 的假设
- 显式 `database_url` 统一要求 PostgreSQL URL
- 修复 `effective_db_name` / `admin_database_url` / `masked_database_url`
- 支持 IPv6 URL 重写与脱敏

### PostgreSQL 能力检查
- 新增 `scripts/check_postgres.py`
- 新增 `novel-analyzer db-capabilities`
- 检查数据库存在性、连接能力、schema 初始化、扩展能力和 text search config
- 保证 capability check 输出为结构化 `key=value`
- 保证错误配置时非零退出

### Web 工作台原型
- 新增独立前端目录：`apps/web/`
- 新增独立后端目录：`apps/api/`
- 前端支持：
  - 真实导入
  - 真实 run / branch 读取
  - 左侧章节导航 + 右侧详情主视图
  - chapter bundle / chapter QA context 结构化阅读
  - 原始章节正文回看
  - 引用中的 `第N章` 跳转
  - 恢复动作与导出链接
- 后端支持：
  - `/api/import`
  - `/api/start`
  - `/api/recovery`
  - `/api/run-snapshot`
  - `/api/branch-snapshot`
  - `/api/chapter-bundle`
  - `/api/chapter-qa-context`
  - `/api/chapter-source`
  - `/api/branch-exports`
  - `/api/download`

### 测试与测试基座迁移
- 迁移一批旧 CLI 测试，移除对 SQLite runtime 成功的依赖
- 新增 `tests/cli_test_support.py`
- 新增 PG capability / script / API 原型相关测试
- 调整 retrieval / QA 测试以匹配 PG-only 语义

### 验证
- `pytest` 目标与 broadened CLI/runtime 切片共 45+ 用例通过
- `ruff check` 通过
- `mypy` 通过
