# 卫图样例验证日志（2026-05-11）

> 本日志记录的是**已经实际执行过的验证证据**，不是规划。

---

## 1. 当前选定的真实验证目标

### Canonical branch

- `branch_id`: `62e636f0-c901-4167-aa1c-aff3da9c83ef`
- `title`: `示例小说-fresh10-db-v2`

### 为什么它可以作为卫图样例验证目标

该分支的真实章节摘要已明确包含：

- 卫图
- 命格
- 养生功
- 龟息养气功

### 章节摘要（摘录）

| chapter | 摘要 |
|---|---|
| 1 | 卫图夜起喂马，眉心金光闪烁，准备去找二姑 |
| 2 | 卫图前往黄宅求见二姑卫荭，打听养生功线索 |
| 3 | 卫图请得养生功图册，开始学习《龟息养气功》 |
| 4 | 卫图持续苦练《龟息养气功》并初见成效 |
| 5 | 婚后继续规划未来，卫图重新投入养生功修炼 |

---

## 2. 已实际执行的 Loom 运行证据

## 2.1 loom-status

执行命令：

```bash
python3 -m novel_analyzer.cli.app loom-status 62e636f0-c901-4167-aa1c-aff3da9c83ef
```

结果摘要：

- `total_facts: 611`
- `active_facts: 611`
- `total_graph_nodes: 768`
- `contradiction_nodes: 0`
- `evolution_nodes: 0`
- `loom_memory_mode: shadow`
- `loom_tension_enabled: True`
- `loom_pairwise_enabled: False`
- `loom_style_enabled: False`
- `loom_character_enabled: False`

### 结论

这证明：

- Loom memory / tension 已接入这个真实卫图分支
- 但该分支目前仍是 **shadow** 模式
- Pairwise / Style / Character 这些更高阶验证能力还没在此分支上真正打开

---

## 2.2 loom-status 的张力输出

同一次 `loom-status` 输出显示：

- `chapter 45`
- `tension_score: 0.5875`
- `plot_similarity: 0.0000`
- `conflict_density: 0.0000`
- `surprise_index: 0.7500`
- alert: `冲突密度 0.00，情节偏平淡`

### 结论

这证明张力指标链已经在真实分支上出结果。

但它只能证明：

> **张力信号可计算**

不能单独证明：

> **Loom 已经让仿写更好**

---

## 2.3 loom-assemble

执行命令：

```bash
python3 -m novel_analyzer.cli.app loom-assemble 62e636f0-c901-4167-aa1c-aff3da9c83ef 6
```

观察到：

- `working_memory.active_characters` 中包含二姑、卫荭、黄老爷、厨娘杏等
- `active_threads` 中包含：
  - 卫图担心养马失误受罚
  - “大器晚成”命格可能晚年显效
  - 卫图计划从二姑处寻找养生功线索

### 结论

这证明：

- Loom 的 carry-over 组装器已经在真实卫图分支上工作
- Working Memory 与 active threads 不是空壳结构

---

## 2.4 loom-consolidate

执行命令：

```bash
python3 -m novel_analyzer.cli.app loom-consolidate 62e636f0-c901-4167-aa1c-aff3da9c83ef 5
```

结果：

- `contradictions: 0`
- `evolutions: 0`
- `ambiguities: 0`
- `human_review: False`

### 结论

这证明：

- 冲突代谢服务可在真实卫图分支上运行
- 当前至少在 chapter 5 上没有触发明显冲突

---

## 2.5 episodic memory 现状

SQL 汇总结果：

- `active_facts: 611`
- `episodic_active: 611`
- `avg_decay: 1.0000`

### 结论

这说明当前卫图分支的 episodic decay 还没有形成明显衰减证据。

可能原因：

- 当前运行模式主要还是 shadow
- consolidate / decay 未在足够长的真实写作闭环里持续发挥

---

## 3. 当前我们能诚实得出的判断

### 已被真实证明的部分

- [x] 卫图样例的真实 PostgreSQL 分支存在
- [x] Loom memory / tension 可在该分支上运行
- [x] Loom carry-over 组装器可产出真实内容
- [x] 冲突代谢服务可运行

### 还没有被真实证明的部分

- [ ] Loom 比 baseline 仿写更好
- [ ] `character_ooc` 确实下降
- [ ] LLM judge 已成为该分支的主评估方式
- [ ] style / character / pairwise 信号已在真实卫图验证中打开
- [ ] 人工 mailbox 介入后完成一次真正 resume 闭环

---

## 4. 当前最大 gap

当前最大 gap 不是“系统没跑起来”，而是：

