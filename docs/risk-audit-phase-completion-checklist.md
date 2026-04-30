# 风险审查体系：当前阶段完成清单

## 1. 目的

这份清单用于明确：

1. 当前阶段哪些内容可视为 **已完成**
2. 哪些内容应明确进入 **下一阶段 backlog**
3. 当前是否可以认为这条线已进入 **阶段性收口**

---

## 2. 当前阶段已完成项

### A. 运行时骨架

- [x] 统一风险审查框架已建立
- [x] checker roster 已建立
- [x] advisory-only 语义已建立
- [x] downstream risk audit 不阻断主提交流程

### B. Checker 层

- [x] `character_ooc` 已正式落地
- [x] `world_rule_consistency` 已正式落地
- [x] `plot_logic_consistency` 已纳入并进入 artifact-signal 提质
- [x] `timeline_consistency` 已纳入并进入 artifact-signal 提质
- [x] `power_scaling_consistency` 已纳入并进入 artifact-signal 提质

### C. 聚合与交付层

- [x] `ChapterRiskCard` 已贯通
- [x] `review_candidates_summary` 已贯通
- [x] `review_candidate_clusters` 已贯通
- [x] `audit_conclusion` 已结构化
- [x] `failed_summary` 已纳入交付

### D. 问题簇层

- [x] `cluster_title`
- [x] `suggested_review_action`
- [x] `review_priority`
- [x] `cluster_status`

### E. 报告层

- [x] Markdown `branch_report` 已可读
- [x] JSON `branch_bundle` 已可消费
- [x] 候选证据预览已进入报告
- [x] 跨章节问题簇已进入报告

### F. 文档层

- [x] 总览文档
- [x] 能力说明文档
- [x] 运行时架构文档
- [x] 运行时边界文档
- [x] `skills_dir` vs checker 边界文档
- [x] checker 路线图文档
- [x] Reader Experience 规划文档
- [x] 文档导航文档
- [x] 文档一致性清单
- [x] 单一事实来源矩阵
- [x] 文档稳定性分级
- [x] 代码稳定性分级
- [x] 最终交付摘要

---

## 3. 当前阶段验证结论

### 工程层

- [x] 当前风险审查相关回归已多轮通过
- [x] 最近 targeted regression 已稳定通过
- [x] 交付物已多次重新导出验证

### 示例验证层

- [x] 当前示例小说在 `1–103` 章范围内未发现明确成立的 OOC
- [x] 当前存在少量 `low` 级人工复核候选
- [x] 当前候选已聚成问题簇
- [x] `104` 章之后不再作为继续拆书目标推进
- [x] `provider_connection` 作为外部阻塞证据已保留

---

## 4. 当前阶段不应继续扩散的内容

以下内容在当前阶段应视为 **不继续扩散**：

- [x] 不再继续扩展示例小说拆书范围
- [x] 不继续优先补 UI
- [x] 不继续无边界增加新 checker 数量
- [x] 不把 Reader Experience 规划直接拉进本环境实施

---

## 5. 下一阶段 backlog

### P1

- [ ] 强化 `character_ooc`
- [ ] 强化 `world_rule_consistency`
- [ ] 强化 `plot_logic_consistency`
- [ ] 强化 `timeline_consistency`
- [ ] 强化 `power_scaling_consistency`

### P2

- [ ] 建立 review workflow 闭环
- [ ] 引入 review owner / note / resolved 机制
- [ ] 让 `cluster_status` 支持真实状态回写

### P3

- [ ] Reader Experience 第一批能力（只在后续阶段考虑）
  - [ ] 踩雷/内容预警标签
  - [ ] 高潮/转折章节定位
  - [ ] 角色/冲突跳转推荐

---

## 6. 当前阶段是否可以视为完成

结论：

> **可以。**

更准确地说：

> 当前风险审查体系已经达到“第一阶段阶段性完成”的状态，后续工作应转入“持续提质 + review workflow 闭环”，而不是继续扩散式建设。

---

## 7. 一句话交接话术

> 当前风险审查体系第一阶段已完成：运行骨架、checker roster、风险卡、问题簇、结构化结论、Markdown/JSON 交付和文档治理体系都已建立；下一阶段重点应转向 checker 精度提升与 review workflow 闭环。
