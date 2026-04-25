# Release / Handoff Brief

这是一份面向“上线前内部交接 / 后续接手者”的简版说明。

---

## 1. 这是什么

这是一个 **小说拆书 agent 后端**，核心职责是：
- 按章节推进拆书
- 沉淀 facts / retrieval / reasoning graph
- 输出 state summary / QA context / thematic contexts
- 提供给写作者工具、问答工具、前端工作台、下游 agent 消费

它不是写作 agent，不负责代写正文。

---

## 2. 当前已经稳定的输出面

### 章节级
- chapter bundle
- chapter markdown
- chapter QA context

### 分支级
- branch bundle
- branch report
- branch QA context
- branch package

### 主题级
- character arc
- conflict arc
- foreshadow arc
- world rule arc

---

## 3. 你应该先看哪几份文档

### 如果你要直接操作
1. `docs/cli-operations-manual.md`
2. `docs/direct-usage-guide.md`

### 如果你要接前端 / 工具 / 其他 agent
1. `docs/interface-manifest.md`
2. `docs/examples/*.sample.json`
3. `docs/final-handoff.md`

### 如果你是接手维护者
1. `docs/final-handoff.md`
2. `docs/interface-manifest.md`
3. `docs/agent-skills-and-embedding.md`

---

## 4. 最常用命令

```bash
poetry run novel-analyzer init-db
poetry run novel-analyzer ingest /path/to/novel.txt --title '样例'
poetry run novel-analyzer start-run <novel_id> <manifest_id>
poetry run novel-analyzer analyze-next <run_id> <branch_id>
poetry run novel-analyzer show-run-status <run_id> <branch_id>
poetry run novel-analyzer export-branch-report <run_id> <branch_id> ./branch.md
poetry run novel-analyzer export-branch-package <run_id> <branch_id> ./branch_pkg
poetry run novel-analyzer ask-branch <branch_id> '命格线如何推进？'
poetry run novel-analyzer export-branch-qa-context <run_id> <branch_id> ./branch-qa.json
```

---

## 5. 关键交付物

### 给写作者参考
- `branch_report.md`
- `chapter_XXXX.md`
- `chapter_XXXX.qa-context.json`

### 给前端/工作台
- `branch_bundle.json`
- `branch_qa_context.json`
- `thematic_contexts`

### 给下游 agent
- `branch_qa_context.json`
- `chapter_output_summary`
- `reasoning_graph`
- `state_summary`

---

## 6. 已知风险

- 外部 LLM relay 稳定性仍可能波动
- 小模型虽然已被 prompt + guard 强化，但关键章节仍建议抽查
- 示例数据较简时，某些 thematic context 字段会偏稀疏
- 当前是 typed contract + manifest docs，不是正式 JSON Schema 导出

---

## 7. 当前结论

项目已达到：
- 可运行
- 可恢复
- 可回退
- 可问答
- 可导出
- 可专题导航
- 可做图谱 / 时间线前端输入
- 可交接

当前状态适合作为“阶段性交付版本”。
