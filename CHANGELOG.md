## 2026-05-01

### 角色/轨道入口补 current API surface 链接
- 为 `docs/roles/integrator/README.md`、`docs/roles/backend/README.md`、`docs/tracks/review-workflow/README.md` 补充 `api-current-surface.md` 入口
- 让接入者、后端维护者与 review workflow 读者都能更快看到“当前已实现 API surface”的 source-of-truth
- 增加自动测试，锁定这三个角色/轨道入口必须继续暴露该文档
- 验证：角色/轨道入口 targeted strict 回归通过

### current API surface 文档边界说明加保护
- 为 `docs/api-current-surface.md` 增加显式测试，要求该文档必须继续指向 `docs/api-contract.md`，并保留“未来目标契约”的边界说明
- 避免后续维护中把 current-surface 文档误改成没有边界的实现清单，或丢失与目标契约的关系说明
- 验证：current-surface / docs index / apps-api README targeted strict 回归通过

### docs/README 增加 current API surface 入口保护
- 为 `docs/README.md` 增加显式测试，要求文档索引必须暴露 `api-current-surface.md` 入口
- 让 root README、docs/README、apps/api/README 三层入口都进入 current API surface 文档的自动保护范围
- 验证：三层入口 targeted strict 回归通过

### 根 README 补当前 API 实现契约入口
- 在仓库根 `README.md` 的 newcomer path 中补充 `docs/api-current-surface.md` 直链
- 让接入者能从项目顶层直接区分“当前已实现 API surface”和“未来目标契约”
- 增加自动测试，要求根 README 必须暴露当前 API 实现契约文档
- 验证：root README / current-surface targeted strict 回归通过

### docs/README 编号检查升级为全节扫描
- 修复 `docs/README.md` 第二个“推荐阅读顺序”小节的编号漂移问题
- 将原本只覆盖“接口类文档”的编号测试升级为：扫描 `docs/README.md` 所有带编号的 `###` 小节，并要求编号连续递增
- 让文档入口结构的自动保护从单点检查升级为全节检查
- 验证：全节编号测试与 API README 路由清单测试 strict 模式通过

### 根 README 标题层级修正并加保护
- 修复根 `README.md` 中一行误写成一级标题的说明文本，消除文档标题层级跳级问题
- 增加自动测试，要求根 README 的标题层级不得出现大于 1 级的跳跃
- 验证：README heading 测试与现有契约测试 strict 模式通过

### docs/api-contract Markdown 结构修复
- 修复 `docs/api-contract.md` 中未闭合的 fenced code block，避免后续标题与内容被错误吞入代码块
- 增加轻量测试，要求该文档的 Markdown 代码块 fence 数量必须成对平衡
- 验证：api-contract fence 测试与 current-surface 契约测试通过

### docs/README 接口文档编号修正并加保护
- 修正 `docs/README.md` 中“接口类文档”小节因多轮增补导致的编号漂移问题
- 增加自动测试，要求该小节的编号必须连续递增，避免后续文档入口继续失序
- 验证：接口文档编号测试与 API README 路由清单一致性测试通过

### apps/api README 路由清单增加完整一致性保护
- 修正 `apps/api/README.md` 中把 `pause|resume|cancel` 写成伪单条 endpoint 的误导表述
- 为 `apps/api/README.md` 增加完整路由集合一致性测试，直接把 README 暴露的 `METHOD /path` 列表与真实 WSGI 路由集合进行比对
- 让 README、`/api/meta` 与 `docs/api-current-surface.md` 三者都进入自动一致性保护范围
- 验证：README / current-surface / meta 三方 targeted 回归通过

### 当前 API surface 文档增加自动一致性保护
- 为 `docs/api-current-surface.md` 增加自动一致性测试，直接把当前实现路由集合与文档中的 `METHOD /path` 列表进行比对
- 让当前实现文档、`/api/meta` 与 `apps/api/README.md` 的维护规则从“靠人工自觉”升级为“有测试锁定”
- 验证：current surface / README / meta 三方 targeted 回归通过

