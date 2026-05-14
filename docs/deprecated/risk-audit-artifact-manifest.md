# 风险审查交付物清单

## 1. 目的

这份清单用于说明：

1. 当前风险审查体系会产出哪些核心交付物
2. 每种交付物适合谁使用
3. 应该从哪里读取或导出

---

## 2. 章节级交付物

### `ChapterRiskCard`

作用：

- 给单章做统一风险概览

包含：

- `overall_risk_level`
- `top_risks`
- `risk_counts_by_domain`
- `risk_counts_by_severity`
- `checker_statuses`
- `coverage_gaps`

适合：

- 作者
- 编辑
- 审稿者

来源：

- `export_chapter_bundle`
- chapter bundle JSON

---

## 3. 分支级交付物

### `risk_summary`

作用：

- 概括整个 branch 的风险状态

包含：

- `risk_card_count`
- `checker_result_count`
- `review_candidate_count`
- `high_risk_chapters`
- `risk_counts_by_domain`
- `risk_counts_by_severity`

### `failed_summary`

作用：

- 说明当前执行阻塞或失败章节

### `audit_conclusion`

作用：

- 给出结构化系统结论

包含：

- `content_judgement`
- `risk_judgement`
- `blocking_judgement`
- `recommended_action`
- `review_progress_note`（若有）

适合：

- 产品
- 编辑负责人
- 研发负责人

来源：

- `export_branch_bundle`
- `export_branch_report`

---

## 4. 复核级交付物

### `review_candidates_summary`

作用：

- 列出当前最值得人工复核的章节级候选

特点：

- 已做跨 checker specificity 排序
- 已做一定程度 noise suppression
- 已附带 continuity / branch signal preview

### `review_candidate_clusters`

作用：

- 把跨章节重复出现的问题聚成问题簇

包含：

- `cluster_title`
- `suggested_review_action`
- `review_priority`
- `cluster_status`
- `review_owner`
- `resolved_at`
- `review_notes`
- `review_history`

适合：

- 编辑
- 审稿负责人
- 后续 review workflow

来源：

- `branch_bundle`
- `branch_report`

---

## 5. 报告级交付物

### Markdown `branch_report`

作用：

- 给团队直接阅读

当前会显示：

- `Audit Conclusion`
- `Failed Summary`
- `Risk Summary`
- `Human Review Candidates`
- `Review Candidate Evidence Preview`
- `Review Candidate Clusters`

### JSON `branch_bundle`

作用：

- 给系统接入 / API / 下游 agent 使用

---

## 6. 最小 review workflow 交付物

### 运行时 review registry

当前最小写回支持：

- `cluster_status`
- `review_notes`
- `review_owner`
- `resolved_at`

CLI：

- `set-cluster-status`
- `show-cluster-status`

适合：

- 内部试用
- 最小人工复核闭环

关联文档：

- `minimal-review-workflow-guide.md`
- `minimal-review-workflow-state-machine.md`
- `cluster-status-semantics.md`

---

## 7. 一句话总结

> 当前风险审查体系的交付物已经覆盖：章节风险卡、分支总结、问题簇、结构化结论和最小人工复核写回原型。
