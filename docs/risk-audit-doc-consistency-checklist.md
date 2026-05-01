# 风险审查文档一致性清单

## 1. 目的

这份清单用于降低风险审查文档体系的长期维护成本。

它回答三个问题：

1. 哪些文档负责什么
2. 哪些内容容易重叠
3. 后续改动时应该先改哪几份

---

## 2. 当前风险审查文档全景

### 总览层

- `risk-audit-docs-index.md`
- `risk-audit-system-overview.md`
- `architecture/README.md`

### 能力说明层

- `risk-audit-capability.md`
- `reader-experience-capability.md`

### 架构与边界层

- `risk-audit-runtime-architecture.md`
- `risk-audit-runtime-boundary.md`
- `skills-vs-risk-checkers-boundary.md`
- `architecture/risk-audit-semantic-enhancement.md`
- `architecture/risk-audit-embedding-pgvector-implementation-spec.md`

### 路线图层

- `risk-audit-checker-roadmap.md`
- `risk-audit-phase2-checker-implementation.md`
- `risk-audit-next-batch-checkers.md`

### 运行期样例结论链

- `.omx/reports/sample-novel-current-conclusion.md`
- `.omx/reports/sample-novel-phase2-offline-memo-20260430.md`
- `.omx/reports/sample-novel-phase2-db-blocker-20260430.md`

---

## 3. 各文档的单一职责

### `risk-audit-docs-index.md`

职责：

- 作为风险审查文档的统一入口
- 按角色给出阅读顺序

不应承担：

- 具体能力定义
- 具体字段解释
- 具体架构细节

### `architecture/README.md`

职责：

- 作为架构专题文档的统一入口
- 帮助后端/维护者快速定位语义增强与 embedding 落地方案

不应承担：

- 具体 checker 能力定义
- 具体实现规格口径

### `risk-audit-system-overview.md`

职责：

- 说明当前成熟度
- 说明系统现状
- 说明如何评估能力是否靠谱

不应承担：

- 细粒度字段契约
- checker 级技术实现细节

### `risk-audit-capability.md`

职责：

- 说明当前系统已经具备哪些能力
- 说明已落地与已纳入 checker
- 说明当前交付链路

不应承担：

- 文档导航职责
- 长篇路线图职责

### `risk-audit-runtime-architecture.md`

职责：

- 说明运行时分层
- 说明 checker / aggregator / export 在系统中的位置

不应承担：

- 产品路线图
- Reader Experience 规划

### `risk-audit-runtime-boundary.md`

职责：

- 说明运行时能力边界
- 说明什么属于系统运行时

不应承担：

- `skills_dir` 细节边界说明（由专门文档承担）

### `skills-vs-risk-checkers-boundary.md`

职责：

- 专门说明 `skills_dir` 与 risk checker 的职责差异

不应承担：

- 系统成熟度判断
- checker roadmap

### `architecture/risk-audit-semantic-enhancement.md`

职责：

- 解释为什么当前风险审查主链没有直接把 embedding / LLM skills 塞进每个 checker
- 说明后续语义增强应该加在哪一层

不应承担：

- 回写当前已落地 checker 现状
- 替代运行时主架构文档

### `architecture/risk-audit-embedding-pgvector-implementation-spec.md`

职责：

- 定义 ONNX embedding + pgvector 的生产落地规格
- 说明 signal store / link service / adjudication service 的拆分建议

不应承担：

- 替代路线图文档
- 回写当前已实现能力现状

### `risk-audit-checker-roadmap.md`

职责：

- 说明 checker roster
- 说明阶段路线图
- 说明提质顺序

不应承担：

- 运行时边界解释
- 文档导航职责

### `risk-audit-phase2-checker-implementation.md`

职责：

- 详细定义 plot / timeline / power 三类 checker 的第二阶段实施方式
- 明确结构化信号、降噪规则、风险类型与验收门槛

不应承担：

- 总体产品定位
- 文档导航职责

### `risk-audit-next-batch-checkers.md`

职责：

- 定义下一批新增 checker 的立项边界
- 收口新增 checker 的风险类型、信号来源与反误报原则

不应承担：

- 回写当前已实现能力现状
- 替代 phase-2 已落地实现说明

### `reader-experience-capability.md`

职责：

- 说明读者体验相关扩展能力规划

不应承担：

- 当前门控系统实现状态判断
- risk checker 运行时架构说明

### `.omx/reports/sample-novel-current-conclusion.md`

职责：

- 作为样例小说当前主结论文档
- 汇总稳定覆盖范围、主判断、fresh verification evidence

不应承担：

- 详细恢复步骤（由 blocker memo 承担）
- phase-2 离线 best-effort 全量展开（由 offline memo 承担）

### `.omx/reports/sample-novel-phase2-offline-memo-20260430.md`

职责：