### 新增当前 API 实现契约文档
- 新增 `docs/api-current-surface.md`，专门描述 `apps/api/app/main.py` 当前已经实现并可调用的 WSGI API surface
- `apps/api/README.md` 改为把该文档作为当前实现契约入口，同时保留 `docs/api-contract.md` 作为未来目标契约参考
- 避免未来目标契约文档被误读成当前实现清单
- 验证：README 指向与 meta/README 一致性 targeted 回归通过

### apps/api README 端点清单补齐
- 补充 `apps/api/README.md` 中缺失的 review workflow、job events、search、ask-branch 等已实现端点
- 增加 README 一致性测试，锁定关键端点在后端 README 中必须被暴露
- 避免 API 实现、`/api/meta` 元信息与后端 README 三者继续漂移
- 验证：README / meta targeted 回归通过

### API meta 端点清单与真实路由对齐
- 修正 `/api/meta` 的 `available_endpoints` 列表，使其与 WSGI 中真实实现的路由集合一致
- 补入真实存在但之前遗漏的 `/api/start` 与 `/api/recovery`
- 移除之前误列入但实际并不存在于该 WSGI 路由表中的 `/api/pipeline/pause`、`/api/pipeline/resume`、`/api/pipeline/cancel`
- 为 `/api/meta` 增加自动比对测试，防止元信息与实现再次漂移
- 验证：meta route inventory targeted 回归通过

### API meta 契约与实际能力对齐
- 修正 `/api/meta` 中关于 write-side import/upload 的过时说明，不再把已可用的 `/api/import` 描述为 future work
- 将 `/api/import` 补入 `available_endpoints` 列表，避免接口清单与真实能力不一致
- 为 `/api/meta` 增加更严格的测试断言，锁定端点暴露与说明文案的一致性
- 验证：`test_meta_endpoint_lists_available_routes` + import endpoint targeted 回归通过

### API multipart 解析去除 cgi 依赖
- 将 `apps/api/app/main.py` 中的 `cgi.FieldStorage` multipart 解析替换为基于 `email.parser.BytesParser` 的标准库实现
- 消除 Python 3.13 方向上的 `cgi` deprecation warning，同时保持 `/api/import` 现有行为不变
- 新增正向 multipart 上传测试，覆盖 `title` / `pipeline_profile` / `file` 三类字段的实际解析与落盘
- 验证：`tests/test_api_main.py` 全量通过

### 根 README 风险审查入口补齐
- 在仓库根 `README.md` 的 newcomer path 中补充 `risk-audit-completion-status.md` 直链
- 让新接手者能直接看到风险审查第一阶段的完成度、测试方法与使用说明
- 验证：关联 report / review endpoint smoke 通过

### 仓库缓存文件治理
- 将 `**/__pycache__/` 与 `*.py[cod]` 明确加入 `.gitignore`，避免 Python 字节码缓存继续污染版本库
- 将历史上已被错误纳管的 `__pycache__` / `.pyc` 文件从 Git 索引中移除
- 这一变更不影响业务代码行为，目标是降低噪音 diff、减少误提交，并提升仓库卫生与后续开发稳定性
- 验证：`git ls-files | rg '(__pycache__/|\.pyc$)' | wc -l` 结果为 `0`；同时补跑导出/报告 smoke 用例通过

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
- 新增 `novel-analyzer runtime-storage` 与 `scripts/check_runtime_storage.py`，用于检查/迁移历史运行时文件
- 新增 `GET /api/runtime-health`，便于后续工作台或排障流程直接查看运行时文件状态

