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
- [`./loom/sota-imitation-progression-checklist.md`](./loom/sota-imitation-progression-checklist.md)
- [`./loom/weitu-real-effect-validation.md`](./loom/weitu-real-effect-validation.md)
- [`./loom/weitu-validation-log-20260511.md`](./loom/weitu-validation-log-20260511.md)

默认阅读顺序建议：

1. `cli-operations-manual.md`
2. `direct-usage-guide.md`
3. `loom/sota-imitation-progression-checklist.md`
4. `loom/weitu-real-effect-validation.md`
5. `loom/weitu-validation-log-20260511.md`

**分步调试与故障定位**：见 [`./ops-debug-manual-20260514.md`](./ops-debug-manual-20260514.md)（scenario-first 速查手册：环境自检 / 常见操作 / 故障决策树 / 反模式）。

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

---

## 12. Loom 记忆与张力命令（Phase 1+2+3）

Loom 是叠加在现有系统之上的记忆代谢与质量评估层。默认以 `shadow` 模式运行（并行计算但不影响主链路）。

### 12.1 环境变量

```bash
# 控制 Loom 记忆层模式
export NOVEL_ANALYZER_LOOM_MEMORY_MODE=shadow   # disabled | shadow | ab | enabled

# 控制张力检测
export NOVEL_ANALYZER_LOOM_TENSION_ENABLED=true

# 控制 pairwise 评估（默认关闭，需要 LLM）
export NOVEL_ANALYZER_LOOM_PAIRWISE_ENABLED=false

# 情节记忆 top-K 锚点数量
export NOVEL_ANALYZER_LOOM_EPISODIC_TOP_K=20

# 张力相似度回溯章节数
export NOVEL_ANALYZER_LOOM_TENSION_LOOKBACK_N=3

# Phase 4：文风量化 + 节奏分析（默认关闭，待 Phase 4 实现后启用）
export NOVEL_ANALYZER_LOOM_STYLE_ENABLED=false

# Phase 4：角色认知基（默认关闭，待 Phase 4 实现后启用）
export NOVEL_ANALYZER_LOOM_CHARACTER_ENABLED=false
```

### 12.2 loom-status — 查看分支记忆与张力状态

```bash
poetry run novel-analyzer loom-status <branch_id>
# 或
python3 -m novel_analyzer.cli.app loom-status <branch_id>
```

输出示例：
```
=== Loom Memory Status ===
branch_id:           <branch_id>
total_facts:         248
active_facts:        231
total_graph_nodes:   89
contradiction_nodes: 2
evolution_nodes:     14
loom_memory_mode:    shadow
loom_tension_enabled:True

=== Loom Tension (chapter 42) ===
tension_score:       0.5823
plot_similarity:     0.4210
conflict_density:    0.8500
surprise_index:      0.3200
alerts:              none
```

**说明**：
- `contradiction_nodes` > 0 时，建议运行 `loom-consolidate` 手动检查冲突
- `tension_score` < 0.3 时，情节可能过于平淡，建议引入新元素
- `plot_similarity` > 0.85 时，当前章节与前几章高度重复

### 12.3 loom-consolidate — 手动运行冲突代谢

```bash
poetry run novel-analyzer loom-consolidate <branch_id> <chapter_index>
```

对指定章节运行冲突检测与情节记忆衰减。通常由 `analysis_service` 在章节分析完成后自动调用（shadow/enabled 模式），此命令用于手动补跑或调试。

输出示例：
```
branch_id:      <branch_id>
chapter_index:  42
contradictions: 1
evolutions:     3
ambiguities:    0
human_review:   True
contradiction details:
  - 张三: '张三' 在第42章与第30章存在直接矛盾
```

### 12.4 loom-assemble — 查看 carry_over_state 内容

```bash
poetry run novel-analyzer loom-assemble <branch_id> <target_chapter>
```

输出 Loom 为目标章节组装的 `carry_over_state` JSON，用于调试记忆层内容。

```bash
# 示例：查看第 43 章的记忆组装结果
poetry run novel-analyzer loom-assemble <branch_id> 43
```

输出包含：
- `working_memory`：当前活跃角色、线索、近期摘要
- `episodic_anchors`：按重要性排序的关键事件锚点
- `semantic_snapshot`：角色数量、活跃规则、关键关系
- `_legacy_compat`：与现有 carry_over_state 格式兼容的字段

### 12.5 PostgreSQL 生产环境启用 Loom

**首次启用前必须运行 Alembic migration：**

