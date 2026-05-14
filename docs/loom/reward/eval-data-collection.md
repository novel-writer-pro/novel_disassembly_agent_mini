# 评估数据收集规范 / Eval Data Collection

---

## 1. 现有数据来源盘点

| 数据来源 | DB 表 | 可提取内容 | 质量 | CLI 命令 |
|---------|------|----------|------|---------|
| 人工评审工作区 | `runs/manual_eval/`（文件） | writer-imitate round-0 vs final | 高（人工标注产物） | `loom-collect-pairs-from-manual` |
| Harness 迭代产物 | `output/writer-imitate-ch*.json` | 同章节多个草案版本 | 高（天然 pairwise） | `loom-collect-pairs` |
| DB 分支对比 | `chapter_artifacts` | 两个分支的 chapter_summary | 中（自动提取） | `loom-collect-pairs-from-db` |
| 读者反馈 | `reader_feedback_comments` | 情感倾向、具体评论 | 中（半结构化） | 待实现 |
| 人工 review 结论 | `cluster_review_records` | 问题簇的处理结论 | 高（人工决策） | 待实现 |

---

## 2. CLI 命令速查

```bash
# 从 manual_eval 工作区提取（推荐首选）
novel-analyzer loom-collect-pairs-from-manual \
  --manual-eval-dir runs/manual_eval/ \
  --pairs-file output/loom-pairs.jsonl

# 从 writer-imitate 产物提取（单目录 round-0 vs final）
novel-analyzer loom-collect-pairs \
  --output-dir output/ \
  --pairs-file output/loom-pairs.jsonl

# 从 writer-imitate 产物提取（跨目录 baseline vs steering）
novel-analyzer loom-collect-pairs \
  --output-dir output/baseline/ \
  --compare-dir output/steering/ \
  --pairs-file output/loom-pairs.jsonl

# 从 DB 分支提取
novel-analyzer loom-collect-pairs-from-db <branch_a_id> <branch_b_id> \
  --pairs-file output/loom-pairs.jsonl

# 查看采集进度
novel-analyzer loom-pairs-stats --pairs-file output/loom-pairs.jsonl
```

---

## 3. Pairwise 数据提取规范

### 3.1 从 Harness 迭代提取（最高质量）

Harness 在修复循环中会产生同一章节的多个草案版本，这是天然的 pairwise 数据：

- 同一 `branch_id + chapter_index` 的多个草案版本
- 取 round-0（初稿）作为 draft_a，final_draft 作为 draft_b
- `pair_source=single_dir_rounds`，`evaluation_method=heuristic`（无 LLM 时）

### 3.2 从人工评审工作区提取

`runs/manual_eval/<workspace>/artifacts/writer-imitate-ch*.json` 中的产物与 harness 产物格式相同，`loom-collect-pairs-from-manual` 自动扫描所有工作区（跳过 `_template`）。

- `pair_source=manual_eval_workspace`
- `workspace` 字段记录来源工作区名称

### 3.3 数据质量过滤规则

- 两个草案长度均 ≥ `--min-draft-length`（默认 50 字符）
- 两个草案内容不完全相同
- `evaluation_method=heuristic` 时无需 LLM，`--use-llm` 时调用配置的 LLM provider

---

## 4. 数据积累目标

| 阶段 | 目标数量 | 预计时间 | 用途 |
|------|---------|---------|------|
| 阶段 1 启动 | 50+ pairs | 立即（从现有数据提取） | LLM-as-judge few-shot |
| 阶段 2 准备 | 500+ pairs | 3-6 个月 | Fine-tuning reward model |
| 阶段 3 准备 | 2000+ pairs（多维度标注） | 6-12 个月 | 多维度 reward model |

---

## 5. 与 0509 Consumer Migration Telemetry 的对接

0509 的 **Consumer Migration Telemetry** 需要知道"哪些消费者已迁到 primary"。

Loom 的评估数据收集可以同时记录"哪个评估路径被使用"：

```json
{
  "pair_id": "...",
  "evaluation_path": "loom_pairwise | legacy_checker | human",
  "consumer": "harness | whole_book | manual_review",
  "migrated_to_primary": true
}
```

这个字段可以直接作为 0509 Consumer Migration Telemetry 的数据来源。

---

返回 [Reward 层入口](./README.md) | [Pairwise 评估设计](./pairwise-eval-design.md)
