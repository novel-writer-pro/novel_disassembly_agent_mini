# 拆书加速优化文档入口

> 这组文档描述“小说拆书双档产物与加速主线”的架构约束、实现顺序、验证要求与剩余关键风险。

## 文档清单

1. [architecture.md](./architecture.md)
   - Quick / Deep 双档的系统设计
   - canonical chapter artifact 与 enrichment 的边界
   - reader isolation、stale guard、benchmark 模型

2. [development-guide.md](./development-guide.md)
   - 开发落地顺序
   - 代码触点
   - 测试矩阵
   - 开发时最容易踩的坑

3. [critical-open-points.md](./critical-open-points.md)
   - 当前方案下仍需重点盯防的关键点
   - 已收敛 vs 尚未完全闭合的问题
   - 后续是否需要再开新工作流的判断依据

4. [benchmark-baseline-20260511.md](./benchmark-baseline-20260511.md)
   - 当前 canonical 默认读路径的基线 benchmark
   - 后续 Quick / Deep 优化的对照零点

5. [development-log-20260511.md](./development-log-20260511.md)
   - 本轮 regression / benchmark / docs lane 的开发记录

6. [usage-log-20260511.md](./usage-log-20260511.md)
   - 本轮命令、验证动作与使用证据

7. [user-manual.md](./user-manual.md)
   - 当前拆书加速优化版本的用户使用说明
   - 已落地能力 / 未落地能力 / 推荐实跑顺序 / 验证口径

8. [version-diff.md](./version-diff.md)
   - 旧版拆书 vs 新版加速拆书的差异说明
   - 覆盖使用差异 / 能力差异 / 恢复差异 / 适用场景差异

## 适合谁看
- **架构师 / 后端负责人**：先看 [architecture.md](./architecture.md)
- **直接开发者**：先看 [development-guide.md](./development-guide.md)
- **接手人 / 审阅者**：再看 [critical-open-points.md](./critical-open-points.md)

## 相关上游产物
- `docs/whole-book-imitation-integration-quickstart.md`
- `docs/imitation-next-dev-handoff.md`
- `.omx/plans/prd-book-deconstruction-quick-deep-profiles.md`
- `.omx/plans/test-spec-book-deconstruction-quick-deep-profiles.md`

9. QA 分层证据与保守回答策略
   - 已补 `chapter/window/graph` 三层证据面，以及按问题类型做 rerank / 降级的 QA 精化路径

10. 卫图真实旧基线 artifact
   - `docs/deconstruction-acceleration/benchmarks/weitu-baseline-20260511.md`

11. funded-provider 真实对照 runbook
   - `docs/deconstruction-acceleration/funded-benchmark-runbook.md`
