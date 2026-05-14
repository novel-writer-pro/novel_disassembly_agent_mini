# 卫图样例真实效果验证工作流

> 目标：用**现有卫图样例小说**验证 Loom 建设是否真的推进了主链路仿写能力。
>
> 重点不是证明“系统能跑”，而是回答：
>
> **Loom 是否真的让仿写更稳、更像、更少 OOC，并且减少人工盯跑负担。**

---

## 1. 本工作流验证什么

本工作流验证的是 **SOTA 仿写主链路**，不是单独验证某个技术组件。

### 关注的核心问题

1. Loom 打开后，卫图样例的仿写质量是否提升？
2. `character_ooc` 是否下降？
3. 多章节 carry-over 是否更稳定？
4. LLM 是否能优先完成大多数评估与筛查？
5. 复杂 case 转人工后，是否还能回到原执行链继续跑？

---

## 2. 本工作流的设计原则

### 2.1 主链路原则

- **主目标是推进 SOTA 仿写能力**
- 评估只是为了给主链路提供证据
- 不允许把“指标建设”误当成“仿写能力提升”

### 2.2 LLM-first / Human-fallback

- 默认优先让 LLM / 自动规则完成：
  - pairwise judge
  - Loom signals 聚合
  - A/B 对比
  - quality gate 初筛
- 只有复杂 case 才转人工：
  - 角色判断明显分歧
  - 风格评分冲突
  - 关键章节无法自动判定优劣

### 2.3 Resume-able

人工介入后，必须能回到原链条继续：

- `writer-imitate-execution-resume.*`
- `resume-run`
- `/api/recovery`
- checkpoint / transition / queue / recovery owner

---

## 3. 当前仓库里已经存在的基础能力

## 3.1 Loom 验证 CLI

当前已存在：

- `loom-collect-pairs`
- `loom-collect-pairs-from-manual`
- `loom-collect-pairs-from-db`
- `loom-pairs-stats`
- `loom-ab-compare`

这些命令用于：

- 从 writer-imitate 产物提取 pairwise 对
- 从人工评估工作区提取 pairwise 对
- 对比 baseline vs loom 的实际效果

## 3.2 人工工作区模板

当前已存在：

- `runs/manual_eval/_template/README.md`
- `scripts/bootstrap_manual_eval_workspace.py`

用途：

- 为需要人工兜底的章节建立评估工作区
- 保存 artifacts / exports / notes
- 为后续 pairwise 数据积累提供入口

## 3.3 恢复 / 续跑 / 兜底链

当前已存在的恢复面：

- `writer-imitate-execution-resume.*`
- `/api/recovery`
- queue / checkpoint / transition / recovery cursor / recovery owner 文档与控制面

因此本工作流不需要重新发明“mailbox”，而是把：

> **manual_eval 工作区 + review queue + recovery/resume surfaces**

当成 mailbox-style 的人工介入机制。

---

## 4. 推荐验证对象：卫图样例

推荐优先使用当前已有的卫图样例线：

- 主角：**卫图**
- 典型线索：`命格`、`养生功`、`龟息养气功`

在仓库内已有多处示例引用：

- `docs/direct-usage-guide.md`
- `docs/deconstruction-acceleration/benchmark-baseline-20260511.md`
- `tests/test_whole_book_imitation_service.py`

如果已有现成 branch / run / artifacts，可优先复用；否则按下方步骤重新建立。

### 当前已确认的真实验证目标

- `run_id`: `ac9449b9-7326-474f-bb72-4416375a7491`
- `branch_id`: `62e636f0-c901-4167-aa1c-aff3da9c83ef`
- `title`: `示例小说-fresh10-db-v2`

这条分支已确认包含卫图相关真实章节摘要，并且已实际跑通：

- `loom-status`
- `loom-assemble`
- `loom-consolidate`
- `export-whole-book-imitation-run --execute`

本轮验证默认优先复用这条分支。

---

## 5. 标准验证流程

## Step 0：准备环境

