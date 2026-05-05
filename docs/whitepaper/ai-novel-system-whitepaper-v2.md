# AI 小说系统白皮书 v2（对外叙事版）

## 1. 一句话定位
我们做的不是“AI 帮你写一段小说”的工具，而是一个围绕小说生产全链路的 AI 系统中台：
从拆书、抽取、检索、风险门控，到受控仿写、评估治理与运营交接，形成可持续优化的内容基础设施。

## 2. 为什么这个方向更有价值
传统 AI 写作产品往往解决的是“生成速度”，但长篇小说真正高成本的问题在于：
- 长文本信息不可控
- 连续性容易失真
- 编辑与作者缺少统一证据面
- 生成内容缺乏门控与治理

因此，真正高价值的不是“多写一点”，而是“写得更可控、更可复盘、更可运营”。

## 3. 我们的系统结构
### A. 内容理解中台
- 章节拆解
- facts / retrieval / graph / state
- branch / chapter / QA / report 导出

### B. 风险与审查中台
- risk checker
- semantic signal / linking / clustering
- DB-backed review workflow

### C. 受控生成中台
- chapter imitation
- harness / repair lanes
- whole-book orchestration
- consistency diagnostics

### D. 治理与交接中台
- sample bundle
- freeze gate
- smoke path
- migration/self-check
- docs/hand-off/checklist

## 4. 与头部 AI 小说产品相比，我们的独特价值
### 我们更强的地方
- 风险门控和可解释审查
- 拆书中台与知识化能力
- 受控仿写的系统骨架
- 运维、自检、迁移、交接能力

### 我们还需快速补强的地方
- story bible / codex 级产品体验
- retrieval 的更强召回层
- whole-book 的更多真实运行样例
- 商务包装和客户场景图表化

## 5. 商业场景
1. 编辑/审校中台
2. 作者工作室知识与质量中台
3. 平台级创作运营基础设施
4. IP 开发前置分析与续写支持系统

## 6. 为什么它是“基础设施”，不是“功能插件”
因为它已经覆盖：
- 数据层
- 审查层
- 生成层
- 评估层
- 运维层
- 交接层

这意味着它可以被平台、工作室、编辑团队持续复用，而不是一次性玩具。

## 7. 当前阶段结论
当前系统已经具备：
- 真库可验证
- whole-book provider path 可跑通
- cluster review schema 可升级可自检
- 文档/样例/交接机制成体系

下一阶段重点不应偏航，而应继续：
- 强化 retrieval 与 author-facing 知识组织层
- 增加更多真实 long-book evidence
- 提升平台化与商业表达能力
