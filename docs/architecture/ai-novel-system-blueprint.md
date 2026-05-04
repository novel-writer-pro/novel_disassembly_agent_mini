# AI 小说系统蓝图 / System Blueprint

## 1. 北极星方向
系统的核心方向不是做一个单点的“AI 写作按钮”，而是做一个：

- 可拆解
- 可理解
- 可检索
- 可门控
- 可仿写
- 可运营
- 可持续优化

的 AI 小说系统中台。

## 2. 五层架构
### 2.1 内容理解层
- chapter intake
- fact extraction
- evidence binding
- retrieval materialization
- graph/state/window materialization

### 2.2 风险与审查层
- checker contracts
- semantic signal store / link / cluster
- review workflow
- branch report / audit conclusion

### 2.3 生成与仿写层
- chapter imitation
- harness controller
- repair lanes
- whole-book orchestration
- long-book consistency diagnostics

### 2.4 治理与评估层
- sample bundles
- freeze policy
- release gates
- readiness / handoff / coverage docs

### 2.5 运营与接入层
- CLI
- API
- exports / samples
- docs IA / release handoff / product whitepaper

## 3. 核心设计原则
1. **规则优先，可解释优先**：risk checker 不直接让模型吞掉主判断。
2. **检索与生成解耦**：QA/search 的 rerank 不直接侵入 risk checker。
3. **能力逐层升级**：先可运行，再可观测，再可治理，再可规模化。
4. **文档即运营面**：架构、样例、handoff、whitepaper 都是产品的一部分。

## 4. 未来优化方向
- retrieval：vector/entity-exact + richer ranking
- risk：better long-window semantic adjudication
- imitation：更多 provider-backed 长书样例与闭环
- governance：把 release criteria 进一步产品化 / dashboard 化
