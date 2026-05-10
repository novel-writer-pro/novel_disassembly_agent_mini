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

## 适合谁看
- **架构师 / 后端负责人**：先看 [architecture.md](./architecture.md)
- **直接开发者**：先看 [development-guide.md](./development-guide.md)
- **接手人 / 审阅者**：再看 [critical-open-points.md](./critical-open-points.md)

## 相关上游产物
- `docs/whole-book-imitation-integration-quickstart.md`
- `docs/imitation-next-dev-handoff.md`
- `.omx/plans/prd-book-deconstruction-quick-deep-profiles.md`
- `.omx/plans/test-spec-book-deconstruction-quick-deep-profiles.md`
