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

### 面向规划 / 持续维护
1. [`./risk-audit-checker-roadmap.md`](./risk-audit-checker-roadmap.md)
2. [`./risk-audit-system-overview.md`](./risk-audit-system-overview.md)

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

### `reader-experience-capability.md`
读者体验能力规划。适合回答：
- 踩雷预警
- 高压苦情
- 结尾崩坏
- 阅读跳转推荐

---

## 3. 当前建议的使用方式

### 如果你只想回答“现在能力到哪了”
看：
- `risk-audit-system-overview.md`

### 如果你只想回答“运行时怎么跑”
看：
- `risk-audit-runtime-architecture.md`
- `skills-vs-risk-checkers-boundary.md`

### 如果你只想回答“接下来研发先做什么”
看：
- `risk-audit-checker-roadmap.md`

### 如果你只想回答“读者侧以后怎么扩展”
看：
- `reader-experience-capability.md`

---

## 4. 一句话总结

> 如果风险审查体系继续扩展，这份索引应作为统一入口维护，避免文档散落后难以接手。