- 说明当前离线样例产物能支持到什么程度的 phase-2 结论
- 明确哪些结论成立、哪些仍不能成立

不应承担：

- 作为主结论文档替代
- 作为数据库恢复操作手册

### `.omx/reports/sample-novel-phase2-db-blocker-20260430.md`

职责：

- 说明真实 sample phase-2 复跑为何被阻塞
- 记录恢复条件、恢复步骤、继续命令、完成判据

不应承担：

- 直接输出内容结论
- 替代 offline memo 或主结论

---

## 4. 当前最容易重叠的内容

### 重叠点 A：成熟度判断

容易出现在：

- `risk-audit-system-overview.md`
- `risk-audit-capability.md`

建议：

- **最终成熟度判断只以 `risk-audit-system-overview.md` 为准**
- `risk-audit-capability.md` 只保留能力边界，不重复长段成熟度论述

### 重叠点 B：checker 当前状态

容易出现在：

- `risk-audit-capability.md`
- `risk-audit-checker-roadmap.md`
- `risk-audit-phase2-checker-implementation.md`

建议：

- `risk-audit-capability.md` 负责说“系统已经能做什么”
- `risk-audit-checker-roadmap.md` 负责说“下一步往哪里走”
- `risk-audit-phase2-checker-implementation.md` 负责说“第二批 checker 具体怎么做”
- `risk-audit-next-batch-checkers.md` 负责说“下一批新增 checker 应该如何收口与立项”
- `architecture/risk-audit-semantic-enhancement.md` 负责说“语义增强为什么不直接放进 checker，以及后续应加在哪一层”
- `architecture/risk-audit-embedding-pgvector-implementation-spec.md` 负责说“最终 embedding / pgvector 方案要怎么落成数据对象与服务”

### 重叠点 C：运行时边界

容易出现在：

- `risk-audit-runtime-boundary.md`
- `skills-vs-risk-checkers-boundary.md`

建议：

- 前者只讲运行时能力边界
- 后者只讲 `skills_dir` vs checker

### 重叠点 D：读者体验扩展

容易出现在：

- `risk-audit-capability.md`
- `reader-experience-capability.md`

建议：

- 所有读者体验扩展，统一以后者为准

---

## 5. 建议统一的核心术语

后续文档统一使用以下术语：

### 核心系统名

- 统一风险审查体系

### 核心交付物

- `ChapterRiskCard`
- `review_candidates_summary`
- `review_candidate_clusters`
- `audit_conclusion`

### 问题簇相关

- `cluster_title`
- `suggested_review_action`
- `review_priority`
- `cluster_status`

### 运行时语义

- `advisory-only`
- `checker roster`
- `artifact signals`
- `branch-level delivery`

---

## 6. 后续改动时的更新顺序建议

### 如果改 checker roster

至少同步更新：

1. `risk-audit-capability.md`
2. `risk-audit-checker-roadmap.md`
3. `risk-audit-phase2-checker-implementation.md`（如影响第二批 checker 路线）
4. `risk-audit-next-batch-checkers.md`（如涉及新增 checker 的立项边界）
5. `risk-audit-system-overview.md`（如成熟度发生变化）

### 如果改运行时架构

至少同步更新：

1. `risk-audit-runtime-architecture.md`
2. `risk-audit-runtime-boundary.md`
3. `skills-vs-risk-checkers-boundary.md`（如果涉及 `skills_dir`）

### 如果改交付字段

至少同步更新：

1. `risk-audit-capability.md`
2. `risk-audit-system-overview.md`
3. `risk-audit-checker-roadmap.md`（如影响路线判断）
4. `risk-audit-phase2-checker-implementation.md`（如影响第二批 checker 实施细节）
5. `risk-audit-next-batch-checkers.md`（如影响下一批 checker 的 signal / risk type 口径）

### 如果改样例小说结论链

至少同步更新：

1. `.omx/reports/sample-novel-current-conclusion.md`
2. `.omx/reports/sample-novel-phase2-offline-memo-20260430.md`（如 phase-2 离线结论发生变化）
3. `.omx/reports/sample-novel-phase2-db-blocker-20260430.md`（如阻塞条件/恢复步骤发生变化）
4. `docs/risk-audit-docs-index.md`（如导航入口变化）
5. `docs/README.md`（如主索引入口变化）

### 如果改读者体验规划

只优先更新：

1. `reader-experience-capability.md`

---

## 7. 建议的维护原则

1. **导航文档不承载实现细节**
2. **总览文档不承载字段清单**
3. **路线图文档不承载运行时边界**
4. **边界文档不承载产品路线**
5. **读者体验规划不回写到当前已实现能力文档**

---

## 8. 一句话总结

> 后续维护时，把“总览、能力、架构、边界、路线图、读者扩展”六层分开维护，就能显著降低文档失控和口径漂移风险。
