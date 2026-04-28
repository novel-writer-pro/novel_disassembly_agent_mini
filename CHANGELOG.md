# Changelog

> 约定：后续每次开发更改，都应在本文件追加一条记录，至少说明“做了什么 / 为什么 / 如何验证”。

## 2026-04-27

### 基础 release 文档收口
- 将当前版本明确收口为“基础可用 release”
- 补充 release 交接说明、工作台基础能力边界与推荐阅读顺序
- 明确这版优先保障可导入、可拆书、可阅读、可问答、可恢复、可导出

### 多作品适配与后端并发补强
- 工作台新增“当前作品库”切换入口，允许在同一个 UI 中切换不同 run / branch
- 为后续多本小说总览页预留基础数据接口：`GET /api/library`
- 后端 WSGI 服务改为可并发处理请求，避免一个长拆书请求把整个 API 完全阻塞
- 当前仍是“单工作台聚焦一个 branch”的交互模型，但已经不再写死只能服务单本小说

### 问答状态可视化与当前作品识别增强
- branch QA 结果新增 `answer_mode` / `degraded_reason`，显式区分正常回答与降级回答
- 当上游问答模型临时 503 时，界面会显示“降级回答”提示，而不是只剩无结果状态
- 工作台头部新增“当前作品”区域，明确显示正在查看的是哪一本小说
- 控制台新增当前作品摘要与作品快捷卡，避免多本切换时看不出自己正处于哪一本

### 小说空间与多作品管理入口
- 新增独立的 `/library` 小说空间页面，作为多本小说管理入口
- 支持按小说名 / 分支 / 状态搜索，并以卡片方式管理大量小说记录
- 小说空间中新增每本书的状态卡、后台进行中统计、待恢复统计与快捷进入按钮
- 将首页默认入口切换到小说空间，先选当前生效小说，再进入控制台 / 阅读 / 问答
- 左侧章节卡片调小，减少单条章节占用高度，便于长目录阅读
- 修复 `/api/library` 中 `_setup_status` 未导入导致的后端报错
- 新增多任务运行 / 恢复中心，并支持自动状态刷新
- 工作台会根据是否存在运行中 / 待恢复任务自动提高刷新频率

### 运行时缓存路径收口
- 将 Web 工作台运行期文件从 `.omx/...` 收口到 `.cache/novel-analyzer/...`
- 导出文件迁移到 `.cache/novel-analyzer/runtime-exports/`
- 上传小说原文迁移到 `.cache/novel-analyzer/uploads/`
- 补充旧 `.omx/uploads/` 路径的兼容读取，减少重启或历史数据切换时出现“文件不存在”
- 后端启动时会自动迁移历史 `.omx/uploads/` 与 `.omx/runtime-exports/` 内容到 `.cache/novel-analyzer/`
- 工作台按 branch 记住独立的最后阅读章节，切回同一本小说时优先恢复各自阅读位置

### 小说问答页修复与产品化增强
- 修复 `/qa` 页面实际未挂载问答组件、进入后无内容的问题
- 将小说问答页重做为真正可交互的聊天式界面，而不是只显示零散表单
- 保留“快速检索”页签，并把问答 / 检索 / 当前回答摘要拆成更清晰的三段结构
- 回答区改为卡片化渲染：引用章节、证据摘要、推理摘要、图谱信号分别分组展示
- 回答中的 `第N章` 引用继续支持直接跳转到章节阅读页

### 流式问答输出
- 新增 `POST /api/ask-branch-stream`
- 前端默认优先使用流式问答接口，按聊天场景逐步显示回答内容
- 若流式接口不可用，前端会自动回退到普通 `/api/ask-branch`，并在本地模拟逐段输出，避免界面完全卡死
- 前端问答消息中补充“推理摘要”展示，用于承接可展示的证据链 / reasoning paths，而不是直接平铺原始 JSON
- 当上游问答模型临时返回 503/不可用时，branch QA 服务现在会自动降级为“基于检索结果的保守回答”，不再直接给用户空结果

### 文档同步
- 更新 `README.md`
- 更新 `apps/web/README.md`
- 更新 `apps/api/README.md`
- 补充当前问答页的位置、流式能力与开发 / 部署说明

### 问答页二次打磨
- 将 `/qa` 页从单列问答改为“主聊天区 + 侧边提示区”的更稳定布局
- 增加顶部概览卡：已提问轮次、最近引用章节、当前模式
- 增加本轮提问记录，支持一键回填问题继续追问
- 将回答明细收拢为折叠分组：引用章节 / 证据摘要 / 推理摘要 / 图谱信号
- 检索结果支持“一键围绕这一章继续问”，让检索和问答联动更自然
- 增加清空会话与自动滚动到底部，减少长对话时的操作负担

### 本轮验证
- `cd apps/web && ./node_modules/.bin/tsc --noEmit`
- `cd apps/web && npm run build`
- `.venv/bin/python -m py_compile apps/api/app/main.py novel_analyzer/services/qa_service.py`

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

### Web 前端产品化重构（进行中）
- 前端开始从单页静态原型迁移到 Next.js + React + Ant Design
- 开始拆分为多组件 / 多页面结构
- 增补原始章节正文回看与 `第N章` 引用跳转
- 补充 Node.js / npm mirror (`https://registry.npmmirror.com/`) 部署说明