> **这条卫图分支还没有形成 baseline vs loom 的双臂对照验证。**

尤其是：

- `loom_memory_mode=shadow`
- `loom_pairwise_enabled=False`
- `loom_style_enabled=False`
- `loom_character_enabled=False`

这意味着：

- 现在可以证明 Loom 信号存在
- 但不能证明 Loom 真的提升了仿写质量

---

## 5. 下一步必须做什么

## 5.0 本轮已实际执行的 baseline vs enhanced 对比

### 执行方式

已实际执行：

```bash
python3 scripts/bootstrap_weitu_validation_workspace.py \
  62e636f0-c901-4167-aa1c-aff3da9c83ef \
  weitu-baseline \
  --force

NOVEL_ANALYZER_LOOM_MEMORY_MODE=enabled \
NOVEL_ANALYZER_LOOM_PAIRWISE_ENABLED=true \
NOVEL_ANALYZER_LOOM_STYLE_ENABLED=true \
NOVEL_ANALYZER_LOOM_CHARACTER_ENABLED=true \
python3 scripts/bootstrap_weitu_validation_workspace.py \
  62e636f0-c901-4167-aa1c-aff3da9c83ef \
  weitu-enhanced \
  --force
```

### 观察结果

| 指标 | baseline | enhanced |
|---|---:|---:|
| `quality_verdict` | `quality-pass` | `quality-hold` |
| `gate_status` | `monitoring` | `blocked-on-quality` |
| `average_chapter_quality_score` | `None` | `0.5` |
| `tension_signal_count` | `2` | `2` |
| `style_signal_count` | `0` | `2` |
| `chapter_quality_signal_count` | `0` | `2` |
| `step0_style_populated` | `False` | `True` |
| `step0_quality_populated` | `False` | `True` |
| `step0_character_populated` | `False` | `False` |

### 这次对比能说明什么

这次对比**已经证明**：

- 开启 Loom 增强 flags 后，whole-book report 的可观测输出确实发生变化
- 变化不是空字段，而是：
  - 新出现 `chapter_quality_signal`
  - 新出现 `style_signal`
  - gate 从单纯 `monitoring` 进入 `blocked-on-quality`

### 但它还不能说明什么

这次对比**还不能证明**：

- enhanced 比 baseline 质量更高
- `character_ooc` 确实下降
- character 信号已经在当前卫图链路里稳定发挥作用

原因：

- 当前 enhanced 的 `quality_verdict=quality-hold`
- `average_chapter_quality_score=0.5` 更像“信号被打开后暴露了问题”，而不是“效果已变好”
- `step0_character_populated=False` 说明角色信号在这轮 whole-book 样例上还没有形成有效输出

### 当前最准确结论

> 这轮对比已经证明 **Loom enhanced 会真实改变执行器侧产物与 gate 结论**，
> 但还没有证明 **它已经提升卫图样例仿写效果**。

---

## 5.1 本轮已实际执行的 writer-imitate 对比

### 执行方式

已实际执行：

```bash
python3 -m novel_analyzer.cli.app writer-imitate \
  62e636f0-c901-4167-aa1c-aff3da9c83ef 2 "延续卫图求养生功线索" \
  --output-dir runs/manual_eval/weitu-baseline/artifacts/writer-output

python3 -m novel_analyzer.cli.app writer-imitate \
  62e636f0-c901-4167-aa1c-aff3da9c83ef 3 "延续卫图得法与初练" \
  --output-dir runs/manual_eval/weitu-baseline/artifacts/writer-output

NOVEL_ANALYZER_LOOM_MEMORY_MODE=enabled \
NOVEL_ANALYZER_LOOM_PAIRWISE_ENABLED=true \
NOVEL_ANALYZER_LOOM_STYLE_ENABLED=true \
NOVEL_ANALYZER_LOOM_CHARACTER_ENABLED=true \
python3 -m novel_analyzer.cli.app writer-imitate \
  62e636f0-c901-4167-aa1c-aff3da9c83ef 2 "延续卫图求养生功线索" \
  --output-dir runs/manual_eval/weitu-enhanced/artifacts/writer-output

NOVEL_ANALYZER_LOOM_MEMORY_MODE=enabled \
NOVEL_ANALYZER_LOOM_PAIRWISE_ENABLED=true \
NOVEL_ANALYZER_LOOM_STYLE_ENABLED=true \
NOVEL_ANALYZER_LOOM_CHARACTER_ENABLED=true \
python3 -m novel_analyzer.cli.app writer-imitate \
  62e636f0-c901-4167-aa1c-aff3da9c83ef 3 "延续卫图得法与初练" \
  --output-dir runs/manual_eval/weitu-enhanced/artifacts/writer-output
```

