# 拆书加速优化用户手册

> 本手册面向“要直接使用当前拆书主线的人”，重点说明：
> 1. 当前这批改进到底已经落地了什么；
> 2. 哪些仍是后续规划；
> 3. 如何安全使用、验证，并确认**不会影响当前仿写默认行为**。

---

## 0. 整条链路的输入说明

### 0.1 数据库输入
当前推荐**显式传入 `--database-url`**，不要只依赖 shell 环境变量。

推荐格式：
```bash
postgresql+psycopg://<user>:<password>@<host>:<port>/<db_name>
```

例如：
```bash
postgresql+psycopg://d2:d2pass@127.0.0.1:5432/novel_analyzer_deconstruction_20260511
```

### 0.2 LLM 输入
当前真实试跑建议显式配置：
- `base_url`
- `model`
- `api_key`
- stage / qa / fallback model

如果是同一 provider 同一模型统一试跑，建议把：
- `NOVEL_ANALYZER_LLM_BASE_URL`
- `NOVEL_ANALYZER_LLM_MODEL_NAME`
- `NOVEL_ANALYZER_LLM_STAGE_MODEL_NAME`
- `NOVEL_ANALYZER_LLM_QA_MODEL_NAME`
- `NOVEL_ANALYZER_LLM_FALLBACK_MODEL_NAME`
全部显式对齐。

### 0.3 小说文本输入
必须提供：
- 本地 txt 文件路径
- 可选标题 `--title`

当前试跑样例：
```bash
/home/user/download_novel/down/万相之王.txt
```

### 0.4 CLI 参数输入
当前拆书主链至少会用到：
- `ingest <path> --title ... --database-url ...`
- `start-run <novel_id> <manifest_id> --database-url ...`
- `analyze-range <run_id> <branch_id> <start> <end> --database-url ...`
- `show-run-status <run_id> <branch_id> --database-url ...`
- `show-context <branch_id> <chapter_index> --database-url ...`
- `show-window <branch_id> <start> <end> --database-url ...`
- `search-branch <branch_id> <query> --database-url ...`
- `ask-branch <branch_id> <question> --database-url ...`

### 0.5 QA / 检索输入
QA 与检索当前都依赖：
- 已物化的 canonical/default-readable artifact
- branch_id
- query / question 文本

### 0.6 当前一个真实注意事项
本轮真实验证中发现：
- `init-db` 使用环境变量初始化新库可以成功
- 但 `db-health` 直接依赖环境变量时出现过“数据库不存在”的异常
- 使用显式 `--database-url` 后恢复正常

因此：
- **当前推荐实际运行时始终显式传 `--database-url`**
- 把“环境变量直跑 db-health 异常”记为现阶段 CLI / 配置读取链路问题

---

## 1. 当前这批改进已经落地了什么

当前已经落地并可依赖的能力：

1. **canonical quick metadata 已开始进入主链**
   - 以 `_deconstruction_profile` 的 shadow metadata 形式出现
   - 不会改名或替换 `ChapterAnalysisOutput` 既有字段

2. **默认 reader 口径已收紧**
   - 默认读取只消费 canonical / default-readable artifact
   - non-downstream companion 不会自动覆盖 canonical active artifact

3. **blocking materialization 安全性提升**
   - retrieval / fact / graph / fixed-window 仍保持 blocking
   - 若 materialization 在 artifact persist 后失败，会恢复 previous active artifact，而不是留下半成品 active state

4. **基线 benchmark 与回归保护已补齐**
   - 已补 context / chapter index / status / run service 的 reader-isolation 回归
   - 已补 canonical 默认读路径的 benchmark baseline

---

## 2. 当前还没有真正落地的部分

这点很重要，避免误用：

### 2.1 还没有完全落地的 Quick / Deep 运行时切换
虽然文档、PRD、测试和部分 metadata 已经到位，但当前仍属于：
- **安全主线 + 默认读口径 + 验证基线先落地**
- 而不是“已经有完整 quick/deep 双档 CLI 开关并大规模异步运行”