```bash
# 方式 1：通过 novel-analyzer CLI
poetry run novel-analyzer db-upgrade

# 方式 2：直接运行 alembic
alembic upgrade head
```

migration 文件：`alembic/versions/20260509_01_loom_memory_fields.py`

新增字段（均有默认值，现有数据安全）：
- `fact_records`：`importance_score`、`decay_factor`、`episodic_status`
- `graph_nodes`：`conflict_status`、`loom_version`、`superseded_by_node_id`、`importance_score`
- `graph_edges`：`conflict_status`、`loom_version`、`is_active`

**切换到 enabled 模式：**

```bash
# .env.local 中设置
NOVEL_ANALYZER_LOOM_MEMORY_MODE=enabled
```

建议先用 `ab` 模式做 A/B 实验验证效果，再切换到 `enabled`：

```bash
NOVEL_ANALYZER_LOOM_MEMORY_MODE=ab
```

### 12.6 Loom 与现有命令的关系

Loom 是非侵入式的叠加层：

| 现有命令 | Loom 影响 |
|---------|---------|
| `analyze-range` | shadow/enabled 模式下，章节完成后自动调用 `loom-consolidate` |
| `harness-imitation` | preflight 新增 `loom_tension` 检查项（warn 级别，非阻塞） |
| `writer-imitate` | carry_over_state 在 enabled 模式下使用三层记忆组装 |
| 其他命令 | 完全不受影响 |

`loom_memory_mode=disabled` 时，所有 Loom 逻辑完全跳过，行为与 Loom 引入前完全一致。

---

### 12.6.1 writer-imitate / writer-imitate-range — 设定替换映射（mapping_pack）

**用途**：跨题材仿写（如把仙侠转成科幻），在生成时让 LLM 系统性地替换名称/世界设定/力量体系。

```bash
# 单章 mapping
novel-analyzer writer-imitate <branch_id> 2 "目标" \
  --use-llm --max-rounds 2 \
  --world-map "郑国=星际联邦" \
  --character-map "卫图=魏拓" \
  --power-map "养生功=星能调息术"

# 多章批量 mapping
novel-analyzer writer-imitate-range <branch_id> \
  "2:目标A" "3:目标B" "4:目标C" \
  --use-llm --max-rounds 2 \
  --world-map "郑国=星际联邦" --world-map "庆丰府=星辰城" \
  --character-map "卫图=魏拓" --character-map "卫荭=魏蓁" \
  --power-map "养生功=星能调息术" \
  --rule-override "封建奴籍体系替换为合同义务工制度"
```

支持的映射类型：
| flag | 用途 | 示例 |
|---|---|---|
| `--world-map` | 国家/地点替换 | `郑国=星际联邦` |
| `--character-map` | 人名替换 | `卫图=魏拓` |
| `--faction-map` | 势力/组织替换 | `黄家=星舰联合` |
| `--power-map` | 力量体系/功法替换 | `养生功=星能调息术` |
| `--rule-override` | 规则覆盖（可重复） | `奴籍替换为合同制度` |
| `--forbidden-transformation` | 禁止转化（可重复） | `不得出现魔法元素` |

**注意**：mapping 在 prompt-time 注入 LLM，由模型整体翻译章节到目标语境（不是 regex 字面替换）。
所有 mapping 信息会被持久化到 output JSON 的 `mapping_pack` 字段，便于审计。

---

### 12.6.2 writer-imitate-range-split — 把多章 range 输出拆为 per-chapter 文件

```bash
novel-analyzer writer-imitate-range-split \
  output/whole-book-weitu-19ch/writer-imitate-range-12-30.json
# 默认输出到 range_json 同目录，每章一个 writer-imitate-ch{N}.json
```

让 `writer-imitate-range` 的输出能被下游 `writer-imitate-review` / `loom-collect-pairs` 等消费。

---

### 12.7 loom-collect-pairs — 从 writer-imitate 产物提取 pairwise 数据

```bash
# 单目录模式：同一目录内 round-0 vs final（默认）
novel-analyzer loom-collect-pairs --output-dir output/ --pairs-file output/loom-pairs.jsonl

# 跨目录模式：baseline vs steering 对比
novel-analyzer loom-collect-pairs \
  --output-dir output/baseline/ \
  --compare-dir output/steering/ \
  --pairs-file output/loom-pairs.jsonl

# 使用 LLM-as-judge（需配置 LLM）
novel-analyzer loom-collect-pairs --output-dir output/ --use-llm
```

扫描 `--output-dir` 下的 `writer-imitate-ch*.json` 文件，提取 pairwise 对并追加写入 JSONL。

