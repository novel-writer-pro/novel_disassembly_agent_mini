# AI 小说系统对标分析 / Benchmark

> 更新时间：2026-05-04  
> 参考来源以官方产品页面/帮助文档为主，重点比较“系统能力形态”，不是做一句话排行榜。

## 1. 对标对象（官方产品面）
- Sudowrite（AI fiction writing / story tools）
- Novelcrafter（Codex / Story Bible / planning-oriented writing）
- NovelAI（storytelling + lorebook + generation）
- Squibler（AI book writing workflow）
- Plot Factory（story planning + collaboration）

## 2. 我们当前做得好的地方
### 2.1 拆书 / 信息抽取
我们不只是“让模型写”，而是已经形成：
- facts
- retrieval
- graph/state/window
- branch report / QA context

这比很多偏创作器产品更像“小说知识中台”。

### 2.2 风险门控
我们在 `risk checker + semantic signal + review workflow` 上已经有明显系统化优势。  
多数通用创作器更强在写作体验，但不一定有：
- 可解释 risk card
- review cluster
- branch-level audit conclusion
- DB-backed review workflow

### 2.3 受控仿写
我们不是纯 prompt 拼接，而是：
- harness
- repair lanes
- long-book consistency diagnostics
- whole-book handoff / freeze governance

这比“单次生成器”更靠近可运营的长篇生产工具。

## 3. 对比矩阵（按能力形态）

| 维度 | 我们当前形态 | 头部创作器常见形态 | 结论 |
| --- | --- | --- | --- |
| 拆书 / 知识化 | 强，已有 facts / retrieval / graph / state / report | 多数更偏创作工作流，不一定有强结构化拆书中台 | 这是我们的核心优势 |
| 检索 / 上下文召回 | 中高，已具备 RRF + optional rerank + diagnostics | 强调写作时上下文调用，但不一定开放结构化诊断面 | 我们更可观测，可继续补 UX |
| 风险门控 / 审查 | 强，已有 risk checker / semantic signals / review workflow | 很多产品强在写，不强在可解释审查 | 这是商业化差异点 |
| story bible / codex / lorebook | 中，已有结构化知识层，但产品界面和交互还不如头部创作器顺手 | Novelcrafter / Sudowrite / NovelAI 在“作者视角知识组织”上更成熟 | 可较快逼近 |
| 仿写 / 续写受控性 | 中高，已有 harness / repair lanes / long-book diagnostics | 许多产品可写，但不一定具备多层 repair / governance | 我们骨架更系统 |
| whole-book orchestration | 中，已能 sandbox + provider-backed rerun | 头部产品更偏作者工作流和知识编排，而不一定有 release-gated system path | 我们更适合平台化 |
| 评估 / freeze gate | 高，已有 sample bundle / release gate | 大多数创作器不会把 eval/governance 暴露成正式流程 | 这是平台级能力优势 |
| 商业包装度 | 中低，系统能力强但市场叙事仍需继续收口 | 头部产品在价值主张与定位表达上更成熟 | 这是当前最值得补的短板 |

## 4. 目前还可以快速补强、逼近头部体验的部分
### 4.1 写作工作流体验
头部创作器通常在：
- writer UX
- story bible 交互
- planning flow
- scene-level editing ergonomics

上更成熟。

我们可以较快逼近的，不一定是 UI 花活，而是：
- 更稳定的 outline / next-chapter / whole-book handoff
- 更好的 sample-driven contract
- 更明确的 repair lane recommendation

### 4.2 retrieval/search 产品化
Sudowrite / Novelcrafter 类产品通常把“上下文召回”做得更贴近创作界面。  
我们当前主链更强在结构化，但可以快速补：
- vector/entity-exact lanes
- retrieval latency evidence
- 搜索结果的产品化摘要

### 4.3 whole-book 连续性证据
我们已经有骨架，但还缺“更多成功 provider-backed、跨多轮、跨更长样本”的证据密度。  
这是很快就能继续补强的地方。

## 5. 哪些已经做得好，哪些可以快速做好
### 已经做得好的
1. **拆书中台化**：不仅有输出，还有 retrieval / graph / state / report 闭环。  
2. **门控与审查体系**：risk checker + semantic signal + review workflow 非常接近“生产系统”而不是 demo。  
3. **受控仿写骨架**：repair lane / handoff / consistency diagnostics 已成体系。  
4. **治理与交接**：sample-based release gate、freeze policy、handoff docs 明显强于常见创作工具。  

### 可以快速做好的
1. **story bible / codex 产品层**：把现有结构化知识层包装得更像作者真正会天天用的内容控制面。  
2. **retrieval 产品体验层**：把现在强大的 diagnostics 进一步变成作者/编辑易懂的摘要与推荐。  
3. **样例与成功证据密度**：继续补 provider-backed / whole-book / risk branch 的真实成功样例。  
4. **商务材料**：把复杂架构翻译成客户能理解的场景价值与 ROI 语言。  

这些都是“低偏航、高收益”的补强，不会破坏当前核心思想。

## 6. 不应偏离的大方向
1. 不要退回成“只有一个聊天框的写作器”
2. 不要把 risk checker 主判断黑盒化
3. 不要为了短期演示牺牲可维护性与可解释性
4. 不要只卷 UI，而忽略中台能力与治理能力

## 7. 商业价值判断
### 最有价值的不是哪一项单点能力最好
真正有商业价值的是：
- 拆书
- 抽取
- 检索
- 风险门控
- 仿写
- 评估
- 交接

这些能力已经能组合成系统产品，而不是单个 AI 功能。

### 最适合先商业化的形态
1. 编辑/审稿中台
2. 小说 IP 研发辅助中台
3. 作者工作室知识与质量中台
4. 平台方的“创作运营基础设施”

### 商业上最容易被买单的能力包
1. **内容质量与风险控制**：直接对应编辑人力成本与事故成本。  
2. **知识化与检索**：直接提升创作/编辑/运营周转效率。  
3. **受控仿写与续写**：最接近“直接产能提升”，但前提是门控与一致性要到位。  
4. **平台级交接与治理**：对 B 端比“生成更炫”更重要。  

## 8. 下一阶段能力建设
- retrieval 向 vector/entity-exact 升级
- risk semantic 向长窗口 adjudication 升级
- whole-book 增加更多真实 provider-backed evidence
- 文档/治理继续产品化

## 9. 官方参考来源（访问时间：2026-05-04）
- Sudowrite Story Bible / feature docs  
  - https://docs.sudowrite.com/using-sudowrite/1ow1qkGqof9rtcyGnrWUBS/what-is-story-bible/jmWepHcQdJetNrE991fjJC  
  - https://docs.sudowrite.com/getting-started/dQph1snuwbfMWG9wRjsNug/features/dq7YUMNy5ZMvKUJiRAisyT
- Novelcrafter Codex / Series Codex / progression docs  
  - https://docs.novelcrafter.com/en/articles/8675743-the-codex  
  - https://docs.novelcrafter.com/en/articles/9387811-series-codex  
  - https://docs.novelcrafter.com/en/articles/8675593-progression-additions
- NovelAI Lorebook docs  
  - https://docs.novelai.net/en/text/lorebook
- Plot Factory official product / planner pages  
  - https://plotfactory.com/  
  - https://plotfactory.com/story-planner
- Squibler official AI writing pages  
  - https://www.squibler.io/?via=aicavo  
  - https://www.squibler.io/learn/software/best-ai-book-generators/