### 2.2 本轮没有开启新的默认异步写回语义
当前没有把 retrieval / fact / graph / window 这些下一章依赖的物化链异步化。

### 2.3 这轮不是“整本 100 章极限提速版本”
当前更像是：
- 先把**安全边界**和**默认行为保护**做对
- 再为后续更快的 quick/deep 主线铺路

---

## 3. 这批改进对你日常使用意味着什么

### 3.1 默认 CLI 使用方式不需要重学
你仍然主要使用：
- `ingest`
- `start-run`
- `analyze-next`
- `analyze-range`
- `show-run-status`
- `show-chapter`
- `show-context`
- `show-window`
- `search-branch`
- `ask-branch`

### 3.2 默认读路径现在更安全
如果后续有人给某一章加了 companion / manual / shadow 类产物：
- **它不会默认污染**
  - `previous_summary`
  - `chapter index`
  - `completed chapter count`
  - `fixed window summary`
  - 默认 branch/status 消费口径

### 3.3 对仿写默认行为的保护更强了
本轮的原则就是：
- **拆书链加速优化不能误伤仿写默认行为**

所以这轮的新增验证明确覆盖了：
- `tests/test_imitation_harness_service.py`
- `tests/test_whole_book_imitation_service.py`
- 相关 context/read-path 基线

---

## 4. 推荐使用流程（当前版本）

### Step 1：准备环境
按 `README.md` 的 PostgreSQL / LLM / embedding 配置来准备。

如果只是做当前主线验证，建议：
- PostgreSQL 走 README 里的本地配置
- embedding 在测试环境下可用 stub / onnx 之一
- 真实跑小说时再切到你的正式 provider 配置

### Step 2：导入小说
```bash
poetry run novel-analyzer ingest /path/to/novel.txt --title 'sample'
```

### Step 3：创建 run
```bash
poetry run novel-analyzer start-run <novel_id> <manifest_id>
```

### Step 4：按小步推进
推荐继续用小批量推进：
```bash
poetry run novel-analyzer analyze-next <run_id> <branch_id>
```
或：
```bash
poetry run novel-analyzer analyze-range <run_id> <branch_id> 1 3
```

### Step 5：查看状态与上下文
```bash
poetry run novel-analyzer show-run-status <run_id> <branch_id>
poetry run novel-analyzer show-chapter <branch_id> <chapter_index>
poetry run novel-analyzer show-context <branch_id> <chapter_index>
poetry run novel-analyzer show-window <branch_id> 1 5
```

### Step 6：做安全验证
建议至少检查：
- `show-run-status` 的 completed / next chapter 是否合理
- `show-context` 是否仍只读 canonical/default-readable 结果
- `show-window` 是否未被 companion 产物污染

---

## 5. 如何确认“改进后的流程能正常运行”

当前这轮最核心的验证方式，不是看 UI，而是看几类行为是否稳定：

### 5.1 run service 行为
- non-downstream artifact 不应隐藏 canonical active artifact
- previous active artifact 在 blocking materialization 失败时会恢复

### 5.2 context / chapter index / status 口径
- `previous_summary` 只读 canonical
- `chapter index` 不被 non-downstream companion summary 污染
- completed chapter count 只统计 canonical/default-readable artifact

### 5.3 imitation 默认行为
- context bundle / imitation harness / whole-book imitation 不因本轮修改而回归

### 5.4 benchmark baseline
当前已记录一个 canonical 默认读路径基线，后续 quick/deep 真正启用时，可以拿它做对照。

---

## 6. 当前已知的真实验证证据

本轮已确认通过的验证包括：

- `tests/test_run_service.py` → 5 passed
- `tests/test_context_service.py` → 2 passed
- `tests/test_chapter_index_service.py` → 2 passed
- `tests/test_status_service.py` → 2 passed
- `test_analysis_service` rollback regression → 1 passed, 19 deselected
- retrieval + fact + graph suite → 22 passed
- `tests/test_context_bundle_cli.py` + `tests/test_imitation_harness_service.py` + `tests/test_whole_book_imitation_service.py` → 17 passed

另有 benchmark baseline：
- rounds = 200
- total_ms = 5154.937
- avg_ms = 25.775

