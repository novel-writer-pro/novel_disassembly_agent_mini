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

## 8. 当前原型前端 / 后端状态

### 8.1 后端原型
`apps/api` 已提供一个轻量 WSGI JSON 原型，支持：
- run snapshot
- branch snapshot
- chapter bundle
- chapter QA context
- 原始章节正文片段
- import / start / recovery / export link generation

### 8.2 前端原型
`apps/web` 正在向 Next.js + React + Ant Design 的产品前端迁移，目标支持：
- 真实导入
- 读取真实 run / branch
- 左侧章节导航
- 右侧章节拆书详情
- QA / 推理视图
- 原始正文回看
- `第N章` 引用跳转
- 导出链接生成


### 8.3 当前推荐运行配置
当前真实拆书与工作台建议统一使用：
- provider: `vip1129`
- base_url: `https://api.vip1129.cc/v1`
- model: `gpt-5.4-mini`

### 8.4 当前恢复策略
- 章节失败默认先自动重试
- 自动重试上限为 **5 次**
- 超过 5 次仍失败，才进入人工恢复

### 8.5 当前真实新任务
本轮已按上述配置从第一章重新创建真实任务：
- `run_id=7e22a5d8-eb57-4306-858b-90386f1c2b22`
- `branch_id=72da24e9-e65c-45a9-836d-957c4ae783ec`


### 8.6 工作台问答能力
- 可在阅读页直接检索人物 / 事件 / 冲突 / 关键词
- 可直接发起“人物背景 / 冲突前因后果 / 关系变化”等问答
- 回答会返回引用章节、证据摘要、推理路径和图谱信号
