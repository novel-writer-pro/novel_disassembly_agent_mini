# 风险审查文档口径统一矩阵

## 1. 目的

这份矩阵用于回答：

1. 哪份文档是 **单一事实来源（source of truth）**
2. 哪份文档只是 **摘要层**
3. 哪份文档属于 **规划层**
4. 后续修改某类信息时，应该先改哪一份

---

## 2. 文档角色矩阵

| 文档 | 角色 | 是否单一事实来源 | 适合读者 |
|---|---|---:|---|
| `risk-audit-docs-index.md` | 导航层 | 否 | 全部角色 |
| `risk-audit-system-overview.md` | 总览层 | 否 | 产品/研发/维护 |
| `risk-audit-delivery-summary.md` | 摘要层 | 否 | 团队同步/汇报 |
| `risk-audit-capability.md` | 能力定义层 | **是（能力现状）** | 产品/研发 |
| `risk-audit-runtime-architecture.md` | 运行时架构层 | **是（架构口径）** | 架构/后端 |
| `risk-audit-runtime-boundary.md` | 运行时边界层 | **是（运行边界）** | 架构/后端 |
| `skills-vs-risk-checkers-boundary.md` | skills/checker 边界层 | **是（职责边界）** | 架构/后端 |
| `risk-audit-checker-roadmap.md` | 路线图层 | **是（后续规划）** | 研发规划 |
| `reader-experience-capability.md` | Reader Experience 规划层 | **是（读者向规划）** | 产品/规划 |
| `risk-audit-doc-consistency-checklist.md` | 文档维护层 | **是（维护规则）** | 长期维护者 |

---

## 3. 推荐的“单一事实来源”映射

### A. 当前系统已经具备哪些能力

唯一优先事实源：

- `risk-audit-capability.md`

说明：

- 如果能力现状变更，先改这里
- `risk-audit-system-overview.md` 与 `risk-audit-delivery-summary.md` 只做同步摘要

### B. 当前运行时怎么工作

唯一优先事实源：

- `risk-audit-runtime-architecture.md`

说明：

- 如果运行链路或分层变化，先改这里

### C. 当前什么不属于运行时

唯一优先事实源：

- `risk-audit-runtime-boundary.md`

### D. `skills_dir` 与 risk checker 的职责差异

唯一优先事实源：

- `skills-vs-risk-checkers-boundary.md`

### E. 后续 checker 路线与阶段

唯一优先事实源：

- `risk-audit-checker-roadmap.md`

### F. Reader Experience 的后续规划

唯一优先事实源：

- `reader-experience-capability.md`

### G. 文档维护规则

唯一优先事实源：

- `risk-audit-doc-consistency-checklist.md`

---

## 4. 哪些文档只做摘要，不做定义

以下文档不应成为“定义源”：

### `risk-audit-system-overview.md`

职责：

- 给出全局认识
- 给出成熟度判断

不应负责：

- 字段细节
- checker 实现边界

### `risk-audit-delivery-summary.md`

职责：

- 给团队同步
- 给阶段汇报

不应负责：

- 作为能力定义的最终依据
- 作为路线图的最终依据

### `risk-audit-docs-index.md`

职责：

- 做导航

不应负责：

- 任何最终定义

---

## 5. 推荐修改顺序

### 如果改“已实现能力”

先改：
1. `risk-audit-capability.md`

再同步：
2. `risk-audit-system-overview.md`
3. `risk-audit-delivery-summary.md`

### 如果改“架构和运行时”

先改：
1. `risk-audit-runtime-architecture.md`
2. `risk-audit-runtime-boundary.md`

若涉及 `skills_dir`：
3. `skills-vs-risk-checkers-boundary.md`

### 如果改“后续计划”

先改：
1. `risk-audit-checker-roadmap.md`

若涉及读者向扩展：
2. `reader-experience-capability.md`

### 如果改“文档体系本身”

先改：
1. `risk-audit-doc-consistency-checklist.md`
2. `risk-audit-docs-index.md`
3. `docs/README.md`

---

## 6. 建议长期遵守的规则

1. **能力现状只认 `risk-audit-capability.md`**
2. **运行时架构只认 `risk-audit-runtime-architecture.md`**
3. **后续 checker 路线只认 `risk-audit-checker-roadmap.md`**
4. **Reader Experience 规划只认 `reader-experience-capability.md`**
5. **团队汇报用 `risk-audit-delivery-summary.md`，但不要反向覆盖定义源**

---

## 7. 一句话总结

> 后续维护时，先改“定义源”，再同步“摘要层”；  
> 不要直接从摘要层反推定义层。
