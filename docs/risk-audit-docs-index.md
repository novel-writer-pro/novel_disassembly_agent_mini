# 风险审查文档导航

这份索引专门服务于 **统一风险审查体系**，把相关文档按用途整理出来，方便产品、研发、维护者快速进入上下文。

---

## 1. 最推荐的阅读顺序

### 面向产品 / 业务
1. [`./risk-audit-system-overview.md`](./risk-audit-system-overview.md)
2. [`./risk-audit-capability.md`](./risk-audit-capability.md)
3. [`./reader-experience-capability.md`](./reader-experience-capability.md)

### 面向架构 / 后端
1. [`./risk-audit-runtime-architecture.md`](./risk-audit-runtime-architecture.md)
2. [`./risk-audit-runtime-boundary.md`](./risk-audit-runtime-boundary.md)
3. [`./skills-vs-risk-checkers-boundary.md`](./skills-vs-risk-checkers-boundary.md)
4. [`./architecture/risk-audit-completion-status.md`](./architecture/risk-audit-completion-status.md)
5. [`./architecture/risk-audit-semantic-enhancement.md`](./architecture/risk-audit-semantic-enhancement.md)
6. [`./risk-audit-production-readiness.md`](./risk-audit-production-readiness.md)
7. [`./architecture/README.md`](./architecture/README.md)

### 面向规划 / 持续维护
1. [`./risk-audit-checker-roadmap.md`](./risk-audit-checker-roadmap.md)
2. [`./risk-audit-phase2-checker-implementation.md`](./risk-audit-phase2-checker-implementation.md)
3. [`./risk-audit-next-batch-checkers.md`](./risk-audit-next-batch-checkers.md)
4. [`./risk-audit-system-overview.md`](./risk-audit-system-overview.md)

---

## 2. 文档用途说明

### `risk-audit-system-overview.md`
总览文档。适合先建立全局认知：
- 当前成熟度
- 当前能力边界
- 当前交付物
- 当前如何评估

### `risk-audit-capability.md`
系统能力说明。适合回答：
- 当前系统已经能做什么
- 哪些 checker 已正式落地
- 哪些 checker 正在提质

### `risk-audit-runtime-architecture.md`
运行时架构说明。适合回答：
- 运行时分层
- checker 与 aggregator 在系统中的位置
- 风险交付链路

### `risk-audit-runtime-boundary.md`
运行时边界说明。适合回答：
- 什么属于运行时门控能力
- 什么不属于运行时能力

### `skills-vs-risk-checkers-boundary.md`
`skills_dir/` 与风险 checker 的职责边界。适合回答：
- `skills_dir/` 当前做什么
- risk checker 当前做什么
- 为什么门控不直接做成 skill

### `risk-audit-checker-roadmap.md`
checker 路线图。适合回答：
- 当前 checker roster
- 哪些处于成熟态
- 哪些仍在提质
- 下一步开发顺序

### `risk-audit-phase2-checker-implementation.md`
第二批 checker 技术路线。适合回答：
- plot / timeline / power 三类 checker 具体怎么补强
- 结构化信号、风险类型、降噪规则是什么
- 补到什么程度算可交付

### `risk-audit-next-batch-checkers.md`
下一批 checker 技术设计。适合回答：
- 下一批再扩哪些 checker 最值
- 新 checker 应保持什么边界
- 新 checker 应该依赖什么信号与输出什么风险类型

### `architecture/risk-audit-completion-status.md`
完成度 / 测试 / 使用说明文档。适合回答：
- 风险审查主链技术上是否已经完成
- 当前推荐怎么验证
- 当前如何使用主链
- 哪些属于第一阶段完成，哪些属于下一阶段

### `architecture/risk-audit-semantic-enhancement.md`
语义增强架构文档。适合回答：
- 为什么当前 checker 主链没有直接全量使用 embedding / LLM skills
- 语义增强应该加在哪一层
- 后续如何在不破坏可测试性的前提下增强风险审查质量
- 当前最终推荐的生产方案是什么

### `architecture/risk-audit-embedding-pgvector-implementation-spec.md`
embedding / pgvector 实施规格。适合回答：
- 最终方案应该如何落成代码与数据对象
- 哪些 checker 优先消费 embedding 结果
- signal store / link service / adjudication service 应该怎么拆

### `risk-audit-production-readiness.md`
正式生产收尾文档。适合回答：
- 现在离正式稳定生产还差什么
- 哪些是真实外部条件阻塞
- PostgreSQL / pgvector / provider / embedding 应该怎么验收

### `architecture/README.md`
架构专题总入口。适合回答：
- 当前有哪些架构专题文档
- 应该按什么顺序看风险审查主链架构
- 维护者/后端接手时从哪里进入

### `reader-experience-capability.md`
读者体验能力规划。适合回答：
- 踩雷预警
- 高压苦情
- 结尾崩坏
- 阅读跳转推荐


### `sample-novel-*` reports（位于 `.omx/reports/`）
样例小说结论链。适合回答：
- 当前样例小说的主结论是什么
- phase-2 离线结论到了什么程度
- 为什么真实 phase-2 复跑仍被数据库阻塞
- 数据库恢复后应该如何继续

### `risk-audit-mainline-verification-20260430.md`（位于 `.omx/reports/`）
风险审查主链验证快照。适合回答：
- 当前主链 checker roster 到了哪一步
- 最新验证基线是什么
- 当前文档治理与架构收口是否已经完成

---

## 3. 当前建议的使用方式

### 如果你只想回答“现在能力到哪了”
看：
- `risk-audit-system-overview.md`

### 如果你只想回答“运行时怎么跑”
看：
- `risk-audit-runtime-architecture.md`
- `skills-vs-risk-checkers-boundary.md`
- `architecture/risk-audit-semantic-enhancement.md`

### 如果你只想回答“接下来研发先做什么”
看：
- `risk-audit-checker-roadmap.md`
- `risk-audit-phase2-checker-implementation.md`
- `risk-audit-next-batch-checkers.md`
- `risk-audit-production-readiness.md`

### 如果你只想回答“读者侧以后怎么扩展”
看：
- `reader-experience-capability.md`

### 如果你要接手样例小说 phase-2 结论线
看：
- `.omx/reports/sample-novel-current-conclusion.md`
- `.omx/reports/sample-novel-first-10-risk-check-20260502.md`
- `.omx/reports/sample-novel-phase2-offline-memo-20260430.md`
- `.omx/reports/sample-novel-phase2-db-blocker-20260430.md`

### 如果你要接手当前风险审查主链交付状态
看：
- `.omx/reports/risk-audit-mainline-verification-20260430.md`

---

## 4. 一句话总结

> 如果风险审查体系继续扩展，这份索引应作为统一入口维护，避免文档散落后难以接手。