### 产物差异（chapter 2 抽样）

- baseline `writer-imitate-ch2.json`
  - 有 `_loom_tension`
  - `chapter_quality_signal={}`
  - `dialogue_signal={}`
- enhanced `writer-imitate-ch2.json`
  - 有 `_loom_tension`
  - 有 `_loom_style`
  - `chapter_quality_signal` 已填充
  - `dialogue_signal={}` 仍为空

### pairwise 采集

已实际执行：

```bash
python3 -m novel_analyzer.cli.app loom-collect-pairs \
  --output-dir /home/user/ai-books/runs/manual_eval/weitu-baseline/artifacts/writer-output \
  --compare-dir /home/user/ai-books/runs/manual_eval/weitu-enhanced/artifacts/writer-output \
  --pairs-file /home/user/ai-books/runs/manual_eval/weitu-compare-pairs.jsonl
```

结果：

- `total_pairs=2`
- `pair_source=cross_dir`

### pairwise 统计

已实际执行：

```bash
python3 -m novel_analyzer.cli.app loom-pairs-stats \
  --pairs-file /home/user/ai-books/runs/manual_eval/weitu-compare-pairs.jsonl
```

结果：

- `total_pairs=2`
- `avg_quality_score=0.5`
- `evaluation_method=heuristic: 2`
- `overall_preference=tie: 2`

### A/B compare

已实际执行：

```bash
python3 -m novel_analyzer.cli.app loom-ab-compare \
  /home/user/ai-books/runs/manual_eval/weitu-baseline/artifacts/writer-output \
  /home/user/ai-books/runs/manual_eval/weitu-enhanced/artifacts/writer-output \
  --output-file /home/user/ai-books/runs/manual_eval/weitu-ab-report.json
```

结果：

- `total_chapters=2`
- `baseline_ooc_count=0`
- `loom_ooc_count=0`
- `ooc_reduction_pct=0.0`
- `target_met=False`
- `baseline_verdict_distribution: needs_revision=2`
- `loom_verdict_distribution: needs_revision=2`

### 这轮 writer-imitate 对比的结论

这次已经证明：

- enhanced 路径确实会让单章 writer-imitate 产物增加 Loom 质量/风格信号
- pairwise / A-B 工具链已经在卫图样例上真正跑通

但这次还没有证明：

- enhanced 比 baseline 更优
- `character_ooc` 有下降
- LLM judge 已经成为主评估方式（当前仍是 `heuristic`）

### 5.2 LLM prose 抽样对读（chapter 2）

#### 已实际执行

```bash
python3 -m novel_analyzer.cli.app writer-imitate \
  62e636f0-c901-4167-aa1c-aff3da9c83ef 2 "延续卫图求养生功线索" \
  --use-llm \
  --output-dir /home/user/ai-books/runs/manual_eval/weitu-llm-baseline/artifacts/writer-output

NOVEL_ANALYZER_LOOM_MEMORY_MODE=enabled \
NOVEL_ANALYZER_LOOM_PAIRWISE_ENABLED=true \
NOVEL_ANALYZER_LOOM_STYLE_ENABLED=true \
NOVEL_ANALYZER_LOOM_CHARACTER_ENABLED=true \
python3 -m novel_analyzer.cli.app writer-imitate \
  62e636f0-c901-4167-aa1c-aff3da9c83ef 2 "延续卫图求养生功线索" \
  --use-llm \
  --output-dir /home/user/ai-books/runs/manual_eval/weitu-llm-enhanced/artifacts/writer-output
```

#### 人工对读结论

- baseline 版本：
  - 围绕“大少爷带回抄本、卫图求二姑打听、二姑给出两种代价”展开
  - 阻力清晰，交易条件明确，更像“主线推进 + 做选择”
- enhanced 版本：
  - 围绕“杏先泄露消息、卫图备礼、二姑给出城南瘸腿道士线索”展开
  - 细节更生活化，场景更顺，但也更像新增支线线索

#### 当前人工判断

这两版都比启发式结构草案更像真正正文，但从 chapter 2 单章看：

- **baseline 更像主线压强版**
- **enhanced 更像细节润色版**

因此当前还不能仅凭这轮 LLM prose 抽样，就宣布 enhanced 更优。

### 5.3 LLM prose 抽样对读（chapter 3）

#### 已实际执行

