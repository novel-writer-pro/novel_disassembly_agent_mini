# Release / Handoff Brief

这是一份面向“上线前内部交接 / 后续接手者”的简版说明。

---

## 1. 这是什么

这是一个 **小说拆书 agent 后端**。

核心职责：
1. 按章节推进拆书
2. 沉淀 facts / retrieval / reasoning graph
3. 输出 state summary / QA context / thematic contexts
4. 提供给写作者工具、问答工具、前端工作台、下游 agent 消费

它不是写作 agent，不负责代写正文。

---

## 2. 当前已经稳定的输出面

### 2.1 章节级
1. chapter bundle
2. chapter markdown
3. chapter QA context

### 2.2 分支级
1. branch bundle
2. branch report
3. branch QA context
4. branch package

### 2.3 主题级
1. character arc
2. conflict arc
3. foreshadow arc
4. world rule arc

---

## 3. 你应该先看哪几份文档

### 3.1 使用者
1. [`./cli-operations-manual.md`](./cli-operations-manual.md)
2. [`./direct-usage-guide.md`](./direct-usage-guide.md)

### 3.2 接入者（前端 / 工具 / 下游 agent）
1. [`./interface-manifest.md`](./interface-manifest.md)
2. [`./examples/`](./examples/)
3. [`./final-handoff.md`](./final-handoff.md)

### 3.3 开发者 / 维护者
1. [`./final-handoff.md`](./final-handoff.md)
2. [`./interface-manifest.md`](./interface-manifest.md)
3. [`./agent-skills-and-embedding.md`](./agent-skills-and-embedding.md)

---

## 4. 最常用命令

1. `init-db`
2. `ingest`
3. `start-run`
4. `analyze-next`
5. `show-run-status`
6. `export-branch-report`
7. `export-branch-package`
8. `ask-branch`
9. `export-branch-qa-context`

---

## 5. 关键交付物

### 5.1 给使用者 / 写作者参考
1. `branch_report.md`
2. `chapter_XXXX.md`
3. `chapter_XXXX.qa-context.json`

### 5.2 给接入者 / 前端 / 工作台
1. `branch_bundle.json`
2. `branch_qa_context.json`
3. `thematic_contexts`

### 5.3 给开发者 / 下游 agent
1. `branch_qa_context.json`
2. `chapter_output_summary`
3. `reasoning_graph`
4. `state_summary`

---

## 6. 已知风险

1. 外部 LLM relay 稳定性仍可能波动
2. 小模型虽然已被 prompt + guard 强化，但关键章节仍建议抽查
3. 示例数据较简时，某些 thematic context 字段会偏稀疏
4. 当前是 typed contract + manifest docs，不是正式 JSON Schema 导出

---

## 7. 当前结论

项目已达到：
1. 可运行
2. 可恢复
3. 可回退
4. 可问答
5. 可导出
6. 可专题导航
7. 可做图谱 / 时间线前端输入
8. 可交接

当前状态适合作为“阶段性交付版本”。