### 测试与测试基座迁移
- 迁移一批旧 CLI 测试，移除对 SQLite runtime 成功的依赖
- 新增 `tests/cli_test_support.py`
- 新增 PG capability / script / API 原型相关测试
- 调整 retrieval / QA 测试以匹配 PG-only 语义

### 验证
- `pytest` 目标与 broadened CLI/runtime 切片共 45+ 用例通过
- `ruff check` 通过
- `mypy` 通过


### 控制台产品化打磨与运行配置收口
- 重做工作台顶部结构、控制台流程区、导出与恢复页，使界面更接近面向作家的产品界面
- Reader / Sidebar / Control / Ops 之间的视觉语言继续统一，减少“技术后台”感
- 文档同步更新为当前推荐运行配置：`vip1129 + gpt-5.4-mini`
- 明确记录章节失败自动重试策略：默认自动重试最多 **5 次**，超过阈值后才进入人工恢复
- 明确从第一章重新创建新 run/branch 进行真实拆书，不再沿用旧 provider 的历史任务

### 本轮验证
- `cd apps/web && ./node_modules/.bin/tsc --noEmit`
- `cd apps/web && npm run build`
- `.venv/bin/pytest tests/test_application_layer.py tests/test_cli_retry_bulk.py -q`
- 真实创建新 run：`run_id=7e22a5d8-eb57-4306-858b-90386f1c2b22`

### 文档补完与仓库清理收口
- 补充 `apps/api/README.md`，明确当前推荐启动方式、provider 与自动恢复机制
- 补充 `docs/release-handoff-brief.md` / `docs/final-handoff.md`，同步当前工作台产品化方向与真实运行配置
- 补充 `.gitignore`，忽略 `apps/web/node_modules`、`.next` 与 ts build 缓存
- 准备将前端从旧静态原型彻底收口到 Next.js 目录结构

### 小说检索 / 问答界面接入
- 新增工作台内的人物/事件检索与基于小说内容的问答面板
- 后端新增 `/api/search-branch` 与 `/api/ask-branch` 接口
- 问答结果保留 `used_chapters`、`evidence`、`reasoning_paths`、`graph_signals`，并在前端可直接跳转章节
- 左侧章节分页增加范围选择与每页条数控制
- 修复章节点击后被旧 query 覆盖、请求竞态回退到旧章节的问题


### 工作台问答 / 检索能力接入与交互修复
- 新增 `BranchQaPanel`，在阅读页内直接提供人物/事件检索与基于小说内容的问答入口
- 后端新增 `/api/search-branch` 与 `/api/ask-branch` 接口，前端直接消费现有 branch retrieval / QA 能力
- 问答结果保留 `used_chapters`、`evidence`、`reasoning_paths`、`graph_signals`，并支持点击跳转章节
- 修复左侧章节点击后被旧 URL query 覆盖回退、请求竞态回退到旧章节、分页无法翻页等交互问题
- 自动拆书任务检查发现第 21 章长期 running，已执行 `clear-running` 并重新继续运行


### 前端构建缓存异常修复
- 定位到一次 `npm run build` 失败并非源码路由缺失，而是 `apps/web/.next` 脏缓存导致 `/ops` 未进入 pages manifest
- 通过删除 `apps/web/.next` 并重新构建恢复正常，新的 build 已重新包含 `/ops` 路由


### 交付纪律补充
- 增补项目约定：每一次修复和变动，都同步更新文档、`CHANGELOG.md` 与 git commit 记录
- 后续所有 UI、API、运行时恢复与自动拆书推进相关修改，均按该约定执行


### 问答区可见性增强
- 将阅读页内的“小说问答 / 检索台”上移为前部主入口，并增加 hero 说明区与能力标签
- 补充文档说明问答区默认优先显示，减少“功能已接入但不易被看到”的问题


### 导出链接从临时目录收口到持久目录
- 修复工作台中导出文件依赖 `/tmp` 临时路径的问题
- `/api/branch-exports` 现在改为输出到项目内 `.omx/runtime-exports/`，避免前端刷新或延迟下载时路径失效


### 控制台首页暴露额度失败与恢复入口
- 当章节因 provider 额度耗尽失败时，控制台首页会直接展示失败提示
- 提示中增加跳转恢复页与刷新进度入口，避免用户只看到章节停住却不知道如何处理


### 上传小说原文持久化，修复 /tmp 源文件丢失
- 修复工作台导入后把原文保存在 `/tmp`，导致后续章节正文回看时报 `No such file or directory` 的问题
- `POST /api/import` 现在把上传小说持久化写入 `.omx/uploads/`
- 同时将当前真实运行任务的 `source_path` 修正为稳定文件路径，恢复前后端展示


### 小说问答改为单独页签
- 将人物检索与基于小说内容的问答从阅读页内联区域拆分为独立的“小说问答”导航页签
- 章节阅读页回归专注阅读，问答与检索改为单独入口，降低信息拥挤度


### 首页重定向改为直接渲染，修复 build 收集 page data 异常
- 将首页 `/` 从运行时 `router.replace("/control")` 改为直接渲染控制台页面
- 修复 Next.js 在构建阶段对 `/` 收集 page data 时的路由异常，新的干净构建已重新包含 `/ /control /reader /qa /ops`