---

## 7. 使用时最重要的注意事项

### 7.1 不要误以为“当前已经有完整 async deep lane”
当前更准确的状态是：
- **reader isolation / canonical safety / blocking materialization 安全性先落地**
- 完整 quick/deep runtime 调度仍是后续工作

### 7.2 companion / manual artifact 不等于默认可读 artifact
如果你在后续调试时手工写入 artifact，请注意：
- 不要因为它是 active row，就默认认为它会成为 canonical 读结果

### 7.3 这轮的目标不是“极限提速”，而是“先把边界做对”
如果你现在就想跑真实长书：
- 可以跑
- 但应该把它视为“安全主线 + 基线观测”
- 而不是“最终版快拆 100 章流水线”

---

## 8. 推荐的实跑顺序（当前版本）

建议这样做：

1. 先用一部短文本或前 1~3 章验证 `show-run-status / show-context / show-window`
2. 再做 5 章级验证，观察 fixed window summary
3. 再用你提供的正式 provider 配置跑候补小说样例
4. 对照 benchmark baseline，观察后续 quick/deep 真实优化收益

---

## 9. 后续你最该关注的 3 个指标

1. **canonical progress 是否稳定**
2. **默认读路径有没有被 companion 污染**
3. **后续真正引入 async/deep lane 时，是否还能保持 imitation 默认行为不变**

---

## 10. 关联文档

- [architecture.md](./architecture.md)
- [development-guide.md](./development-guide.md)
- [benchmark-baseline-20260511.md](./benchmark-baseline-20260511.md)
- [critical-open-points.md](./critical-open-points.md)
- [../direct-usage-guide.md](../direct-usage-guide.md)
- [../cli-operations-manual.md](../cli-operations-manual.md)
- [../../README.md](../../README.md)


## 11. 真实试跑已验证到哪一步

当前已在独立新库上验证通过：
- 新库创建
- schema 初始化
- 小说导入（《万相之王》100 章）
- run / branch 创建
- 使用 DeepSeek `deepseek-v4-flash` 真实启动拆书
- 至少前 3 章已成功完成 canonical artifact / fact / graph / risk card 生成
- `show-run-status` 可正确显示 completed/running/next_chapter
- `show-context` 可正确返回 previous_summary / fact_context / graph_context
- `search-branch` 可返回命中章节
- `ask-branch` 可返回带 evidence / reasoning_path / graph_signal 的答案

### 当前真实运行中已暴露并修复的问题
1. **风险审计缺表**
   - 问题：`gate_checker_results` / `chapter_risk_cards` 未进入新库初始化链路
   - 影响：第 1 章 risk aggregation 时直接报 `UndefinedTable`
   - 处理：补 Alembic 迁移 `20260511_02_risk_audit_records.py`

2. **`db-health` 环境变量直跑不稳定**
   - 问题：同一套配置下，`init-db` 成功，但 `db-health` 直接吃环境变量时曾报“database does not exist”
   - 处理建议：当前实际运行**始终显式传 `--database-url`**

### 当前仍待继续验证
- 前 20 章整段长跑是否 0 failed
- 第 5 章后的 `show-window`
- 更长跑下的 provider 稳定性与耗时分布


### 真实运行补充结论（2026-05-11）
当前独立新库 + 真实 DeepSeek 试跑已经进一步确认：
- 前 1~5 章可以成功完成
- 第 4 章起曾从 staged pipeline 降级到 `monolithic_fallback`，但仍能继续向前推进
- 这说明当前真实风险不再是“流程跑不起来”，而是：
  - 某些章节在 `fact_extractor` 阶段会触发降级
  - 系统依赖 fallback 保持主线继续

因此当前版本更准确的描述应是：
- **主线可跑通**
- **fallback 可工作**
- **阶段稳定性仍需继续优化**
- **不是所有章节都稳定走完小模型 staged path**

进一步的真实运行证据：
- 前 8 章可连续完成
- 第 9 章再次出现 `job stalled for more than 180 seconds`，而且这次卡在 `evidence_binder @ 30%`，说明稳定性问题不是单一 `fact_extractor` 阶段专属，而是 staged pipeline 的中间阶段在真实长跑下都可能出现 stall

