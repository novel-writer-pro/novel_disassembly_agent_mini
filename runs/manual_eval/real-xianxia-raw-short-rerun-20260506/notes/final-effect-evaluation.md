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
- 风险/复核链接入度：**4.5/5**
- author-facing 知识组织：**4/5**
- retrieval/operator 导出稳定性：**4/5**
- 当前商业化中台 readiness：**4.3/5**

## Why not 5/5 yet
1. retrieval / diagnostics / novel-assistant 导出虽然已恢复可用，但 retrieval diagnostics 链中 `rerank` 与 `vector route` 仍明显偏重；其中 rerank 输入裁剪已带来小幅收益，但未从根本上改变慢点排序；
2. chapter 4 的低风险 review candidate 虽已人工复核为 benign，但还需要更多真实样本确认 risk precision。

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

## Export profiling evidence
- stepwise profiling 结果已落盘到 `notes/export-profile.json`。
- 当前已确认快速完成的步骤：
  - `status_service.get_run_status` ≈ 0.023s
  - `export_service.export_branch_bundle` ≈ 0.191s
  - `author.build_branch_knowledge_pack` ≈ 0.089s
- profiling 在进入首个 `retrieval.search_branch_with_diagnostics(...)` 后长时间无新增结果，说明当前慢点边界已收缩到 retrieval diagnostics / benchmark 链，而不是 branch report / author knowledge / 基础状态读取。

## Export profiling update
- provider cache + rerank 本地缓存优先策略落地后，以下导出在完成分支上已恢复成功：
  - `export-retrieval-benchmark`
  - `export-search-branch-diagnostics`（两条 query）
  - `export-governance-dashboard`
  - `export-novel-assistant`
- 这说明本轮优化已经把“严格超时窗口内大包不可用”的问题，推进成“可用但 retrieval diagnostics 链仍偏重”。


## Reader Feedback Evidence
- comment_count: 3
- signals: ['general_feedback', 'pacing_slow', 'reader_hook_strong']
- revision_recommendations: ['压缩中段铺垫，增强行动推进密度。', '保留章尾钩子并加强下一章期待。']

## Whole-book Readiness Evidence
```text
{
  "contract_version": "whole-book-imitation-readiness.v1",
  "stable_contract_version": "whole-book-imitation-readiness-pre-v1",
  "whole_book_contract_version": "whole-book-imitation.v1",
  "whole_book_stable_contract_version": "whole-book-imitation-pre-v1",
  "database": {
    "masked_database_url": "postgresql+psycopg://d2:***@127.0.0.1:5432/novel_analyzer",
    "effective_db_name": "novel_analyzer"
  },
  "provider": {
    "provider_name": "vip1129",
    "base_url": "https://api.vip1129.cc/v1",
    "api_key_present": true,
    "model_name": "gpt-5.4-mini",
    "stage_model_name": "gpt-5.4-mini",
    "qa_model_name": "gpt-5.4-mini",
    "provider_health": {
      "provider_name": "vip1129",
      "model_name": "gpt-5.4-mini",
      "last_status": "degraded",
      "degraded_events": 14,
      "success_events": 8,
      "last_error": "503 Service temporarily unavailable",
      "last_updated_at": "2026-05-04T10:39:09.713945+00:00"
    }
  },
  "branch_candidate": {
    "branch_id": "23685de0-a53e-4229-a946-14d53d5b026d",
    "exists": true,
    "chapter_analysis_count": 5,
    "fact_record_count": 51,
    "chapter_span": {
      "min": 1,
      "max": 5
    },
    "run_id": "51499b32-cdd0-475f-bbc7-2ac27ea0f529",
    "branch_name": "main",
    "status": "active",
    "novel_title": "真实中文修仙样例-青华-原文3节短复跑"
  },
  "readiness_notes": [
    "如果 api_key_present=false，则不能做真实 provider-backed whole-book execute。",
    "如果 provider_health.last_status=degraded，应先确认上游 provider 是否恢复。",
    "如果 branch_candidate.chapter_analysis_count < 2，则不适合做 whole-book imitation freeze evidence。"
  ]
}
```

## Route-level profiling update
- postfix route profiling 结果：
  - `fts` ≈ 0.004s
  - `similarity` ≈ 0.004s
  - `like` ≈ 0.001s
  - `keyword` ≈ 0.001s
  - `entity_exact` ≈ 0.003s
  - `vector` ≈ 2.501s
  - `raw_search` ≈ 0.197s
  - `rerank` ≈ 6.312s
- 这说明 retrieval diagnostics 的最重路径已经被收缩到：`rerank` 第一、`vector route` 第二，SQL/keyword/entity-exact 路由都不是主要瓶颈。

## Candidate-cap follow-up
- 已新增 rerank candidate cap 与 raw candidate multiplier 收敛。
- 但在当前 5 节完成分支上，`raw_search` 只产生了 5 个候选，因此 rerank 实际仍对 5 个候选执行，时延约 `6.688s`。
- 这说明本轮裁剪更偏向保护更大规模 branch；对当前小分支而言，下一步真正需要优化的是 rerank 本体，而不是继续压缩候选规模。

## Rerank input trim result
- 在相同完成分支上，route profiling 显示：
  - 之前 `rerank` ≈ 6.688s
  - 本轮加入 rerank 输入裁剪后 `rerank` ≈ 6.021s
- 这说明输入裁剪在当前短样例分支上带来了约 10% 左右的真实收益，但 `rerank` 仍然是第一慢点。
