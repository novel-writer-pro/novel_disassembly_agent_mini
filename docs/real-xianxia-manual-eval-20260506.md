# Real Xianxia Manual Eval — 2026-05-06

## 样例
- 来源：仓库本地缓存 `./.cache/novel-analyzer/uploads/c495a0a263b947058a19dad743dab8a1-novel.txt`
- 类型：中文修仙 / 男频向开篇样例
- 评估工作区：`runs/manual_eval/real-xianxia-sample-20260506/`

## 核心结论
1. **真实原文节级标题兼容已补齐**
   - 原文使用 `第一节/第二节/第三节` 标题。
   - 本轮修复后，`inspect-novel` 结果：`raw_heading_count=5`、`normalized_chapter_count=5`。
   - `ingest` 结果：`chapter_count=5`。
   - 说明当前切章器已能直接识别真实中文网文常见的“节级标题”。

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
  1. 小模型结构化输出与 operator-facing 导出稳定性。
  2. chapter list / file import 两条导入路径的长期产品化维护。

## 推荐下一步
1. 先修 `第X节` 标题兼容，再复跑同一原文，验证“无需归一化副本”也能直跑。
2. 修 chapter intake 的 `dialogue_candidates` schema 兼容，再对第 2 章复测，确认不再依赖 fallback。
3. 单独排查 `export-novel-assistant` / governance / diagnostics 的超时问题，补一轮 retrieval 与 QA 的可落盘证据。

## 补充验证（当日修复后）
- 使用原始未归一化真实文本重新执行：
  - `inspect-novel .cache/novel-analyzer/uploads/c495a0a263b947058a19dad743dab8a1-novel.txt`
  - fresh evidence：`raw_heading_count=5`、`normalized_chapter_count=5`
- 再执行：
  - `ingest ... --title 真实中文修仙样例-青华-原文直跑复测`
  - fresh evidence：`chapter_count=5`
- 说明本轮切章修复已经覆盖真实原文，不再需要手动把 `第一节` 改成 `第1章` 才能导入。

## 补充验证（5节短复跑完成后）
- 原始未归一化 5 节真实修仙文本短复跑分支：`run_id=51499b32-cdd0-475f-bbc7-2ac27ea0f529`。
- fresh evidence：`completed_chapters=5`、`failed_jobs=0`、`graph_node_count=64`、`graph_edge_count=524`。
- chapter 2 未再出现 `dialogue_candidates` schema fail。
- chapter 3 未再出现 `normalized_title` 缺失导致的 `small_model_pipeline` fail，也未进入 `monolithic_fallback`。
- chapter 4 / 5 同样完成 `validated`，说明这两类兼容修复已经在整条 5 节原始文本上取得运行面证据。
- 对应效果评估见：`runs/manual_eval/real-xianxia-raw-short-rerun-20260506/notes/final-effect-evaluation.md`。

## 导出慢点边界（补充诊断）
- 对完成分支做 stepwise profiling 后，`status_service.get_run_status`、`export_branch_bundle`、`author.build_branch_knowledge_pack` 都在 0.2s 以内完成。
- profiling 在进入首个 `retrieval.search_branch_with_diagnostics(...)` 后卡住，说明当前 operator-facing 慢点更靠近 retrieval diagnostics / benchmark 链，而不是 branch report 或 author knowledge 生成。

## 导出慢点优化结果
- 在完成分支上补入 provider cache 与 rerank 本地缓存优先策略后，`export-retrieval-benchmark`、两条 `export-search-branch-diagnostics`、`export-governance-dashboard`、`export-novel-assistant` 已成功导出。
- 新结论：operator-facing 导出问题已从“经常超时/不可用”改善为“可用，但 retrieval diagnostics / benchmark 链仍是相对较重的路径”。

## Reader feedback / whole-book readiness 补充证据
- 在完成分支 `23685de0-a53e-4229-a946-14d53d5b026d` 上已成功导入 3 条 reader feedback，并导出 `reader-feedback-summary.json`。
- feedback summary 已给出 `signals` 与 `revision_recommendations`，说明 reader feedback 闭环在真实样例上可用。
- `show-whole-book-imitation-readiness` 已成功返回 readiness contract，当前分支 `chapter_analysis_count=5`、`fact_record_count=51`，但 provider health 为 `degraded`，说明 whole-book 前还需确认上游 provider 恢复。

## Route-level profiling（补充诊断）
- 在完成分支上对 retrieval route 逐项计时后，已确认：
  - `fts/similarity/like/keyword/entity_exact` 都在毫秒级或接近毫秒级；
  - `vector route` 约 2.5s；
  - `rerank` 约 6.3s。
- 新结论：retrieval diagnostics 链的主要性能瓶颈已进一步收缩到 `rerank` 与 `vector route`，而不是 SQL route 本身。

## Candidate cap 验证结论
- 新增 rerank candidate cap 后，在当前 5 节完成分支上再次 route profiling。
- fresh evidence：`raw_search` 仅返回 5 个候选，因此 rerank 仍对 5 个候选执行，耗时约 6.7s。
- 结论：candidate cap 对更大 branch 有保护价值，但对该短样例分支的主要慢点改善有限，下一步应直接优化 rerank 本体。