```bash
source .venv/bin/activate
python3 scripts/check_postgres.py
alembic upgrade head
```

确认：

- PostgreSQL 可用
- LLM provider 可用
- Loom migration 已在当前 DB 生效

---

## Step 1：准备卫图样例 branch

如果复用当前已确认分支，可直接记录：

```text
run_id=ac9449b9-7326-474f-bb72-4416375a7491
branch_id=62e636f0-c901-4167-aa1c-aff3da9c83ef
```

如果没有现成样例 branch，再新建：

```bash
python3 -m novel_analyzer.cli.app inspect-novel /path/to/weitu-sample.txt
python3 -m novel_analyzer.cli.app ingest /path/to/weitu-sample.txt --title "卫图样例"
python3 -m novel_analyzer.cli.app start-run <novel_id> <manifest_id>
```

记录：

- `novel_id`
- `manifest_id`
- `run_id`
- `branch_id`

---

## Step 2：建立 baseline 与 Loom 两组产物

### 2.1 baseline

建议：

- `loom_memory_mode=disabled`
- 其余 Loom 能力按最保守 baseline 关闭或最小化

对同一批章节生成 writer-imitate 产物。

> 注意：当前真实卫图分支已经证明 Loom 信号可运行，但**还没有 baseline 对照臂**。
> 因此当前阶段最多只能证明“Loom 在真实卫图分支上工作”，还不能证明“Loom 比 baseline 更好”。

### 2.2 loom

建议：

- `loom_memory_mode=ab` 或 `enabled`
- 打开需要验证的 Loom 能力

对同一批章节生成对应产物。

### 2.3 建议章节范围

最小可比样本：

- 卫图样例中连续 **5–20 章**

原因：

- 少于 5 章，长程 carry-over 价值不明显
- 高于 20 章前，先跑出第一轮趋势

---

## Step 3：优先让 LLM / 自动链完成验证

## 3.1 收集 pairwise 对

如果有 writer-imitate 输出目录：

```bash
python3 -m novel_analyzer.cli.app loom-collect-pairs baseline_dir loom_dir \
  --output-file output/loom-pairs.jsonl
```

如果要从 DB 两个分支抽取：

```bash
python3 -m novel_analyzer.cli.app loom-collect-pairs-from-db \
  <baseline_branch_id> <loom_branch_id> \
  --output-file output/loom-pairs.jsonl
```

## 3.2 查看数据积累情况

```bash
python3 -m novel_analyzer.cli.app loom-pairs-stats output/loom-pairs.jsonl
```

重点关注：

- `total_pairs`
- `avg_quality_score`
- `evaluation_method distribution`

### 重要说明

如果 `evaluation_method` 主要还是 `heuristic`，说明：

> 我们的“评估能力已建成”，但“真实 LLM judge 证据”仍然不足。

这时不要误报“已被真实证明有效”。

## 3.3 跑 A/B 对比

```bash
python3 -m novel_analyzer.cli.app loom-ab-compare baseline_dir loom_dir \
  --output-file output/weitu-ab-report.json
```

重点看：

- `character_ooc` 触发率变化
- reduction 是否达到预期（例如 ≥20%）

### 当前已执行到的最近一轮对比

基于同一真实卫图分支，已经执行过一轮 **baseline vs enhanced report** 对比。

观察到：

- enhanced 会新增 `chapter_quality_signal` / `style_signal`
- enhanced 的 `session_loom_gate_summary` 会从 `monitoring` 进入 `blocked-on-quality`

这说明：

> Loom enhanced 确实改变了执行器侧可观测产物。

但这还不等于：

> Loom 已被证明提升了仿写效果。

完整证据仍需要：

- baseline vs loom 双臂产物
- `character_ooc` 对照
- pairwise / manual review 闭环

目前这一步已经向前推进到：

- pairwise 工具链已在卫图样例上实际跑通
- A/B compare 已在 2 个章节上真实执行
- 但当前结果是 `tie` / `0.0% reduction`，因此仍不能宣布 Loom 已提升效果

