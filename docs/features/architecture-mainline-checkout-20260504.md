# Architecture Mainline Checkout — 2026-05-04

## 1. 本轮范围
- 主线能力：retrieval / risk semantic / whole-book imitation / eval governance / docs IA
- 关联真实样例：
  - risk fresh10 branch: `62e636f0-c901-4167-aa1c-aff3da9c83ef`
  - run: `ac9449b9-7326-474f-bb72-4416375a7491`
- 目标用户：
  - 写作工作台用户
  - 风险审查维护者
  - 仿写系统接入者
  - 后续接手开发者

## 2. 当前已完成
### 2.1 retrieval / QA
- 已有多路召回 + RRF + optional rerank 的主链结构。
- `search_branch()` 仍保持 QA/search 兼容。
- `search_branch_with_diagnostics()` 已提供 raw/reranked/latency/route observability。

### 2.2 risk semantic
- canonical key / evidence reason / candidate-linking 证据已落地。
- checker 主判断仍未被黑盒模型接管，保持可解释。
- 真实 sample branch report 已在 legacy review schema 与 migrated schema 下都验证可导出。

### 2.3 whole-book imitation
- repair-lane diagnostics 与 long-book consistency diagnostics 已进入 whole-book sandbox 主链。
- fresh provider-backed rerun 成功，表明 whole-book 真调用路径不是理论设计，而是已被实证打通。

### 2.4 eval / governance
- cross-lane sample bundle / freeze policy / release gate 已落地。
- whole-book / risk / retrieval 的样例与 handoff 文档已可对照回归。

### 2.5 文档治理
- 新增 feature checkout 体系。
- 新增产品战略 / 系统蓝图 / 白皮书骨架。
- fresh provider rerun 与 sample branch post-migration report 已固化为仓库样例，而不是只留在 `/tmp`。

## 3. 当前未完成
### 3.1 retrieval
- 还没有把 vector/entity-exact 路线接进当前 RRF 主链。
- live PostgreSQL retrieval 仍缺一轮更系统的 latency profiling。

### 3.2 risk semantic
- 目前更强的是“语义信号 + 证据 pack”，还不是全自动高置信 adjudication。
- 仍缺跨更长章节窗口的 linking/cluster质量评估。

### 3.3 imitation / generation
- provider 可用，但多轮/长书级稳定性证据仍偏少。
- 当前 still sandbox-oriented，尚未把生成正文正式写入 live artifact 主链。

### 3.4 docs / product
- 文档入口已经更清晰，但仍需要持续减少重复口径。
- 还缺针对销售/合作方的更图表化版本资料。

## 4. 预期效果
### 用户/业务侧
- 写作者与编辑能更快判断“系统现在能做什么、不能做什么”。
- 接入方能拿到更稳定的 report / sample / freeze 口径。
- 商务侧能更清楚解释本系统不是“通用写作玩具”，而是“可审计、可运营的 AI 小说系统中台”。

### 技术侧
- 核心主链更可观测。
- 真库样例复验链更闭环。
- 遗留 DB schema 不再靠人工记忆处理。

### 运维/交接侧
- 当前能力、证据、风险、下一步都能从 checkout 与战略文档快速定位。

## 5. 解决的问题
- 之前：文档多而散，真实进展只能从对话或 /tmp 推断。
- 现在：形成 docs IA + tracked samples + feature checkout + self-check migration path。
- 仍残留：whole-book 样例/风格债较多，部分长文档仍有重复叙述。

## 6. 测试 / 评估状态
- targeted regression：retrieval / QA / risk signal / whole-book / eval governance 已通过。
- fresh provider rerun：成功。
- fresh branch report：成功。
- DB migration/self-check：真实 PG 已验证。
- 结论：当前主链达到“可持续优化、可维护、可交接”的标准。

## 7. 下一步闭环
### 必做闭环
1. retrieval 增补 vector/entity-exact lanes 与 live latency evidence。
2. risk semantic 增补长窗口 linking / cluster quality evidence。
3. whole-book 增补更多 provider-backed 多轮样例。

### 可快速补齐
1. 更统一的 docs 去重与 FAQ 化。
2. 更结构化的商务/白皮书图表版。
3. 关键 sample export 再增加 CLI smoke 自动化。

### 中期优化
1. 把 generation 从 sandbox 提升到受控 live artifact lane。
2. 把 review / risk / imitation 的统一运营看板指标沉淀出来。
3. 把 retrieval/search 评估与 release gate 完整联动。

## 8. 结论
当前系统最重要的价值不在“能生成一段小说”，而在：
- 它已经具备拆书、抽取、风险门控、仿写、交接、回归、自检的系统化骨架；
- 它正在从“功能集合”收口成“可维护、可演进、可商业化的 AI 小说系统中台”。
