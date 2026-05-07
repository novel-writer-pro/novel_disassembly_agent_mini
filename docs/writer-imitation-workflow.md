# Writer Imitation Workflow / 小说仿写实战流程

本流程面向真实仿写实战，默认工作目录为：
- `output/`

约束：
- `output/` 只作为工作目录
- 不提交进 Git
- 最终沉淀到仓库的应是：代码、流程文档、评估结论，而不是每次仿写草稿

---

## 1. 当前建议入口

### 1.1 单章仿写
```bash
./.venv/bin/novel-analyzer writer-imitate <branch_id> <source_chapter_index> "<target_goal>" --output-dir output
```

输出：
- `output/writer-imitate-ch<idx>.json`
- `output/writer-imitate-ch<idx>.md`

### 1.2 多章批量仿写
```bash
./.venv/bin/novel-analyzer writer-imitate-range <branch_id> '3:目标A' '4:目标B' --output-dir output
```

输出：
- `output/writer-imitate-range-3-4.json`
- `output/writer-imitate-range-3-4.md`

---

## 2. 推荐实战顺序
1. 先完成拆书 / facts / graph / risk 主链
2. 用 `show-author-knowledge` / `export-author-knowledge` 确认人物、关系、规则、线程
3. 先跑 `writer-imitate` 拿结构化 draft
4. 看 `risk_gate_notes / policy_summary / final_verdict`
5. 如果要连续多章，再跑 `writer-imitate-range`
6. 必要时上：
   - `preflight-imitation`
   - `harness-imitation`
   - `iterate-imitation`
   - `run-whole-book-imitation`

---

## 3. 当前仿写链路包含什么

### 已有能力
- source chapter intake
- fact extraction
- imitation constraint pack
- skeleton / llm draft
- draft self-check
- style calibration
- rhythm analysis
- reader-sim review
- dialogue review
- targeted revise queue
- risk gate notes
- policy summary
- multi-round harness
- whole-book queue / sandbox execute

### 当前 writer-facing 包装层补齐了什么
- 更适合写手直接用的统一入口
- 自动把结果写到 `output/`
- 自动产出 `json + markdown`
- 不需要每次手工拼 CLI 组合

---

## 4. 实战时重点关注字段

### 单章仿写
重点看：
- `final_draft.draft_title`
- `final_draft.draft_text`
- `final_draft.risk_gate_notes`
- `final_verdict`
- `stop_reason`
- `policy_summary`

### 多章仿写
重点看：
- 每章 `final_verdict`
- 每章 `stop_reason`
- 每章 `final_draft`
- 是否出现连续性的 carry-over 问题

---

## 5. 当前最重要的仿写实战原则
1. **先保连续性，再追求表面文风像**
2. **先保人物/规则/线程不崩，再追求“写得像”**
3. **把 risk gate 当硬门，而不是装饰信息**
4. **output 只是工作区，不是最终知识库**
5. **发现真实问题就修流程/代码，不要只改一份草稿了事**

---

## 6. 与你给的 writer-imitate 参考的对齐点
当前我们已经覆盖或接近覆盖：
- 章节窗口化上下文
- story bible / author knowledge 约束注入
- imitation constraint pack
- draft + self-check + revise queue
- 风险门控
- reader-sim / style / rhythm / dialogue repair lanes
- whole-book carry-over 与 consistency

当前仍值得继续补强的点：
- 更明确的 writer-facing continuation notes
- 更直接的“这一章为什么这么写”的编剧式说明
- output 目录下更标准化的批量实验记录
- source / target / repaired draft 的并排对照产物

---

## 7. 推荐下一步实战增强
1. 补一个 `writer-imitate-review` 导出，把 source / draft / risk / verdict 汇总到一份 markdown
2. 补一个 `writer-imitate-session`，把同一轮多章实验的 notes / artifacts 聚合进 output 子目录
3. 对真实仿写章节做一次“边写边修”的长链实验，持续发现问题并优化
