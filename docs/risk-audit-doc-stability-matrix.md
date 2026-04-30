# 风险审查文档稳定性分级 / 冻结建议

## 1. 目的

这份文档用于明确：

1. 哪些文档已经进入 **稳定维护态**
2. 哪些文档仍属于 **持续更新态**
3. 后续维护时应采用什么变更策略

---

## 2. 分级说明

### A. 稳定维护态

定义：

- 核心结构已成型
- 不应频繁大改
- 后续只做小幅更新或随实现变更同步

### B. 持续更新态

定义：

- 内容仍在随能力扩展快速变化
- 路线、边界、规划仍可能调整
- 需要随着 checker / 交付层演进持续更新

---

## 3. 当前建议分级

### 稳定维护态

1. `risk-audit-docs-index.md`
   - 已是稳定导航入口

2. `risk-audit-doc-source-of-truth-matrix.md`
   - 已是文档口径治理入口

3. `risk-audit-doc-consistency-checklist.md`
   - 已是维护规则说明

4. `skills-vs-risk-checkers-boundary.md`
   - 当前职责边界已较清晰，后续变动频率应较低

5. `risk-audit-runtime-boundary.md`
   - 运行时与非运行时边界已较稳定

### 持续更新态

1. `risk-audit-system-overview.md`
   - 会随着成熟度判断变化而更新

2. `risk-audit-delivery-summary.md`
   - 会随着当前交付物变化而更新

3. `risk-audit-capability.md`
   - 会随着已实现能力变化而更新

4. `risk-audit-runtime-architecture.md`
   - 会随着运行时交付链变化而更新

5. `risk-audit-checker-roadmap.md`
   - 本质上就是规划文档，应持续更新

6. `reader-experience-capability.md`
   - 当前仍是规划态，应持续更新

---

## 4. 推荐维护策略

### 对稳定维护态文档

建议：

- 不主动改结构
- 尽量只做内容校正
- 变更前优先确认是否真的影响边界/导航/治理

### 对持续更新态文档

建议：

- 与实现同步更新
- 每次 checker、交付字段、结论策略变化都要审视是否影响这些文档
- 允许随着阶段演进调整结构

---

## 5. 变更优先顺序建议

### 当实现变化时

优先更新：

1. `risk-audit-capability.md`
2. `risk-audit-runtime-architecture.md`
3. `risk-audit-checker-roadmap.md`
4. `risk-audit-system-overview.md`
5. `risk-audit-delivery-summary.md`

### 当文档治理变化时

优先更新：

1. `risk-audit-doc-source-of-truth-matrix.md`
2. `risk-audit-doc-consistency-checklist.md`
3. `risk-audit-docs-index.md`

---

## 6. 当前冻结建议

### 可以视为“基本冻结”的文档

- `risk-audit-docs-index.md`
- `risk-audit-doc-source-of-truth-matrix.md`
- `risk-audit-doc-consistency-checklist.md`
- `skills-vs-risk-checkers-boundary.md`
- `risk-audit-runtime-boundary.md`

### 不建议冻结的文档

- `risk-audit-system-overview.md`
- `risk-audit-delivery-summary.md`
- `risk-audit-capability.md`
- `risk-audit-runtime-architecture.md`
- `risk-audit-checker-roadmap.md`
- `reader-experience-capability.md`

---

## 7. 一句话总结

> 导航、口径治理、边界类文档可以进入稳定维护态；  
> 能力、架构、路线图、交付摘要类文档仍应保持持续更新态。