### 系统健康面板与任务中心增强
- 小说空间与运行/恢复中心接入 `runtime-health` 数据
- 新增系统健康面板，直接展示 `.cache` / `.omx` 文件数量与迁移状态
- 多任务运行/恢复中心增加筛选视图：聚焦 / 运行中 / 待恢复
- 新增 `provider-health` 状态记录与 API，用于展示 ask-stream 最近的 503 / 降级情况
- 任务中心开始联动 provider 健康状态，在 ask-stream 持续 503 时给出更明确的运行/恢复建议
- 问答页降级提示改为更产品化文案，减少直接暴露原始 503/429 错误噪音
- 顶部新增统一系统状态条，集中显示 provider/cache/自动刷新状态
- 恢复页开始根据 provider degraded 状态调整恢复动作提示与按钮强调级别
- provider degraded 时，工作台自动刷新会自动退避到较低频率，减少高频轮询噪音
- 任务中心中的恢复入口也开始根据 provider degraded 状态弱化动作强调
- 问答页降级回答减少重复提示，只保留一次清晰说明
- 系统健康面板新增聚合建议文案
- 恢复页进一步细化“什么时候该等、什么时候该恢复”的说明
- 系统健康面板、任务中心、恢复页开始复用统一建议规则，减少状态解释冲突
- 任务中心新增统一优先级排序规则，优先展示“待恢复 > 运行中 > 可继续推进 > 已完成”
- 小说空间卡片排序已与任务中心优先级规则统一，减少不同界面对同一批小说的排序不一致
- 任务中心、恢复页、系统健康面板开始复用共享的恢复动作策略规则

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

## 2026-04-28

### 工作台运行态规则进一步收口
- 新增 `apps/web/src/lib/operations.ts`，把 provider/cache/恢复/优先级 相关规则从纯展示格式化中拆出
- 系统状态条、小说空间、任务中心、健康面板、恢复页开始复用同一套运行态摘要与建议文案
- 进一步降低 provider degraded 时的界面噪音，把“该等待还是该恢复”统一成更稳定的产品文案

### Next.js 页面构建修复
- 为 `/library`、`/control`、`/reader`、`/qa`、`/ops` 等工作台页面补充 SSR 入口
- 修复 `npm run build` 时 `/reader`、`/qa` 等页面 prerender 阶段报 `Cannot find module for page` 的问题
- 当前工作台页面已明确作为动态产品界面按需服务，而不是强行静态导出

### 文档同步
- 更新 `apps/web/README.md`
- 更新 `docs/final-handoff.md`

### 章节跳转状态同步修复
- 修复 reader 内部章节跳转时“界面切到新章节，但 URL 仍停留旧章节”的状态分裂问题
- 修复因此引发的章节被 `router.query.chapter` 回拉到旧值、点击后跳错章/跳回旧章的问题
- 现在左侧目录、章节内引用跳转、问答引用跳转都会优先同步 reader 路由参数，再加载对应章节
- 切换章节时会先清空上一章内容，避免出现“左侧高亮和 URL 已切换，但右侧正文还短暂显示旧章节”的闪烁错位

### 当前作品状态持久化修复
- 修复进入 `/library`、`/ops` 等页面时，工作台在 hydration 前被默认示例小说状态覆盖的问题
- 修复因此导致“明明已选中别的小说，但页面一刷新/一跳转又回到默认示例小说”的问题
- 现在只有在本地 workbench 状态完成加载后，才会开始自动写入 localStorage 和执行首次分支刷新

### 控制台继续拆书入口增强
- 在控制台顶部 Hero 区增加显性的“继续拆书 / 刷新进度 / 导出 / 恢复”按钮组
- 将进度区按钮文案从“继续整理后续章节”改为更直白的“继续拆书到后续章节”
- 减少“功能存在但入口不明显”带来的误判，方便直接进入下一轮批量拆书

### 异步可观测流水线 Phase 0 启动
- 扩展 `chapter_jobs` 可观测字段：`current_stage`、`progress_percent`、`heartbeat_at`、`failure_class` 等
- 新增 `chapter_job_events` 表，用于记录章节任务过程事件
- 现有同步拆书流程开始写入基础事件：`job_started`、`stage_started`、`stage_completed`、`stage_failed`、`artifact_saved`、`job_completed`、`job_failed`
- 新增 `novel-analyzer list-job-events` CLI 命令
- 新增 `GET /api/job-events` 接口，便于后续前端任务控制台接入

