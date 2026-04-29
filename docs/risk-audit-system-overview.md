# 风险审查系统总览

## 1. 当前结论（一页读懂）

### 当前成熟度判断

当前风险审查能力已经达到：

> **第一阶段比较完整、可交付、可维护的系统水准**

并且：

> **第二阶段（review workflow 正式化）设计稿已就绪，可直接进入排期。**

但还没有达到：

> **最终成熟、高召回、低噪音的审稿引擎水准**

### 为什么说“第一阶段比较完整”

因为系统已经具备完整链路：

1. 上游拆书分析产物
2. checker 层
3. risk aggregator
4. review candidates
5. review candidate clusters
6. structured audit conclusion
7. Markdown / JSON 导出交付

### 为什么还不算“最终成熟”

因为：

- `plot / timeline / power` 仍在持续提质
- 仍有 heuristic / advisory-first 语义
- 还未接入人工复核回写闭环
- 误报抑制与跨章节推理仍有提升空间

---

## 2. 系统解决什么问题

当前系统的核心目标不是替代创作，而是：

1. 对章节做 **设定/连续性风险审查**
2. 帮助作者 / 编辑 / 审稿者快速定位可疑章节
3. 输出统一的风险卡、问题簇和审查结论
4. 形成可复核、可导出、可持续维护的系统能力

---

## 3. 当前系统能力边界

### 3.1 已经覆盖

- 人物 OOC
- 世界规则一致性
- 剧情逻辑
- 时间线一致性
- 战力/能力漂移

### 3.2 当前不覆盖

- 自动修文
- 自动改 canon
- 审美/文风优劣
- 写作接管
- 最终“好不好看”打分

### 3.3 默认语义

- advisory-only
- 不阻断主提交
- 优先给出风险提示与人工复核入口

---

## 4. 当前运行时架构

```text
原文章节
  ↓
skills_dir 驱动的上游拆书分析
  ↓
chapter_artifact / facts / graph / windows / state summary
  ↓
risk_audit_service 中的 checker
  ↓
risk card / review candidates / clusters / audit conclusion
  ↓
bundle / report / API / 下游消费
```

### 4.1 `skills_dir` 的职责

主要负责：

- 上游章节拆书分析 prompt
- staged analysis 资产
- 章节结构化产物生成

### 4.2 risk checker 的职责

主要负责：

- 下游门控与风险判断
- 风险聚合
- 风险导出
- 审查结论生成

---

## 5. 当前 checker 现状

## A. 相对成熟

### `character_ooc`

- 当前最成熟
- 已形成较稳定的 candidate / cluster / report 输出链路

### `world_rule_consistency`

- 已正式落地
- 规则层审查已进入统一体系
- 已开始复用 artifact signals（`world_rule_signals`、`unsupported_inferences`、`evidence_backed_resolutions`、`unresolved_threads`）

## B. 已开始提质

### `plot_logic_consistency`

已开始复用：

- `unsupported_inferences`
- `state_transition_notes`
- `evidence_backed_resolutions`
- `unresolved_threads`

### `timeline_consistency`

已开始复用：

- `timeline_signals`
- `unsupported_inferences`
- `ambiguous_points`
- `state_transition_notes`
- `unresolved_threads`

### `power_scaling_consistency`

已开始复用：

- `power_signals`
- `unsupported_inferences`
- `ambiguous_points`
- `state_transition_notes`
- `unresolved_threads`

---

## 6. 当前系统交付物

### 6.1 章节级

- `ChapterRiskCard`
- 风险明细
- supporting / counter evidence

### 6.2 分支级

- `risk_summary`
- `failed_summary`
- `review_candidate_count`
- `review_candidates_summary`
- `review_candidate_clusters`
- `audit_conclusion`

### 6.3 报告级

- Markdown `branch_report`
- JSON `branch_bundle`
- package 级逐章产物

---

## 7. 当前问题簇能力

当前系统已经不仅能给出“单章风险”，还可以给出：

### `review_candidate_clusters`

字段包括：

- `cluster_title`
- `checker_names`
- `risk_types`
- `chapters`
- `chapter_count`
- `first_chapter`
- `last_chapter`
- `max_confidence`
- `suggested_review_action`
- `review_priority`
- `cluster_status`

当前已经接近：

> **编辑可直接阅读的问题清单**

---

## 8. 当前如何评估能力是否靠谱

建议从三层评估：

### A. 架构完整性

判断标准：

- 是否具备完整链路
- 是否有稳定交付物
- 是否能支撑后续扩展

当前结论：

- 已达标

### B. 工程可靠性

判断标准：

- 是否可测试
- 是否可回归
- 是否可重复导出

当前 evidence：

- 最近 targeted regression: **40 passed**

当前结论：

- 已达标

### C. 判断质量

判断标准：

- 是否噪音可控
- 是否有稳定证据链
- 是否已具备跨章节解释性

当前结论：

- 人物 OOC：较好
- 规则一致性：中等
- plot / timeline / power：已可用，但仍在提质

---

## 9. 当前建议对外表述

推荐表述：

> 系统已经具备统一风险审查体系的第一阶段能力，当前正式覆盖人物 OOC 与规则一致性，并已将剧情逻辑、时间线、战力能力审查纳入统一 checker 体系。系统可输出风险卡、问题簇与结构化审查结论，适合作为作者 / 编辑的审稿辅助能力使用。

不推荐表述：

- 已经是完全成熟的自动审稿引擎
- 能自动判断小说好不好看
- 能直接替代人工编辑

---

## 10. 文档阅读建议（按角色）

### 给产品/业务

1. `risk-audit-system-overview.md`
2. `risk-audit-capability.md`
3. `reader-experience-capability.md`

### 给架构/后端

1. `risk-audit-runtime-architecture.md`
2. `risk-audit-runtime-boundary.md`
3. `skills-vs-risk-checkers-boundary.md`

### 给研发规划/长期维护

1. `risk-audit-checker-roadmap.md`
2. `risk-audit-system-overview.md`

---

## 11. 后续维护重点

1. 强化 `character_ooc`
2. 强化 `world_rule_consistency`
3. 继续提质 `plot / timeline / power`
4. 建 review workflow 闭环
5. 控制噪音与误报
6. 稳定问题簇与结论语义

---

## 12. 一句话总结

> 当前风险审查系统已经具备“第一阶段比较完整”的系统能力；  
> 它已经是可运行、可导出、可解释、可维护的门控框架，但仍处在持续提质阶段。
