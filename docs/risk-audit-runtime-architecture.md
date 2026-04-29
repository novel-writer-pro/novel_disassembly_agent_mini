# 统一风险审查体系：运行时架构说明

## 1. 定位

当前 `novel-analyzer` 的风险审查能力属于 **系统运行时能力**。

它的职责是：

1. 基于章节拆书产物识别连续性/设定风险
2. 聚合为章节风险卡
3. 进一步生成 review candidates、问题簇与审查结论
4. 为作家 / 编辑 / 审稿者提供可解释的复核入口

---

## 2. 运行时分层

```text
原文章节
  ↓
章节拆书分析层
  ↓
chapter_artifact / facts / graph / windows / state summary
  ↓
risk_audit_service checker 层
  ↓
aggregator / branch export / report 层
  ↓
risk card / review candidates / clusters / audit conclusion
```

---

## 3. 各层职责

### A. 上游拆书分析层

产出：

- `chapter_artifact`
- `retrieval_document`
- `fact_record`
- `graph_nodes / graph_edges`
- `window_artifact`
- `state_summary`

作用：

- 为下游门控提供稳定输入底座

### B. Checker 层

当前实现位于：

- `novel_analyzer/services/risk_audit_service.py`

当前 checker roster：

- `character_ooc`
- `world_rule_consistency`
- `plot_logic_consistency`
- `timeline_consistency`
- `power_scaling_consistency`

作用：

- 逐章节产出统一 `GateRiskItem`
- 允许 `ready / partial / skipped / failed`
- 默认 advisory-only

### C. 聚合层

作用：

- 合并多个 checker 输出
- 生成 `ChapterRiskCard`
- 统计 `risk_counts_by_domain / severity`
- 产出 `review_candidates_summary`
- 产出 `review_candidate_clusters`
- 生成结构化 `audit_conclusion`

### D. 交付层

作用：

- 输出 `branch_bundle`
- 输出 `chapter_bundle`
- 输出 `branch_report`
- 输出可供 API / report / 下游消费的 JSON/Markdown

---

## 4. 关键运行时对象

### `GateRiskItem`

单条标准化风险项，包含：

- `checker_name`
- `risk_domain`
- `risk_type`
- `severity`
- `confidence`
- `summary`
- `supporting_evidence`
- `counter_evidence`

### `ChapterRiskCard`

章节级统一风险卡，包含：

- `overall_risk_level`
- `top_risks`
- `risk_counts_by_domain`
- `risk_counts_by_severity`
- `checker_statuses`
- `coverage_gaps`

### `review_candidates_summary`

章节级候选摘要，强调：

- 哪一章需要人工复核
- 为什么需要复核
- 有哪些证据预览

### `review_candidate_clusters`

跨章节问题簇，强调：

- 同类问题是否重复出现
- 影响到哪些章节
- 建议动作
- 处理优先级
- 生命周期状态

### `audit_conclusion`

结构化系统审查结论，包含：

- `content_judgement`
- `risk_judgement`
- `blocking_judgement`
- `recommended_action`

---

## 5. 当前运行时语义

### advisory-only

当前风险审查结果默认：

- 不阻断主提交
- 不自动修文
- 不自动改 canon
- 只做风险提示与人工复核辅助

### 非目标

当前运行时不负责：

- 写作接管
- 自动续写
- 自动修改正文
- 主观文风优劣评判

---

## 6. 当前系统已经具备的交付能力

### 章节级

- 风险卡
- 风险细节
- supporting / counter evidence

### 分支级

- risk summary
- failed summary
- review candidate count
- review candidate summary
- review candidate clusters
- structured audit conclusion

### 报告级

- Markdown branch report
- JSON branch bundle
- package 级逐章导出产物

---

## 7. 当前最适合的产品化表述

推荐说：

> 系统基于章节拆书产物、事实层、图谱层和连续性信号层，运行统一风险审查引擎，输出章节风险卡、问题簇与结构化审查结论。

---

## 8. 当前限制

1. 后三类 checker（plot / timeline / power）虽已开始提质，但仍不是最终高召回版。
2. review candidate cluster 目前是 heuristic clustering，不是严格语义聚类。
3. cluster status 目前只是运行时默认状态语义，尚未接入人工确认/回写闭环。

---

## 9. 下一步自然演进

1. 增强 cross-chapter evidence ranking / 降噪
2. 为 cluster 增加人工确认回写机制
3. 把 cluster status 与 review workflow 真正接通