## 12. 推荐的当前最稳妥运行方式

### 12.1 数据库
优先用独立新库，不污染已有主库。

### 12.2 配置传递
- **数据库：显式 `--database-url`**
- **LLM：环境变量显式对齐 base_url / model / key / stage / qa / fallback**

### 12.3 推荐命令顺序
1. `init-db --database-url ...`
2. `db-capabilities --database-url ...`
3. `ingest ... --database-url ...`
4. `start-run ... --database-url ...`
5. `analyze-range ... --database-url ...`
6. 过程中穿插：
   - `show-run-status`
   - `show-context`
   - `search-branch`
   - `ask-branch`
   - 第 5 章后 `show-window`

## 13. 当前版本的故障恢复建议

### 情况 A：risk / checker 相关缺表
先做：
```bash
python3 -m novel_analyzer.cli.app init-db --database-url <dburl> --no-ensure-db
python3 -m novel_analyzer.cli.app db-capabilities --database-url <dburl>
```
确认：
- `initialized_schema=true`
- `missing_tables=` 为空

### 情况 B：db-health 明明建库成功却报库不存在
优先怀疑配置读取链路，而不是数据库本身。

处理：
- 改用显式 `--database-url`
- 用 `db-capabilities --database-url ...` 作为更可靠的判定口径

### 情况 C：QA / search 结果异常
先检查：
- 当前是否已有 active canonical artifacts
- `show-run-status` 的 `completed_chapters` 是否大于 0
- `show-context` 是否能返回 previous_summary / fact_context / graph_context

### 情况 D：还没到第 5 章却要看 window
这是正常现象。固定 window 需要在 5 / 10 / 15 ... 章边界后才能验证。


### 情况 E：长跑中某一章卡在 fact_extractor / stall timeout
真实试跑里已经遇到过：
- 前 1~3 章通过
- 第 4 章在 `fact_extractor` 阶段卡住
- 180 秒后被系统判定为 `job stalled for more than 180 seconds`

这说明当前版本虽然能跑通前几章，但在真实模型 / 真实文本下仍可能出现阶段性 stall。

建议处理顺序：
1. 先看 `show-run-status` / `list-failed-jobs`
2. 确认失败章、失败阶段、attempts
3. 优先做一次 `retry-chapter`
4. 若重复在同一阶段 stall，再检查：
   - provider 响应耗时
   - chapter 文本长度 / prompt 负载
   - `chapter_job_stall_timeout_seconds` 是否过低

当前结论：
- 这属于**真实运行稳定性问题**
- 不是 schema 初始化问题
- 也不是默认 reader / QA / context contract 问题

- 当前版本新增了一个重要保护：若某章已经拥有 active canonical artifact，则 `retry-chapter` 会被拒绝，以避免 job 状态与 artifact 进度出现错位。

- 当前默认 `chapter_job_stall_timeout_seconds` 已提高到 600；真实长阶段调用若仍出现 stall，再考虑更细粒度 heartbeat 或更早 fallback。

### 5.5 QA 新证据分层（本轮新增）
当前 `ask-branch` 回答结果内部已补充更细的证据分层：
- `chapter_evidence`
- `window_evidence`
- `graph_evidence`

同时会先做问题类型识别（如人物 / 关系 / 世界规则 / 时间线 / 伏笔），再对检索命中做轻量 rerank，并在证据偏薄时更保守地回答，减少“答得像对、其实证据不够”的情况。

### 6.4 卫图真实验证结论（2026-05-11）
当前已在独立数据库中对“卫图”前 20 章链路做真实运行验证，其中前 5 章已完成并验证：
- `show-run-status`
- `show-chapter`
- `show-context`
- `show-window 1-5`
- `search-branch`
- `ask-branch`

结论：
- 链路可运行、可检索、可 QA；
- 但当前速度仍偏慢，前 5 章约 31 分钟，主要受单章串行 LLM stages 耗时影响。