### 12.8 loom-collect-pairs-from-manual — 从人工评估工作区提取 pairwise 数据

```bash
novel-analyzer loom-collect-pairs-from-manual \
  --manual-eval-dir runs/manual_eval/ \
  --pairs-file output/loom-pairs.jsonl
```

扫描 `runs/manual_eval/` 下所有工作区（跳过 `_template`）的 `artifacts/writer-imitate-ch*.json`，提取 round-0 vs final pairwise 对，`pair_source=manual_eval_workspace`。

### 12.9 loom-collect-pairs-from-db — 从 DB 分支提取 pairwise 数据

```bash
novel-analyzer loom-collect-pairs-from-db <branch_a_id> <branch_b_id> \
  --pairs-file output/loom-pairs.jsonl
```

跨两个 DB 分支，按章节索引匹配 `ChapterArtifact` 记录，用 `chapter_summary` 作为对比文本。

### 12.10 loom-pairs-stats — 查看 pairwise 数据采集进度

```bash
novel-analyzer loom-pairs-stats --pairs-file output/loom-pairs.jsonl
```

输出示例：
```
=== Loom Pairwise Data Stats ===
pairs_file:        output/loom-pairs.jsonl
total_pairs:       47
target:            500
progress:          9.4%
avg_quality_score: 0.6823
unique_chapters:   12
chapter_range:     1–42

preference distribution:
  A: 21
  B: 19
  tie: 7

evaluation_method distribution:
  heuristic: 47

pair_source distribution:
  manual_eval_workspace: 12
  single_dir_rounds: 35

remaining_to_target: 453
```

### 12.11 loom-ab-compare — A/B 实验对比报告

```bash
novel-analyzer loom-ab-compare output/baseline/ output/loom/ \
  --output-file output/ab-report.json
```

对比两个 writer-imitate 输出目录的 `character_ooc` 触发率和 Loom 信号差异。

输出包含：
- character_ooc 触发率对比（目标下降 ≥20%）
- risk level / verdict 分布变化
- Loom 信号对比（tension / hook / style_drift / chars / reader_sim / fidelity）

### 12.12 loom-reference-eval — 仿写还原度评估（vs 原文）

```bash
# 单章评估
novel-analyzer loom-reference-eval <branch_id> <chapter_index> <draft_dir>

# 批量评估（chapter_index=0 扫描目录内所有章节）
novel-analyzer loom-reference-eval <branch_id> 0 <draft_dir>

# 两个目录对比（A vs B 各自对原文的 fidelity）
novel-analyzer loom-reference-eval <branch_id> 0 <draft_dir_a> --compare-dir <draft_dir_b>
```

以原文为 gold standard，评估仿写草案的还原程度。6 个维度：

| 维度 | 含义 |
|------|------|
| `structure_fidelity` | 场景节拍、推进节奏是否与原文一致 |
| `character_fidelity` | 角色行为、语气、动机是否与原文一致 |
| `style_fidelity` | 文风、用词习惯、叙事视角是否与原文一致 |
| `continuity_fidelity` | 是否正确承接前文、保持世界观一致 |
| `tension_fidelity` | 冲突密度、悬念设置是否与原文水平匹配 |
| `information_density` | 每千字推进量是否与原文匹配 |

输出示例（单章）：
```
=== Loom Reference Eval (chapter 2) ===
original_title:      二姑卫荭
draft_len:           1363
evaluation_method:   llm_reference_judge
overall_fidelity:    0.4900
confidence:          0.8200
suggestion:          将大段连续叙述拆解为原文式的短句短段...

dimensions:
  structure_fidelity: 0.3200
  character_fidelity: 0.5200
  style_fidelity: 0.3800
  continuity_fidelity: 0.6800
  tension_fidelity: 0.5000
  information_density: 0.5800
```

输出示例（批量对比）：
```
=== Loom Reference Eval (batch) ===
branch_id:   62e636f0-c901-4167-aa1c-aff3da9c83ef
draft_dir:   /tmp/enhanced/
compare_dir: /tmp/baseline/

  ch2: A=0.350  B=0.150  delta=-0.200
  ch3: A=0.300  B=0.450  delta=+0.150
  ch4: A=0.450  B=0.150  delta=-0.300
```

**关键说明**：
- Reference-based 评估是**主评估方式**（衡量"像不像原作"）
- Pairwise A vs B 是辅助评估（衡量"哪个更好看"）
- `overall_fidelity < 0.5` 时 gate summary 触发 `fidelity-blocked`
- 需要 LLM provider 可用；不可用时 fallback 到 heuristic（基于文本长度和字符重叠）