### 异步可观测流水线 Phase 1 后端骨架
- 新增 `pipeline_runs` 表，用于持久化一次后台拆书区间任务
- 新增最小可用的后台 daemon pipeline runner：支持从当前 `next_chapter` 连续推进到目标章数
- 新增 API：
  - `POST /api/pipeline/start-range`
  - `GET /api/pipeline/status`
  - `GET /api/pipeline/runs`
  - `POST /api/pipeline/pause`
  - `POST /api/pipeline/resume`
  - `POST /api/pipeline/cancel`
- 当前版本仍是单进程原型级异步执行，但已经完成“控制面/API 与执行线程解耦”的第一步

### 拆书流水线前端控制台接入
- 新增 `/pipeline` 页面与工作台导航入口
- 前端已接入后台流水线 API：启动、暂停、恢复、取消、查看最近 runs、查看章节事件流
- 当前控制台先聚焦“从 next_chapter 连续往后跑”的最小版本，用于先验证后台异步控制链路和事件可视化

### 拆书流水线任务台增强
- 新增 `GET /api/chapter-jobs`，返回章节级任务监控数据
- `/pipeline` 页面新增章节任务表，展示 `status / current_stage / progress_percent / attempts / heartbeat / failure_class`
- `/pipeline` 页面自动刷新频率收紧为 5 秒，更适合盯运行中任务

### 卡住任务保护（保守收口）
- 新增 `chapter_job_stall_timeout_seconds` 配置项，默认 180 秒
- 后端在 run status / chapter-jobs 查询以及 pipeline runner 循环中都会顺手扫描 stalled job
- 超过心跳阈值的 running job 会被保守地标记为 `failed + failure_class=stalled`
- `/pipeline` 页面新增 stalled 告警与汇总标签，优先让操作者看见“假 running / 真卡死”的问题

### Pipeline 任务详情增强
- 新增 `GET /api/chapter-job-events?branch_id=...&chapter_index=...`
- `/pipeline` 页面支持点击章节打开任务详情抽屉，查看该章事件链
- 进一步强化“先看清楚再处理”的操作体验，优先保证可读性与维护性

### Pipeline 过滤与恢复联动增强
- `/pipeline` 章节任务表新增过滤器：全部 / 运行中 / 失败 / stalled
- 单章任务详情抽屉新增失败摘要展示
- 当章节已有失败分类时，可直接从详情抽屉跳转到恢复页继续处理

### Pipeline 总览统计增强
- `/pipeline` 顶部新增章节任务统计卡：已完成 / 运行中 / 失败 / stalled
- 最近章节事件流新增错误/警告筛选，便于更快聚焦异常信号
- 当最近一次后台 run 已记录错误摘要时，会在页面顶部显式提醒

### 多小说上下文与栏目收口修复
- 修复切换到其他小说后，进入章节阅读时偶发丢失 `run_id / branch_id` 上下文并落回默认书第一章的问题
- reader / qa / ops / control / pipeline 路由现在会显式携带当前 `run_id + branch_id`
- 拆书流水线不再单独占用左侧主栏目，改为收纳到“开始整理”内部，以 tab 方式区分“开始整理 / 拆书流水线”

### 交接与下一步优化点补充
- 在 `docs/final-handoff.md` 中补充了下一阶段优化优先级（P0/P1/P2）
- 在 `docs/session-handoff-manual.md` 中补充了下一位继续开发者的执行优先级
- 在 `docs/cli-operations-manual.md` 与 `docs/release-handoff-brief.md` 中补充了维护建议与下一步优化顺序

### 本轮验证
- `cd apps/web && npm exec tsc --noEmit`
- `cd apps/web && NEXT_TELEMETRY_DISABLED=1 npm run build`
- `python3 -m compileall apps/api/app/main.py novel_analyzer/runtime/storage.py novel_analyzer/runtime/provider_health.py novel_analyzer/services/qa_service.py`

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
