# Final Effect Evaluation — Raw Xianxia Short Rerun

## Branch
- run_id: `51499b32-cdd0-475f-bbc7-2ac27ea0f529`
- branch_id: `23685de0-a53e-4229-a946-14d53d5b026d`

## Final completion evidence
- `manifest_chapter_count=5`
- `completed_chapters=5`
- `failed_jobs=0`
- `running_jobs=0`
- `fact_count=51`
- `window_count=1`
- `graph_node_count=64`
- `graph_edge_count=524`

## Key compatibility conclusions
1. 原始真实中文修仙文本使用 `第一节/第二节/...` 标题时，已可直接 `inspect + ingest`。
2. chapter 2 不再出现 `dialogue_candidates` 对象导致的 `small_model_pipeline` schema fail。
3. chapter 3 不再出现 `normalized_title` 缺失导致的 `small_model_pipeline` schema fail。
4. chapter 4 / 5 也未观察到 fallback 迹象，整条 5 节原始文本主链完整跑通。

## Content-effect summary
- chapter 1 hook=`4.5`
- chapter 2 hook=`4.0`
- chapter 3 hook=`4.0`
- chapter 4 hook=`4.0`, review=`True`
- chapter 5 hook=`4.0`

## Author knowledge evidence
- `chapter_span = {'min': 1, 'max': 5, 'count': 5}`
- `entity_count = 10`
- `relationship_watch = ['小六子和青旒是同门师兄妹']`
- `unresolved_threads = []`

## Effect scores
- 导入兼容性：**5/5**
- 小模型结构化稳定性：**4.5/5**
- 拆书主链稳定性：**5/5**
- 风险/复核链接入度：**4/5**
- author-facing 知识组织：**4/5**
- retrieval/operator 导出稳定性：**3/5**
- 当前商业化中台 readiness：**4/5**

## Why not 5/5 yet
1. retrieval benchmark / diagnostics / novel-assistant 大包导出在该分支上仍出现超时或偏慢现象；
2. chapter 4 存在一个低风险 review candidate，需要人工复核以确认 precision。

## Final assessment
对于真实中文修仙 / 男频开篇文本，当前系统已经具备：
- 原文直导入能力
- 5 节连续拆书主链稳定跑通能力
- 风险审查与 review candidate 接入能力
- branch report / author knowledge 可导出能力
- graph / facts / hook / state 的中台级沉淀能力

如果目标是“商业化小说中台助手”，当前已经从“概念验证”进入到“可真实跑样例、可发现问题、可持续优化”的阶段。

## Next recommended work
1. 在 20~50 章真实男频修仙文本上继续复测稳定性。
2. 专门排查 retrieval / diagnostics / novel-assistant 导出的慢点。
3. 对 chapter 4 的 review candidate 做人工复核，确认 risk lane precision。