### 12.13 export-whole-book-imitation-run — 导出整书仿写执行报告（含 Loom 摘要）

当你需要把整书仿写的 dry-run / sandbox execute 结果交给下游系统、评估层或后续执行器消费时，使用：

```bash
python3 -m novel_analyzer.cli.app export-whole-book-imitation-run \
  <branch_id> \
  "项目名" \
  "源作名" \
  "目标作名" \
  /tmp/whole-book-report.json \
  "2:延续主线" \
  "3:加深冲突" \
  --execute
```

#### 这次补强了什么

**Changelist marker**：`CL-loom-whole-book-bridge-01`

之前 `writer-imitate-session-state.json` / `writer-imitate-operator-surface.json` 已有：
- `session_loom_signals`
- `session_loom_gate_summary`

但 whole-book export report 还没有统一继承这些 Loom 视图，导致：
- 下游如果只消费 whole-book report，看不到 Loom 质量/张力结论
- operator 看到的 gate 与执行器侧产物不完全一致

现在 whole-book report 也统一新增：
- `session_loom_signals`
- `session_loom_gate_summary`
- `executed_steps[*].loom_signals`

#### 关键字段

| 字段 | 含义 |
|------|------|
| `session_loom_signals.average_chapter_quality_score` | whole-book sandbox 章节平均质量分 |
| `session_loom_signals.average_tension_score` | whole-book 平均张力分 |
| `session_loom_signals.average_style_drift_score` | 风格漂移均值 |
| `session_loom_signals.average_hook_density` | 爽点/钩子密度均值 |
| `session_loom_signals.average_reader_sim_score` | 读者模拟满意度均值 |
| `session_loom_signals.average_reference_fidelity` | 对原文还原度均值 |
| `session_loom_gate_summary.quality_verdict` | `quality-pass` / `quality-hold` |
| `session_loom_gate_summary.gate_status` | 当前 whole-book Loom gate 状态（monitoring / fidelity-blocked / reader-sim-warn） |
| `executed_steps[*].loom_signals` | 每章真实 harness Loom 输出的聚合快照 |

#### 解决的问题

1. 解决 whole-book 执行报告绕开 Loom gate 的问题
2. 解决 service 层有 Loom 聚合、CLI 导出边界缺合同验证的问题
3. 让更接近执行器的整书产物与 operator surface 保持一致视图

#### 推荐验证

```bash
python3 -m pytest tests/test_whole_book_imitation_service.py tests/test_cli.py -v
```

重点检查导出 JSON 中是否存在：
- `session_loom_signals.contract_version=whole-book-session-loom-signals.v1`
- `session_loom_gate_summary.contract_version=loom-gate-summary.v2`

### 12.13 bootstrap_weitu_validation_workspace.py — 卫图样例验证工作区一键初始化

如果你要复现当前 Loom 的卫图样例真实验证，不要手动逐条导出 artifact，直接运行：

```bash
python3 scripts/bootstrap_weitu_validation_workspace.py \
  62e636f0-c901-4167-aa1c-aff3da9c83ef \
  weitu-sample \
  --force
```

这条命令会自动完成：

1. 创建/重建 `runs/manual_eval/weitu-sample/`
2. 导出 `weitu-branch-bundle.json`
3. 导出 `weitu-whole-book-report.json`
4. 导出 `weitu-branch-report.md`
5. 生成 mailbox-style 的 `README.md / manual-review-notes.md / next-actions.md / problem-trace.md`

它解决的问题是：

- 过去卫图验证工作区需要手工逐条导出 artifact
- 人工兜底入口与 resume 链条说明分散在多份文档里
- 同一轮验证很难稳定复现

现在这条脚本把：

- Loom 当前执行证据
- whole-book report
- manual_eval mailbox 工作区
- resume/recovery 下一步

收成一个可重复执行的入口。


## 拆书加速优化（当前版本）

当前拆书加速优化已落地的重点不是完整 quick/deep 异步流水线，而是：
- canonical quick metadata 的安全引入
- 默认 reader / status / chapter index / window 的 canonical-only 口径
- blocking materialization 失败时恢复 previous active artifact
- regression / benchmark / docs / usage evidence

推荐使用说明见：
- `docs/deconstruction-acceleration/user-manual.md`

当前建议 CLI 验证顺序：
1. `show-run-status`
2. `show-context`
3. `show-window`
4. `search-branch` / `ask-branch`

若后续引入 companion / manual artifact，请记住：
- 不是所有 active artifact 都会进入默认读路径
- 默认 reader 只消费 canonical/default-readable artifact


