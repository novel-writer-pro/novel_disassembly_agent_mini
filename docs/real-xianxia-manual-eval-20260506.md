# Real Xianxia Manual Eval — 2026-05-06

## 样例
- 来源：仓库本地缓存 `./.cache/novel-analyzer/uploads/c495a0a263b947058a19dad743dab8a1-novel.txt`
- 类型：中文修仙 / 男频向开篇样例
- 评估工作区：`runs/manual_eval/real-xianxia-sample-20260506/`

## 核心结论
1. **真实原文直导入失败**
   - 原文使用 `第一节/第二节/第三节` 标题。
   - `inspect-novel` 结果：`raw_heading_count=0`、`normalized_chapter_count=0`。
   - `ingest` 结果：`chapter_count=0`。
   - 这说明当前切章器对真实中文网文常见“节级标题”兼容不足。

2. **最小归一化后主链跑通**
   - 只做标题最小归一化：`第一节 -> 第1章`。
   - 归一化后：`raw_heading_count=3`、`normalized_chapter_count=3`。
   - 分支：`branch_id=86ce179e-475a-42b9-ade3-a81a8626dc5f`
   - 运行：`run_id=b0fb667b-ce1e-47a0-8346-92e3dbc6d3bc`
   - 前 3 章全部完成：`completed_chapters=3`、`failed_jobs=0`。

3. **真实运行暴露出结构化 intake 兼容问题，但 fallback 有效**
   - 第 2 章 `small_model_pipeline` 报 schema 校验错误：
     - `normalized_title` 缺失
     - `dialogue_candidates` 返回对象而非字符串
   - 系统自动切到 `monolithic_fallback`，并成功完成 chapter 2。
   - 说明 fallback 链具备实战价值，但小模型结构化 contract 仍需修正。

## 新鲜证据
### Branch status
- `manifest_chapter_count=3`
- `completed_chapters=3`
- `fact_count=37`
- `graph_node_count=48`
- `graph_edge_count=256`

### Hook / review
- chapter 1: `hook=4.5`
- chapter 2: `hook=4.0`
- chapter 3: `hook=4.0`, `review=True`

### 已成功导出
- `runs/manual_eval/real-xianxia-sample-20260506/exports/branch-report.md`
- `runs/manual_eval/real-xianxia-sample-20260506/artifacts/author-knowledge.json`
- `runs/manual_eval/real-xianxia-sample-20260506/notes/chapter1.bundle.txt`
- `runs/manual_eval/real-xianxia-sample-20260506/notes/chapter2.bundle.txt`
- `runs/manual_eval/real-xianxia-sample-20260506/notes/stage-summary.md`
- `runs/manual_eval/real-xianxia-sample-20260506/notes/problem-trace.md`

### 内容质量早期判断
- 第 1 章：世界观 / 伏笔抽取较强，但 summary 略泛。
- 第 2 章：人物互动、情绪曲线、关系刻画提炼较好。
- branch report 已能给出低风险 review candidate，而不是只给空白通过结果。

## 本轮发现的问题
### P1. 原文节级标题不兼容
- 影响：真实中文小说直导入失败。
- 优先级：P1
- 建议：扩展 heading parser，支持 `第X节`、卷-节混排、站点常见节标题模式。

### P2. 小模型 chapter intake schema 不兼容
- 影响：第 2 章结构化 intake 失败，依赖 fallback 收口。
- 优先级：P1
- 建议：
  1. 放宽 `dialogue_candidates` schema，兼容对象列表；或
  2. 在 parser 层统一把对象投影为字符串/标准结构。

### P3. 部分 operator-facing 导出偏慢
- 现象：本轮 `export-governance-dashboard`、`export-search-branch-diagnostics`、`export-novel-assistant` 未在 40 秒内稳定完成。
- 优先级：P2
- 建议：单独排查导出链的慢点/阻塞点，必要时增加 lighter-weight partial mode。

## 当前判断
- **可证明主链能处理真实中文修仙文本内容本身**，前提是标题格式被识别。
- **离产品化还差两类补强**：
  1. ingest 对真实网文章节格式的兼容；
  2. 小模型结构化输出与 operator-facing 导出稳定性。

## 推荐下一步
1. 先修 `第X节` 标题兼容，再复跑同一原文，验证“无需归一化副本”也能直跑。
2. 修 chapter intake 的 `dialogue_candidates` schema 兼容，再对第 2 章复测，确认不再依赖 fallback。
3. 单独排查 `export-novel-assistant` / governance / diagnostics 的超时问题，补一轮 retrieval 与 QA 的可落盘证据。