### 6.5 当前真实运行中的兜底行为
在卫图真实样例运行中，第 6 章曾出现一次 `small_model_pipeline` 的 JSON 修复失败；系统随后自动进入 `monolithic_fallback` 并完成该章。

这说明：
- 当前版本虽然不够快；
- 但遇到阶段性模型输出不稳定时，已经具备一定的自动兜底能力。

### 6.6 当前已落地的加速动作（第 1 刀）
当前 quick 主链已把 `writer_learning_lens` 从同步阶段移出，改为 deferred：
- 章节仍会保留 `writer_learning_notes` 字段；
- 但默认值可为空；
- `_deconstruction_profile.writer_lens_status` 会标记为 `deferred`。

这意味着：
- 默认 status/context/search/QA 链路不受影响；
- 每章会少一次同步模型调用，是当前版本最安全的提速动作之一。

### 6.7 当前已落地的加速动作（第 2 刀）
当前 quick 主链已把 `risk_aggregation` 从同步尾部工作中移出，改为 deferred。

这意味着：
- 章节主产物、context/search/QA 主链先完成；
- risk card 聚合不再拖慢当前章的返回与下一章推进。

### 6.8 卫图完整 20 章真实验证结论
当前卫图前 20 章真实拆书已经完整跑通：
- `completed_chapters=20`
- `failed_jobs=0`
- `running_jobs=0`

说明当前版本已经具备：
- 真实长跑可完成性；
- 基本恢复/兜底能力；
- 可继续在完整链路上做性能对照优化。

### 6.9 当前已落地的加速动作（第 3 刀）
当前 `analysis_generator` 与 `anti_fabrication_guard` 已不再默认消费完整图谱 JSON，而是改为：
- 不传完整 `graph_context_json`
- 只传 compact `state_summary_json`

这意味着：
- continuity / guard 仍能参考关键前情状态；
- 但会显著减少阶段 prompt 的上下文体积，降低 token 成本。

### 6.10 当前已落地的加速动作（第 4 刀）
当前事实链路也已做 prompt 缩减：
- `fact_extractor` 不再携带完整图谱摘要；
- `evidence_binder` 只保留最小必要输入。

这意味着：
- 事实链路的同步 token 成本继续下降；
- 而输出结构、context/search/QA 消费契约仍不变。

### 6.11 当前已落地的加速动作（第 5 刀）
当前前情事实输入也已改为 compact 版：
- 只保留小规模前情摘要；
- 事实只保留关键信息，不再把大体积 evidence / metadata 整包传入同步 stage。

这意味着：
- quick 主链的同步 prompt 体积已被系统性压缩；
- 后续真实提速验证将更有意义，因为不是单点优化，而是多刀叠加后的主链瘦身结果。

### 6.12 性能护栏已落地
当前拆书 quick 主链的 prompt 缩减结果，已经被固化为测试护栏：
- 检查真实卫图样本上的 prompt 长度上限；
- 检查相对旧版 prompt 的缩减比例。

这意味着：
- 后续继续开发时，如果同步 prompt 又膨胀回去，会被测试直接拦住。

### 6.13 当前已落地的加速动作（第 6 刀）
当前上一章摘要输入也已做 compact 处理：
- 默认会截断到较短长度；
- 防止 previous_summary 在多个同步 stage prompt 中重复膨胀。

这意味着：
- quick 主链的公共上下文成本进一步下降；
- 且这一优化对多个 stage 同时生效。

### 6.14 运行观测能力已增强
当前拆书原始输出记录中，已经开始保存同步 stage 的 prompt 大小指标：
- `prompt_char_counts`
- `total_prompt_chars`

这意味着：
- 后续真实 benchmark 不只看总耗时；
- 还能直接对照“prompt 缩减是否真的换来了运行时间收益”。

### 6.15 真实 benchmark 脚本已就位
当前已经提供：
```bash
python3 scripts/benchmark_deconstruction_run.py <run_id> <branch_id> --database-url <dburl> --json
```

它可以直接汇总：
- `completed_chapters`
- `failed_jobs`
- `elapsed_seconds`
- `avg_seconds_per_completed_chapter`
- `prompt_char_totals`
- `per_chapter[*].total_prompt_chars`

