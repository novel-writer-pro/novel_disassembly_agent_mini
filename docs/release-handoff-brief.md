# Release / Handoff Brief

这是一份面向“上线前内部交接 / 后续接手者”的简版说明。

---

## 0. 当前 release 定位

当前可视为一个 **基础可用 release**，重点不是把所有高级能力都做满，而是先保证下面这些能力已经可以稳定串起来：

1. 导入小说
2. 基于 PostgreSQL 按章节持续拆书
3. 在工作台查看章节拆书详情
4. 回看原始章节正文
5. 基于整本小说做检索与问答
6. 在问答结果中保留可跳转的章节引用
7. 在失败时进行自动重试与人工恢复
8. 导出分支级结果

这意味着它已经满足“先投入内部使用 / 继续小步迭代”的标准。

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
3. [`./eval-governance-sample-release-contract.md`](./eval-governance-sample-release-contract.md)
4. [`./examples/eval-governance-cross-lane-bundle.sample.json`](./examples/eval-governance-cross-lane-bundle.sample.json)
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

---

## 9. 当前 release 验收口径

如果只按“基础功能是否可交付”来判断，当前 release 至少应满足：

### 9.1 后端 / 数据链路
- PostgreSQL-only 运行时可用
- 章节拆书结果可写入数据库
- branch snapshot / chapter bundle / chapter source 可读
- 检索与问答接口可返回结果

### 9.2 工作台
- `/library` 可作为多本小说的统一管理入口
- `/control` 可导入 / 继续整理 / 查看进度
- `/reader` 可查看章节拆书内容与原文
- `/qa` 可进行聊天式问答、查看证据、跳转章节
- `/ops` 可执行恢复与导出

### 9.3 交付物
- 文档已覆盖开发、部署、工作台、恢复、问答
- CHANGELOG 持续记录
- Git 提交历史可追踪

这版之后的优化原则：
- 先做“可用性与体验打磨”
- 不轻易扩大范围
- 不破坏现有基础流程

### 建议的下一步优化顺序
1. 多小说上下文继续收紧
2. pipeline 当前 run 聚焦模式
3. pipeline / ops 恢复联动继续完善
4. 章节任务排序与错误摘要
5. SSE 与更深层 scheduler/worker 重构放后

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


## 10. Eval / governance freeze gate

Before a release handoff claims freeze readiness, run the cross-lane sample bundle through `EvalGovernanceService.evaluate_sample_bundle()`. The handoff must include `bundle_id`, stable contract versions, `sample_count_by_lane`, lane summaries, release blockers, and `freeze_policy.may_freeze`. If `may_freeze=false`, the release remains blocked even when individual lane docs look complete.