---

## Step 4：只把复杂 case 转人工

## 4.1 何时转人工

满足任一条件时进入人工 mailbox：

- A/B 结果无法明确判断
- LLM judge 与规则信号明显冲突
- 卫图关键角色行为是否 OOC 存在分歧
- 风格/对话判断对最终结论影响很大

## 4.2 建人工工作区

推荐优先使用一键脚本，而不是手动拼命令：

```bash
python3 scripts/bootstrap_weitu_validation_workspace.py \
  62e636f0-c901-4167-aa1c-aff3da9c83ef \
  weitu-sample \
  --force
```

这条命令会自动：

- 创建/重建 `runs/manual_eval/weitu-sample/`
- 导出 `weitu-branch-bundle.json`
- 导出 `weitu-whole-book-report.json`
- 导出 `weitu-branch-report.md`
- 回填 notes / README，让人工兜底与 resume 链有明确入口

如果只想建空工作区，也可以继续用：

```bash
python3 scripts/bootstrap_manual_eval_workspace.py weitu-sample
```

得到：

- `runs/manual_eval/weitu-sample/`

本轮已实际创建该工作区，并已写入：

- `artifacts/weitu-branch-bundle.json`
- `artifacts/weitu-whole-book-report.json`
- `exports/weitu-branch-report.md`

把需要人工看的 artifacts 放进去：

- baseline 产物
- loom 产物
- whole-book report
- notes

## 4.3 人工 mailbox 处理原则

把 manual_eval 工作区视为 mailbox：

- `artifacts/` = 待处理输入
- `notes/` = 人工决策记录
- `exports/` = 处理后导出结果

要求：

- 人工只处理复杂章节
- 人工结论要可回收为 pairwise / manual data

---

## Step 5：人工处理后恢复原链路

## 5.1 writer-imitate 恢复

优先查看：

- `writer-imitate-execution-resume.json`
- `writer-imitate-execution-resume.md`

它们是“人工处理后怎么继续”的第一入口。

## 5.2 branch / pipeline 恢复

恢复链可用：

- `resume-run`
- `/api/recovery`
- checkpoint / transition / replay / apply / resume 面

### 恢复原则

人工介入后，应该：

1. 写明处理结论
2. 明确哪些章节/产物被确认
3. 回到最近的 resume / recovery 节点
4. 继续执行后续章节，而不是推倒重来

---

## 6. 最终判定：这轮 Loom 建设是否有效

满足以下条件，才可判定“有效”：

- [ ] baseline vs loom 已真实对比
- [ ] 卫图样例上 `character_ooc` 呈下降趋势
- [ ] whole-book 报告能看到 Loom gate，而不是只在 operator surface 可见
- [ ] LLM 完成了大多数初筛与评估
- [ ] 人工只处理复杂 case
- [ ] 人工处理后能 resume 回原链路
- [ ] 结果已写回手册 / handoff / changelog

如果只是：

- 能跑
- 有报告
- 有 signals
- 有 heuristic score

但还没有真实 A/B 与人工复核闭环，那么结论只能是：

> **能力已建成，效果待证实。**

---

## 7. 复现时的最低检查清单

- [ ] PostgreSQL 正常
- [ ] LLM provider 正常
- [ ] 卫图样例 branch 可访问
- [ ] baseline / loom 两组产物都存在
- [ ] `loom-ab-compare` 已运行
- [ ] `loom-pairs-stats` 已运行
- [ ] 复杂 case 已进入 manual_eval 工作区
- [ ] resume / recovery 路径已记录

---

## 8. 对应文档索引

- [SOTA 仿写能力推进 Checklist](./sota-imitation-progression-checklist.md)
- [Loom 开发交接文档](./handoff.md)
- [CLI 操作手册](../cli-operations-manual.md)
- [人工评估工作区模板](../../runs/manual_eval/_template/README.md)
- [使用指南](../direct-usage-guide.md)
