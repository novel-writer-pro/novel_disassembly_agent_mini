# AI 小说系统能力评分卡 / Capability Scorecard

> 版本：2026-05-05
> 用途：给产品、研发、交接、商务侧统一理解当前系统成熟度与优先级。

评分说明：
- 1 = 早期概念 / 零散能力
- 2 = 能跑通 demo
- 3 = 主链可用
- 4 = 生产可维护
- 5 = 领先级 / 平台级壁垒

| 能力线 | 当前评分 | 当前状态 | 商业价值 | 快速补强空间 | 主要闭环 |
| --- | ---: | --- | --- | --- | --- |
| 拆书 / chapter analysis | 4 | 主链稳定、可复跑、可导出 | 高 | 中 | 更系统的多书样例与速度评估 |
| 信息抽取 / facts | 4 | facts 已进入 branch/chapter/report 主链 | 高 | 中 | 更统一的作者/编辑消费面 |
| retrieval / QA / search | 4 | RRF + diagnostics + benchmark 已成形，vector/entity-exact 已接入 | 高 | 高 | rerank 真正改序证据、更多 query bank |
| risk semantic | 3.5 | signal/link/cluster/review 已成链 | 高 | 高 | 长窗口 linking / quality benchmark |
| 风险门控 / checker | 4 | 可解释、可维护、真库已验证 | 很高 | 中 | 更多真库样例、批量复核优化 |
| chapter imitation | 4 | harness + repair lanes + assistant control surface 已成形 | 高 | 高 | 更深 story bible / provider-backed 实例密度 |
| whole-book imitation | 3 | provider-backed rerun 成功，仍偏 sandbox | 很高 | 高 | 更多 success evidence、多轮稳定性 |
| eval / governance | 4 | sample bundle / freeze gate / handoff 已落地 | 很高 | 中 | 更产品化的运营 dashboard |
| docs / handoff / ops | 4 | canonical 入口、smoke path、checkout 已落地 | 高 | 中 | FAQ 化、图表化、继续去重 |

## 我们现在最强的 4 个点
1. **风险门控的系统化程度**：很多 AI 写作产品没有这层。  
2. **拆书 + facts + retrieval + graph 的中台结构**：比单点生成器更像平台。  
3. **受控仿写骨架**：不是“直接写”，而是“带 repair / gate / handoff 的写”。  
4. **治理/交接能力**：sample、freeze、smoke、自检、migration 已成闭环。  

## 最值得快速补强的 4 个点
1. retrieval 的 vector/entity-exact 召回  
2. story bible 产品层  
3. whole-book 多轮成功样例密度  
4. 商务白皮书与客户价值图表化  

## 结论
当前系统已经从“功能集合”进入“平台骨架”阶段。  
短期最值得继续投入的，是 retrieval 提升 + author-facing 知识组织层 + more real evidence，而不是单纯去卷更多表层功能。
