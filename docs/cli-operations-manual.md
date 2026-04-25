# CLI Standard Workflow Manual

本手册面向实际操作，描述从导入小说到导出拆书结果、问答上下文、专题导航的标准 CLI 路径。

---

## 1. 初始化环境

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

## 2. 导入小说并创建分支

### 2.1 导入文本
```bash
poetry run novel-analyzer ingest /path/to/novel.txt --title '样例小说'
```

记录输出：
- `novel_id`
- `manifest_id`
- `chapter_count`

### 2.2 创建 run / branch
```bash
poetry run novel-analyzer start-run <novel_id> <manifest_id>
```

记录输出：
- `run_id`
- `branch_id`

---

## 3. 标准拆书推进路径

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

## 4. 运行状态与审计

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

---

## 5. 图谱、状态机与专题导航

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

## 6. 小说问答与 QA Context

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

## 7. Package 导出标准路径

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

---

## 8. 恢复、修复与回退

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