```bash
python3 -m novel_analyzer.cli.app writer-imitate \
  62e636f0-c901-4167-aa1c-aff3da9c83ef 3 "延续卫图得法与初练" \
  --use-llm \
  --output-dir /home/user/ai-books/runs/manual_eval/weitu-llm-baseline/artifacts/writer-output

NOVEL_ANALYZER_LOOM_MEMORY_MODE=enabled \
NOVEL_ANALYZER_LOOM_PAIRWISE_ENABLED=true \
NOVEL_ANALYZER_LOOM_STYLE_ENABLED=true \
NOVEL_ANALYZER_LOOM_CHARACTER_ENABLED=true \
python3 -m novel_analyzer.cli.app writer-imitate \
  62e636f0-c901-4167-aa1c-aff3da9c83ef 3 "延续卫图得法与初练" \
  --use-llm \
  --output-dir /home/user/ai-books/runs/manual_eval/weitu-llm-enhanced/artifacts/writer-output
```

#### 人工对读结论

- baseline 版本：
  - 通过“账房赵伯借册子”的方式让卫图获得《调息舒筋法》
  - 路径更朴素、更下层生活化，但也偏离了前文已出现的二姑/黄宅线索
- enhanced 版本：
  - 直接承接二姑卫荭与阮武师，把《龟息养气功》图册作为主线结果落下来
  - 与前面卫图求二姑、求养生功的方向更连续，章节标题也更贴近“初练龟息”这一收束

#### 当前人工判断

从 chapter 3 单章看：

- **enhanced 更像 continuity 对齐版**
- **baseline 更像另起一条可行支线**

### 5.4 chapter 2 + 3 合并判断

当前人工对读的合并结论是：

- chapter 2：baseline 更强
- chapter 3：enhanced 更强

因此到目前为止：

> **两边各有优点，还没有形成 enhanced 稳定胜出的证据。**

这也与当前自动评估结果一致：

- pairwise: `tie`
- A/B compare: `ooc_reduction_pct=0.0`

最准确的阶段性判断仍然是：

> Loom enhanced 已经让单章产物出现更多质量/风格信号，
> 但在卫图样例的当前抽样里，还没有形成稳定优于 baseline 的正文证据。

### 5.5 chapter 4 + 5 扩样人工判断

#### chapter 4

- baseline：
  - 主线围绕“赎身银 / 去府城采买药材 / 护镖或应征机会”展开
  - 压力更现实，代价也更硬
- enhanced：
  - 主线围绕“看青三年换赎身机会”展开
  - 情绪和家庭细节更稳，但时间跨度与赎身数额拉得更大，主线推进速度更慢

#### chapter 5

- baseline：
  - 婚后筹谋聚焦在“月例下降、去府城办差、立军令状、拿赏钱换赎身”
  - 冲突更集中，章尾钩子更强
- enhanced：
  - 婚后筹划聚焦在“看青三年、慢慢攒赎身钱、边务农边练功”
  - 日常感和夫妻协作更顺，但整体更像中期铺陈，不像强推进章节

### 5.6 chapter 2–5 合并趋势

当前 4 章人工对读后，趋势大致是：

- chapter 2：baseline 更强
- chapter 3：enhanced 更强
- chapter 4：baseline 略强
- chapter 5：baseline 更强

### 5.7 当前最接近真实的结论

在当前卫图样例的 2–5 章 LLM prose 抽样中：

- **baseline 更偏“主线压强 / 现实交易 / 推进更硬”**
- **enhanced 更偏“细节润色 / 生活感 / 连续性更柔和”**

因此当前并没有出现 “enhanced 稳定胜出” 的趋势。

这与自动评估结果仍然一致：

- 4 章 pairwise：`A=1, tie=3`
- `avg_quality_score=0.4875`
- `evaluation_method=heuristic`
- `character_ooc`: `0 → 0`

所以当前阶段性判断应更新为：

> **Loom enhanced 已经稳定改变了信号层和部分文本风格，但在卫图样例 2–5 章抽样里，正文效果暂时仍是 baseline 略占优或至少未被反超。**

### P0

1. 为卫图样例建立 **baseline** 产物
2. 为卫图样例建立 **loom** 产物（至少 `ab` 或 `enabled`）
3. 运行：

```bash
python3 -m novel_analyzer.cli.app loom-ab-compare <baseline_dir> <loom_dir>
python3 -m novel_analyzer.cli.app loom-pairs-stats <pairs_file>
```

### P1

4. 把复杂章节导入 `runs/manual_eval/weitu-sample/`
5. 人工完成后验证 resume / recovery

---

## 6. 关联文档

- [卫图样例真实效果验证工作流](./weitu-real-effect-validation.md)
- [SOTA 仿写能力推进 Checklist](./sota-imitation-progression-checklist.md)
- [Loom 开发交接文档](./handoff.md)
