# Docs FAQ / Consolidation Guide

## 1. 为什么文档这么多？
因为系统当前不是一个单点功能，而是：
- 拆书中台
- 风险审查
- 仿写/生成
- 样例/治理
- 运维/交接

它天然比普通 SaaS 功能文档复杂。

## 2. 为什么不能简单删掉很多旧文档？
因为大量旧文档承载的是：
- 真实样例证据
- 历史决策背景
- 运行链路恢复信息

这些对维护和交接有价值。正确做法不是“全删”，而是：
- 建 canonical 入口
- 把 archive / evidence / strategy 分层
- 让读者先看到正确入口，再决定是否深入历史层

## 3. 当前文档最容易让人迷失的地方
1. index 重复
2. 历史文档与当前 canonical 文档并列
3. 技术文档、产品文档、商务叙事混在一起

## 4. 当前的整理原则
- README 只做分流与总导航
- roles/tracks/architecture 负责读者视角入口
- features/strategy/whitepaper 负责当前阶段治理与叙事
- examples/evidence/.omx reports 负责事实与历史证据

## 5. 什么时候该新建文档？
- 新能力方向 / 新叙事 / 新治理机制：新建
- 只是“找不到入口”：优先改索引
- 只是一次临时验证：优先放 evidence / sample，再决定是否升级

## 6. 交接时最关键的文档组合
1. `docs/release-handoff-brief.md`
2. `docs/features/architecture-mainline-checkout-20260504.md`
3. 对应 capability checkout
4. 对应 sample / evidence

## 7. 最后目标
不是让文档变少，而是让文档：
- 更可导航
- 更少重复
- 更强可维护性
- 更能支撑下一轮优化与商业化表达
