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
| `architecture/README.md` | 架构专题导航层 | 否 | 架构/后端/维护 |
| `architecture/risk-audit-semantic-enhancement.md` | 语义增强架构层 | **是（语义增强边界）** | 架构/后端 |
| `architecture/risk-audit-embedding-pgvector-implementation-spec.md` | embedding 实施规格层 | **是（生产落地规格）** | 架构/后端 |
| `risk-audit-checker-roadmap.md` | 路线图层 | **是（后续规划）** | 研发规划 |
| `risk-audit-next-batch-checkers.md` | 新增 checker 设计层 | **是（新增 checker 设计口径）** | 架构/后端/规划 |
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

### E. 风险审查主链为什么不直接全量使用 embedding / LLM skills

唯一优先事实源：

- `architecture/risk-audit-semantic-enhancement.md`

### F. embedding / pgvector 最终方案如何落成数据对象与服务

唯一优先事实源：

- `architecture/risk-audit-embedding-pgvector-implementation-spec.md`

### G. 后续 checker 路线与阶段

唯一优先事实源：

- `risk-audit-checker-roadmap.md`

### H. 下一批新增 checker 的立项边界与设计口径

唯一优先事实源：

- `risk-audit-next-batch-checkers.md`

### I. Reader Experience 的后续规划

唯一优先事实源：

- `reader-experience-capability.md`

### J. 文档维护规则

唯一优先事实源：

- `risk-audit-doc-consistency-checklist.md`

### K. 样例小说结论链

唯一优先事实源按职责拆分：

- 主结论：`.omx/reports/sample-novel-current-conclusion.md`
- phase-2 离线 best-effort：`.omx/reports/sample-novel-phase2-offline-memo-20260430.md`
- phase-2 阻塞/恢复：`.omx/reports/sample-novel-phase2-db-blocker-20260430.md`

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

### `architecture/README.md`

职责：

- 作为架构专题文档总入口

不应负责：

- 单独定义某个架构主题的最终口径

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

若涉及语义增强路线：
4. `architecture/risk-audit-semantic-enhancement.md`

若涉及 embedding / pgvector 落地规格：
5. `architecture/risk-audit-embedding-pgvector-implementation-spec.md`

### 如果改“后续计划”

先改：
1. `risk-audit-checker-roadmap.md`

若涉及新增 checker 的具体设计边界：
2. `risk-audit-next-batch-checkers.md`

若涉及读者向扩展：
3. `reader-experience-capability.md`

### 如果改“文档体系本身”

先改：
1. `risk-audit-doc-consistency-checklist.md`
2. `risk-audit-docs-index.md`
3. `docs/README.md`

### 如果改“样例小说结论链”

先改：
1. `.omx/reports/sample-novel-current-conclusion.md`
2. `.omx/reports/sample-novel-phase2-offline-memo-20260430.md`
3. `.omx/reports/sample-novel-phase2-db-blocker-20260430.md`

再同步：
4. `risk-audit-doc-consistency-checklist.md`
5. `risk-audit-docs-index.md`
6. `docs/README.md`

---

## 6. 建议长期遵守的规则

1. **能力现状只认 `risk-audit-capability.md`**
2. **运行时架构只认 `risk-audit-runtime-architecture.md`**
3. **语义增强边界只认 `architecture/risk-audit-semantic-enhancement.md`**
4. **embedding / pgvector 落地规格只认 `architecture/risk-audit-embedding-pgvector-implementation-spec.md`**
5. **后续 checker 路线只认 `risk-audit-checker-roadmap.md`**
6. **新增 checker 的立项边界只认 `risk-audit-next-batch-checkers.md`**
7. **Reader Experience 规划只认 `reader-experience-capability.md`**
8. **团队汇报用 `risk-audit-delivery-summary.md`，但不要反向覆盖定义源**
9. **样例小说主结论 / 离线 memo / blocker memo 各自分工，不互相替代**

---

## 7. 一句话总结

> 后续维护时，先改“定义源”，再同步“摘要层”；  
> 不要直接从摘要层反推定义层。