因此下一次 provider 余额恢复后，可以直接做 funded-provider 对照跑。

### 6.16 benchmark CLI 已有自动化测试保护
当前 `scripts/benchmark_deconstruction_run.py` 已有自动化测试覆盖：
- 新 run（带 prompt metrics）
- 旧 run（不带 prompt metrics）

这意味着：
- 后续做真实性能对照时，benchmark 工具链本身也更可靠。

### 6.17 benchmark compare CLI 已就位
当前已经提供：
```bash
python3 scripts/compare_deconstruction_benchmarks.py baseline.json candidate.json --json
```

它可以直接比较：
- `elapsed_seconds`
- `avg_seconds_per_completed_chapter`
- `failed_jobs`
- `prompt_char_totals`

所以 funded-provider 新 run 跑完后，可以立即做结构化对照，而不必手工算差值。

### 6.18 一键 benchmark runner 已就位
当前已经提供：
```bash
python3 scripts/run_deconstruction_benchmark.py <novel_path> --title <title> --database-url <dburl> --end-chapter 20 --ensure-db --json
```

它会自动执行：
- init-db（可选）
- ingest
- start-run
- analyze-range
- benchmark 汇总

因此 provider 可用后，可以直接跑一条新的真实 20 章对照链路。

### 6.19 benchmark 工具链 smoke 已跑通
当前已真实验证：
- `run_deconstruction_benchmark.py`
- `benchmark_deconstruction_run.py`
- `compare_deconstruction_benchmarks.py`

三者可以串成完整链路使用。

### 6.20 benchmark summary 已支持 fallback 识别
当前 benchmark summary 已额外输出：
- `fallback_modes`
- `fallback_chapter_count`
- `is_pure_primary_provider_run`

这意味着：
- 后续 funded-provider 对照时，可以明确知道某次 run 是否混入了 fallback / heuristic 路径。

### 6.21 benchmark bundle exporter 已就位
当前已经提供：
```bash
python3 scripts/export_deconstruction_benchmark_bundle.py baseline.json candidate.json out_dir
```

它会直接输出：
- `baseline.json`
- `candidate.json`
- `compare.json`
- `summary.md`

因此新的 funded-provider 对照 run 完成后，可以一键导出完整交付包。

### 6.22 compare CLI 已支持“严格可比性”判断
当前 compare 输出会额外给出：
- `chapter_count_match`
- `provider_purity_match`
- `is_strictly_comparable`
- `notes`

这意味着：
- 后续看到 delta 之前，先能判断这次 baseline/candidate 对照是否真的严格成立。

### 6.23 一键 benchmark bundle runner 已就位
当前已经提供：
```bash
python3 scripts/run_and_export_deconstruction_benchmark_bundle.py /path/to/novel.txt   --title 'benchmark'   --database-url <dburl>   --baseline-json docs/deconstruction-acceleration/benchmarks/weitu-baseline-20260511.json   --output-dir out_dir   --end-chapter 20   --ensure-db
```

它会自动完成：
- candidate run
- benchmark summarize
- compare
- bundle export

### 6.24 最终一键对照链真实 smoke 已跑通
当前已经真实验证：
- `run_and_export_deconstruction_benchmark_bundle.py`
会在真实数据库路径上自动完成：
- candidate run
- benchmark summarize
- compare
- bundle export

并且对 1 章 smoke vs 20 章旧基线的结果，能正确判定为 `is_strictly_comparable=false`。

### 6.25 funded-provider 对照 runbook 已就位
当前已经提供：
- `docs/deconstruction-acceleration/funded-benchmark-runbook.md`

它明确说明了：
- provider 恢复后该如何执行新 20 章对照 run
- 什么条件下结果才算严格可比
- 最终应该汇报哪些指标

### 6.26 benchmark bundle validator 已就位
当前已经提供：
```bash
python3 scripts/check_deconstruction_benchmark_bundle.py out_dir --json
```

它会自动检查：
- bundle 文件是否齐全
- compare 关键字段是否齐全
- comparability 字段是否齐全
