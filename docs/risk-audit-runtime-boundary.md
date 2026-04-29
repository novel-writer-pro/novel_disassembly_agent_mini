# 风险审查能力的运行时边界

## 结论

当前这套 **统一风险审查能力** 在运行时 **不依赖 Codex skills**。

它真正依赖的是系统自己的：

1. 章节拆书与分析产物
2. facts / graph / windows / state summary 等派生层
3. Python 后端中的 risk checker / aggregator / export / report 逻辑

`skills` 只是在开发期、代理工作流里辅助：

- 规划
- 调试
- 验证
- 推动代码实现

而不是产品运行时的核心执行组件。

---

## 运行时真正依赖的能力层

### 1. 上游章节分析层

系统先产出：

- `chapter_artifact`
- `retrieval_document`
- `fact_record`
- `graph_nodes / graph_edges`
- `window_artifact`
- `state_summary`

这些是风险审查的真实输入。

### 2. 风险审查层

当前运行时的 checker 位于：

- `novel_analyzer/services/risk_audit_service.py`

当前系统 checker roster：

- `character_ooc`
- `world_rule_consistency`
- `plot_logic_consistency`
- `timeline_consistency`
- `power_scaling_consistency`

### 3. 聚合与交付层

风险结果再由系统自己的后端组件聚合与输出：

- `ExportService`
- `branch_report`
- `branch_bundle`
- `chapter_bundle`

交付物包括：

- `ChapterRiskCard`
- `review_candidates_summary`
- `review_candidate_clusters`
- `audit_conclusion`
- Markdown / JSON 报告

---

## skills 在哪里有关系

只在 **开发期 / 代理执行期** 有关系，例如：

- 让代理规划下一步 checker 路线
- 让代理执行回归验证
- 让代理补文档和代码

但这些都不属于产品运行时门控能力。

---

## 对外建议表述

推荐说：

> 系统内置统一风险审查引擎，基于章节拆书、事实层、图谱层和连续性信号层生成风险卡、问题簇与审查结论。

不推荐说：

> 这是 Codex / skill 帮忙检查出来的结果。

---

## 当前产品化边界

### 属于系统运行时

- chapter analysis pipeline
- facts / graph / windows / state summary
- risk_audit_service
- risk card / review candidates / clusters / audit conclusion
- export / report / API consumption

### 不属于系统运行时

- Codex prompt skills
- 代理编排工作流
- 开发时的 deep-interview / ralph / plan 等辅助能力

---

## 一句话总结

> 当前风险审查能力是 **系统运行时能力**；skills 只是开发与推进这套能力时的辅助工具，不是最终产品的执行依赖。
