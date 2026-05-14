# 风险审查代码稳定性分级 / 冻结建议

## 1. 目的

这份文档用于说明：

1. 哪些代码模块已经进入 **稳定维护态**
2. 哪些代码模块仍属于 **持续提质态**
3. 哪些模块后续不建议频繁重构
4. 哪些模块应继续快速迭代

---

## 2. 分级标准

### A. 稳定维护态

定义：

- 核心职责清晰
- 接口基本稳定
- 已被多轮回归覆盖
- 后续以小改/修正为主

### B. 持续提质态

定义：

- 已可用，但算法/信号质量仍在演进
- 误报抑制、召回率、解释性仍需持续优化
- 不宜过早冻结

---

## 3. 当前模块分级

### 稳定维护态

#### 1. `novel_analyzer/reporting/branch_report.py`

原因：

- 已承载稳定报告输出
- 结构化结论、问题簇、候选预览等交付形态已成型

建议：

- 不要频繁重构整体结构
- 后续以字段补充、小幅排版调整为主

#### 2. `novel_analyzer/services/export_service.py` 的交付拼装职责

稳定部分：

- branch bundle 输出骨架
- risk summary 输出骨架
- audit conclusion 输出骨架
- review candidate / cluster 交付骨架

建议：

- 输出骨架不宜大改
- 后续主要增强字段质量，不轻易推翻输出结构

#### 3. 风险审查文档体系

对应文档：

- `risk-audit-docs-index.md`
- `risk-audit-doc-source-of-truth-matrix.md`
- `risk-audit-doc-consistency-checklist.md`
- `risk-audit-doc-stability-matrix.md`

建议：

- 进入稳定维护态

---

### 持续提质态

#### 1. `novel_analyzer/services/risk_audit_service.py`

原因：

- checker roster 已稳定
- 但 checker 质量仍在持续提质

建议：

- 保持框架稳定
- 继续优化 checker 内部逻辑

#### 2. `character_ooc`

状态：

- 当前最成熟

但仍建议：

- 持续优化角色画像基线
- 优化误报抑制

#### 3. `world_rule_consistency`

状态：

- 已正式落地

但仍建议：

- 强化规则真源提取
- 区分规则例外与规则冲突

#### 4. `plot_logic_consistency`

状态：

- 已进入 artifact-signal 提质阶段

但仍建议：

- 继续补事件因果链建模

#### 5. `timeline_consistency`

状态：

- 已进入 artifact-signal 提质阶段

但仍建议：

- 继续补时间线、恢复时长、顺序推断质量

#### 6. `power_scaling_consistency`

状态：

- 已进入 artifact-signal 提质阶段

但仍建议：

- 继续补战力基线、能力跃迁阈值

---

## 4. 推荐冻结策略

### 可以视为“基本冻结”的代码层

1. `branch_report.py` 的章节/风险/问题簇/审查结论总体结构
2. `export_service.py` 的 branch-level 交付骨架
3. 风险审查文档导航与治理体系

### 不建议冻结的代码层

1. `risk_audit_service.py` 内部 checker 判定逻辑
2. candidate ranking / denoise 规则
3. cluster heuristic 规则
4. audit conclusion heuristics

---

## 5. 后续改动建议

### 如果要“加能力”

优先方式：

- 在现有框架内加字段/加信号/加规则

不建议：

- 直接推翻 risk card / cluster / conclusion 输出骨架

### 如果要“提质量”

优先方式：

- 强化 signal extraction
- 强化 cross-chapter evidence
- 强化 false-positive 抑制

### 如果要“做闭环”

优先方向：

- cluster status 回写
- review owner / note / resolved 机制

---

## 6. 一句话总结

> 当前风险审查系统的“交付结构”可以进入稳定维护态；  
> 当前风险审查系统的“checker 判断质量”仍应保持持续提质态。