## 底座优化运维（P0 闭环）

P0 链路：领域词典 → pg_jieba → bm25_vector。完整说明见 [foundation-optimization/p0-quickstart-and-handoff.md](./foundation-optimization/p0-quickstart-and-handoff.md)。

### `domain-dict-rebuild`

从 DB 重建 `domain-dict.txt` + `jieba-user-dict.txt`。

```bash
# 默认：自动发现所有有 retrieval_documents 的 branch
python -m novel_analyzer.cli.app domain-dict-rebuild

# 可选：指定 branch 子集
python -m novel_analyzer.cli.app domain-dict-rebuild \
  --branch-id 72da24e9-... --branch-id 2ac6f639-...
```

输出文件位置：`.cache/novel-analyzer/{domain-dict.txt, jieba-user-dict.txt}`。

### `bm25-reindex`

强制重建 `retrieval_documents.bm25_vector` 列（`ALTER TABLE DROP+ADD GENERATED ALWAYS`），用当前 jieba tokenizer 状态全表重写。

```bash
# 必须先 dry-run 确认 tokenizer 已加载新 userdict
python -m novel_analyzer.cli.app bm25-reindex

# 确认后真正执行
python -m novel_analyzer.cli.app bm25-reindex --confirm
```

**前置条件**：先重启 PG 容器加载新 userdict。dry-run 会做 tokenizer 自检并 WARN 但不会拒绝执行。

### `rematerialize-retrieval`

修复缺失的 `retrieval_chunks` / `chunk_embeddings`（典型场景：诊断时手工 DELETE 留下的孤儿 retrieval_documents）。

```bash
# dry-run 列出所有缺 chunks 的 doc
python -m novel_analyzer.cli.app rematerialize-retrieval

# 真正执行（会重跑 ONNX embedding，每章 ~1-2s）
python -m novel_analyzer.cli.app rematerialize-retrieval --confirm

# 限定 branch
python -m novel_analyzer.cli.app rematerialize-retrieval \
  --branch-id 72da24e9-... --confirm
```

### `retrieval-benchmark`

跑 BM25 召回率 + MRR 基准，对比不同 FTS config，可选多路融合 fullpipeline 模式。

```bash
# BM25-only 对比 simple vs jiebacfg（默认）
python -m novel_analyzer.cli.app retrieval-benchmark <branch_id> \
  --output-file /tmp/bench.json

# 带 fullpipeline（多路 RRF + rerank，慢，建议配 --max-queries）
python -m novel_analyzer.cli.app retrieval-benchmark <branch_id> \
  --configs simple,jiebacfg,fullpipeline \
  --max-queries 10 --output-file /tmp/bench.json
```

Query bank 自动从 `keyword_list` 构建，DF >40% 的常见词被过滤；输出 JSON 含 per-config Recall@1/3/5/10、MRR、平均延迟。

### `loom-benchmark`

跑 LLM 综合能力基准（拆书 / 仿写 / 风险检查三维），需要可用 LLM。

```bash
python -m novel_analyzer.cli.app loom-benchmark <branch_id> \
  --chapters "2,3,4,5" --use-llm \
  --output-file /tmp/loom.json
```

详见 `novel_analyzer/services/model_benchmark_service.py`。

### 完整 P0 刷新流程

字典更新后的标准动作（每次都跑一遍）：

```bash
# 1) 重建词典文件
python -m novel_analyzer.cli.app domain-dict-rebuild

# 2) 复制 + 过滤到 PG 容器挂载目录
python <<'PY'
import re
src = open('.cache/novel-analyzer/jieba-user-dict.txt', encoding='utf-8').readlines()
def ok(t):
    if len(t) < 2 or len(t) > 10: return False
    if re.search(r'[，。！？、；：「」【】()（）\s\u3000]', t): return False
    return len(re.findall(r'[\u4e00-\u9fff]', t)) >= 2
keep = [l.strip() for l in src if l.strip() and ok(l.strip().split()[0])]
open('/home/user/pgsql17-ubuntu24/jieba/dicts/novel_analyzer.dict','w',encoding='utf-8').write('\n'.join(keep)+'\n')
print(f'wrote {len(keep)} terms')
PY

# 3) 重启 PG 容器
sudo docker restart d2-pg17 && sleep 15

# 4) 重建 bm25_vector（必须新连接）
python -m novel_analyzer.cli.app bm25-reindex --confirm

# 5) 验证
python -m novel_analyzer.cli.app retrieval-benchmark <branch_id> \
  --output-file /tmp/post-bench.json
```
