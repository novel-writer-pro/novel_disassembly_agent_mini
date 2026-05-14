# 底座优化优先级与 ROI 预研 + 落地计划 — 2026-05-12

## TL;DR

> **Quick Summary**: 对 LLM / Embedding / 分词词典 / Rerank 做一次优先级预研,结论是底座不是当前主瓶颈;即便动底座,按"白捡 → 换开源 SOTA → 最后才评估微调"的顺序推进,并且明确不走商业 API、不自研 embedding 微调。
>
> **Deliverables**:
> - 调研结论文档(本文档)
> - 3 个 P0 落地选项,任选其一推进
> - 一份底座决策复核清单,保证"换模型"决策有证据链
>
> **Estimated Effort**: Short(1-2 周分流)
> **Parallel Execution**: NO — 决策型调研,决策后再分流执行
> **Critical Path**: 此预研 → 用户选 P0 选项 → 启动对应实施计划

---

## Context

### Original Request
用户(项目负责人)希望参谋四件事:
1. 当前拆书/风险检查/仿写结合行业 SOTA 已经够了,是否该转向底座能力提升?
2. 非要提升底座,各项的优先级和性价比?
3. 当前 LLM/embedding 是否改用成熟商业 embedding 即可?还是非要自己微调?
4. GitHub 上的 AI 写小说项目有哪些精华可以吸收?

### 预研方法与证据强度

| 来源 | 说明 | 置信度 |
|------|------|--------|
| 本地代码扫描 | `novel_analyzer/embedding/`、`rerank/`、`services/domain_dictionary_service.py`、`services/retrieval_service.py`、`.env.example` | 高 |
| 本地文档回溯 | `ai-novel-capability-scorecard.md`、`foundation-optimization/*`、`risk-audit-embedding-pgvector-implementation-spec.md`、`independent-agent-knowledge-and-retrieval.md` | 高 |
| 网络搜索(2026-05) | C-MTEB 榜单、商业 embedding 定价、GitHub AI 小说项目 | 中(搜索快照有时效性) |
| 预期的并行后台调研 | `librarian` × 2 + `explore` × 1 均经 7 次模型降级最终落到 nano 模型,返回空 | 无 |

**告诫**:网络搜索部分的具体 MTEB 分数、价格、star 数会漂移。做"换模型"决策前,请复核当天的 C-MTEB / MTEB-multilingual 榜单 + 官方定价页。

### 本地底座现状(事实核对)

**Embedding**
- 模型:`BAAI/bge-m3`,ONNX,dim=1024,pooling=CLS,max_length=2048
- 来源:`novel_analyzer/embedding/service.py` 的 `OnnxBgeEmbeddingProvider`;`.env.example:18-21`
- 存储:pgvector

**Rerank**
- ONNX cross-encoder(bge-reranker-v2-m3 级别),max_length=512
- 来源:`novel_analyzer/rerank/service.py` 的 `OnnxCrossEncoderRerankProvider`
- 有 `DisabledRerankProvider` 作为 fallback

**分词 / BM25**
- 检索链路:FTS + similarity + like + keyword + entity_exact + vector → RRF → rerank
- BM25 分词:**使用默认 FTS,jieba 未加载**
- `DomainDictionaryService` 已实现并在 materialization 后更新 `.cache/novel-analyzer/domain-dict.txt`(源自 `GraphNode` + `FactRecord`)
- **关键不对称**:词典在持续生成,下游 BM25 没真正消费

**LLM**
- 生产配置:`deepseek-v4-flash` + `NOVEL_ANALYZER_USE_MERGED_STAGES=true`
- Stage merging 5→3,单章延迟 -40%
- Complexity router 已启用
- Phase 1-4 完成:adaptive context、foreshadowing lifecycle、arc memory、entity resolution、causal graph、confidence calibration、self-eval loop

---

## Work Objectives

### 核心目标
为"接下来 1-2 个月要不要动底座"提供证据支持的决策,并把决策落成可执行的行动计划。

### 四个预研问题的结论

#### Q1. 底座是否是当前主瓶颈?→ **不是**

证据:

1. **能力评分卡自述**(`docs/product/ai-novel-capability-scorecard.md`)
   - retrieval / QA:4/5,瓶颈在"rerank 真正改序证据、更多 query bank",**非底座本身**
   - risk semantic:3.5/5,瓶颈在"长窗口 linking / quality benchmark"
   - whole-book imitation:3/5,瓶颈在"真库成功样例密度、多轮稳定性"
   - 评分卡最后:"**短期最值得继续投入的,是 retrieval 提升 + author-facing 知识组织层 + more real evidence**"

2. **RRF 稀释效应**:embedding 只是 6 路召回中的 1 路,RRF 归一 + rerank 重排后,embedding 本身 +15% 的提升,净传递到下游往往 <5%。已进入收益递减区。

3. **对比 GitHub 同类项目**(见 Q4):大多数是提示词壳。本项目差异化在工作流结构,不在 embedding 选型。

**更应投入的三件事**(ROI 降序):

| # | 方向 | 为什么 |
|---|------|--------|
| 1 | Whole-book 真书到完本的成功样例密度 | 评分 3/5,商业化决定性 |
| 2 | Story bible 产品化消费面 | 数据已有,缺产品层 |
| 3 | retrieval live route benchmark | 低成本,给"要不要动底座"决策前置 |

#### Q2. 非要动底座,优先级与性价比

| 级别 | 动作 | 成本 | 收益 | 性价比 |
|------|------|------|------|--------|
| **P0** | domain-dict 真接入 BM25(jieba `load_userdict`) | 1-2 天 + 回归 | 专有名词 BM25 召回 +20-30%,ClaimGrounding +10-15% | ★★★★★ |
| **P1** | bge-m3 → Conan-Embedding-v2 或 Qwen3-Embedding-4B | 1 周(ONNX 导出 + pgvector 维度迁移 + 回归) | C-MTEB +8-12%,落地净增益估 +3-6% | ★★★☆☆ |
| **P2** | Rerank 升级到 Qwen3-Reranker-4B | 3-5 天 | top-k +5-10%,净增益 <3% | ★★☆☆☆ |
| **P3** | 自研微调 embedding | 1-2 个月 + 持续运营 | 不稳定,过拟合风险 | ★☆☆☆☆ 不推荐 |

**P0 是白捡**:词典已在生成,只差临门一脚;实施路径见 `docs/foundation-optimization/embedding-rerank-dictionary-guide.md` §1.4-1.5。

**P1 的坑**:
- Conan-v2 dim=1792,Qwen3-Embedding-4B dim=2560,bge-m3 dim=1024 — **pgvector 列需迁移,旧向量需重跑**
- 必须回滚预案(双写 30 天 + 一键切回)
- 灰度:10% → 50% → 100%,每档观察 Recall@5 / MRR

#### Q3. 商业 API / 自研微调?

**结论**:
- 商业 API:**当前不推荐**
- 自研微调:**当前不推荐**
- 推荐路径:继续走开源 SOTA(bge-m3 → Conan-v2 / Qwen3),保持本地 ONNX 部署

**反对商业 API**:

| 维度 | 说明 |
|------|------|
| 数据规模惩罚 | 100 万字 ≈ 150 万 token,chunk+回填后实际 5-10x,100 本 $50-1000。本地 ONNX $0 |
| 向量数据主权 | 向量是中台资产,第三方托管 = 网络往返 + 厂商下线风险(2025-2026 已有厂商调价/停服) |
| 中文能力 | OpenAI-3-large、Voyage-3、Cohere-v3 都是多语言模型,中文 MTEB 打不过 Conan-v2/Qwen3/BGE |
| 延迟 | 商业 API P95 约 300-500ms,本地 ONNX 可压 20-50ms |

唯一适用场景:未来做 SaaS 多租户托管 + 愿意成本透传客户。

**反对自研微调**:

| 维度 | 说明 |
|------|------|
| 数据不足 | 需 10K+ 高质量标注对,目前没有 |
| 全流程成本 | 训练 + 评测集标注 + 部署 + 运营 ≥ 换更好的开源基座 |
| 基座快速迭代 | 开源 SOTA 每 3-6 个月一代,微调 v1 易被超越 |
| 过拟合 | 训 5 本仙侠后,都市/科幻可能不升反降 |
| 评测集成本 | 光标 100+ query 成本已高于微调本身 |

**例外**:真正值得自研的是 **rerank**,不是 embedding。但也建议等 P0/P1 完成后再评估。

**商业/开源对照(2026-05 快照,请复核)**

| 模型 | 维度 | 价格 | 中文 | 建议 |
|------|------|------|------|------|
| OpenAI text-embedding-3-large | 3072 | ~$0.13/M | 中 | 否 |
| Voyage-3 | 1024 | ~$0.06/M | 中 | 否 |
| Jina-embeddings-v3 | 1024 | ~$0.02/M | 中 | 备选 |
| Cohere embed-multilingual-v3 | 1024 | ~$0.10/M | 中 | 否 |
| 阿里 DashScope text-embedding-v3 | 1024 | ~¥0.0005/1k | 强 | 国内场景备选 |
| **Conan-Embedding-v2** 开源 | 1792 | $0 | C-MTEB SOTA(2026-01) | **推荐** |
| **Qwen3-Embedding-4B/8B** 开源 | 2560/4096 | $0 | MTEB multilingual #1 | **推荐** |
| bge-m3(当前) | 1024 | $0 | 中上 | 基线 |

#### Q4. GitHub AI 写小说项目可吸收的精华

**值得深研 (★★★)**

| 项目 | 链接 | 为什么 |
|------|------|--------|
| lingfengQAQ/webnovel-writer | `https://github.com/lingfengQAQ/webnovel-writer` | 基于 Claude Code 的长篇网文(200 万字量级),专解决"遗忘/幻觉",中文场景最像本项目架构 |
| AutoNovelAI(AutoGen 多智能体) | AgentScope 生态文章 | 故事构思/大纲/分章/写作/一致性审查多 agent,其一致性审查可对标本项目 checker roster |
| GOAT-AI-lab/GOAT-Storytelling-Agent | `https://github.com/GOAT-AI-lab/GOAT-Storytelling-Agent` | 虽走微调路线(GOAT-70B),但 storytelling 循环结构值得一看 |

**值得看但不深研 (★★)**
- `datacrystals/AIStoryWriter`(提示词多步 pipeline)
- `Doriandarko/gemini-writer`(单模型 agent)
- `RecurrentGPT`(2023 原型,ArcMemory 已覆盖)

**跨领域借鉴 (★★★)**

| 项目 | 借鉴点 |
|------|--------|
| HiAgent2024/HiAgent | 分层工作记忆,给 ArcMemory v2 设计参考 |
| agiresearch/A-mem | Agentic memory,借鉴进 AuthorKnowledgeService |
| kingjulio8238/Memary | agent 记忆层,对比 foreshadowing 状态机 |

**不建议做**:
- 读"单文件 AI 写小说 demo"(多为 prompt 壳)
- 照抄 AutoGen/CrewAI agent 协作框架(本项目已更领域化,引入反而降维)

**反向验证**:AgentScope 圈"7 大范式重构 AI 长篇小说写作"文章的观点 = 从提示工程到可靠工作流,**本项目已经在这条路上**。对照读可验证"没漏范式"。

### 最终决策表

| 方向 | 优先级 | 周期 | ROI | 前置条件 |
|------|--------|------|-----|----------|
| Whole-book 3-5 本真书到完本(3→4) | P0 | 3-4 周 | 极高 | provider 稳定 |
| Story bible 产品化消费面 | P0 | 2-3 周 | 高 | — |
| retrieval live route benchmark | P0 | 1 周 | 高(决策前置) | — |
| jieba + domain-dict 接入 BM25 | P1 | 2 天 | 中高(白捡) | — |
| 研读 webnovel-writer + AutoNovelAI 对标备忘 | P1 | 1 周 | 中 | — |
| bge-m3 → Conan-v2 / Qwen3 | P2 | 1 周 | 中 | benchmark 有净收益证据 |
| Rerank → Qwen3-Reranker | P3 | 3-5 天 | 低 | P1/P2 完成 |
| 商业 embedding API | 不做 | — | 负 | — |
| 自研微调 embedding | 不做 | — | 负 | — |
| 自研微调 rerank | 观察 | — | 待评估 | P0/P1 完成 + 有标注 pair |

### Must Have
- 本预研文档在 `.sisyphus/` 下完整留档
- 三个 P0 建议选项明确到"启动 1 周就能看到结果"
- 决策复核清单明确"没有哪些证据就不该动底座"

### Must NOT Have (Guardrails)
- 不在本文档里立刻触发换 embedding 基座的实施 — 这需要先跑 benchmark
- 不直接改生产配置 — 所有切换要走灰度
- 不把"做调研"本身错写成"做实施"
- 不做商业 embedding 迁移的技术实施
- 不做自研 embedding 微调的训练 pipeline 设计

---

## Verification Strategy

本文档是**决策记录**,不是代码实施。验证点:

- **Infrastructure exists**: N/A(非代码任务)
- **自动化测试**: 无
- **QA Policy**: 每个结论都必须有 **来源引用**(文件路径或网络搜索快照时间);用户读完应能独立判断每个结论的证据强度

---

## TODOs

- [ ] 1. **决策:选择 P0 起手动作**

  **What to do**:
  - 由项目负责人从以下三选一并回复:
    - **选项 A — retrieval live route benchmark**(1 周,低风险,产出当前底座真实 Recall@5 / MRR / 延迟,决定是否动底座)
    - **选项 B — jieba + domain-dict 接入**(2 天,白捡,词典已在生成只差加载)
    - **选项 C — 深研 webnovel-writer 架构并写对标备忘**(1 周,产品视角补强,产出 `docs/product/webnovel-writer-benchmark.md`)
  - 选定后,由 Prometheus(或相应 planner)为该选项生成独立的实施计划

  **Must NOT do**:
  - 不在未选定前就并行启动多个
  - 不跳过选择直接进入实施

  **Acceptance Criteria**:
  - [ ] 负责人明确回复选项字母
  - [ ] 对应的实施计划已写入 `.sisyphus/plans/`

  **Commit**: NO(决策条目)

- [ ] 2. **把本预研迁移到 `docs/foundation-optimization/`**

  **What to do**:
  - 由 Sisyphus / build agent 把本文档复制到 `docs/foundation-optimization/priority-and-roi-research-20260512.md`
  - 在 `docs/foundation-optimization/README.md` 中追加本文档的入口链接
  - Prometheus 不执行此任务(受 `.sisyphus/` 路径约束)

  **Must NOT do**:
  - 不修改内容,只做文件搬运
  - 不替换现有 `embedding-rerank-dictionary-guide.md`,两者并存

  **Acceptance Criteria**:
  - [ ] `docs/foundation-optimization/priority-and-roi-research-20260512.md` 存在且与本文档内容等价
  - [ ] `docs/foundation-optimization/README.md` 包含该文档的入口

  **Commit**: YES
  - Message: `docs(foundation-optimization): record embedding/rerank/dict priority research`
  - Files: `docs/foundation-optimization/priority-and-roi-research-20260512.md`、`docs/foundation-optimization/README.md`

- [ ] 3. **复核清单归档**

  **What to do**:
  - 把"换 embedding 基座的决策复核清单"单独抽出(见本文档 §复核清单)
  - 放到 `docs/foundation-optimization/embedding-migration-checklist.md`
  - 未来任何"换基座"PR 都必须勾选完这份清单

  **Must NOT do**:
  - 不把清单嵌入现有 guide — 独立文件便于后续 PR 模板引用

  **Acceptance Criteria**:
  - [ ] 文件存在
  - [ ] 在 README 中链接

  **Commit**: YES
  - Message: `docs(foundation-optimization): add embedding migration checklist`

---

## 决策复核清单(换 embedding 基座前必查)

> 做"换 embedding 基座"决策前,以下证据必须在手。缺一就不动。

- [ ] retrieval live route benchmark 结果(当前 Recall@5 / MRR 基线数字)
- [ ] 评测集(≥100 query,覆盖 ≥3 本代表性小说)
- [ ] 至少一次候选开源新基座的离线对比(同评测集跑 Recall@5)
- [ ] pgvector 维度迁移的 dry-run SQL(能在 staging 跑通)
- [ ] 回滚预案文档(双写期、回滚触发阈值、一键切回开关位置)
- [ ] 灰度计划(10% → 50% → 100% 每档观察指标与停止条件)

**没有这些证据,就不要动 embedding 基座**,否则容易陷入"换了但讲不清楚为什么更好"。

---

## 开放问题(写给未来的自己)

- [ ] **评测集缺口**:当前无人工标注的 Chinese novel retrieval benchmark(query → relevant chapters)。这是阻塞"换模型能否拿到净收益"决策的关键。100 query × 3 本小说约 2-3 人天标注量。
- [ ] **长窗口 linking ground truth**:risk semantic 从 3.5 → 4 的关键数据是什么?需要专项设计。
- [ ] **pgvector 维度迁移策略**:如果真换到 Conan-v2(1792) 或 Qwen3-4B(2560),双写迁移 SQL/流程需要一份 runbook。
- [ ] **商业化成本分摊**:未来 SaaS 多租户,embedding 成本是自研摊销还是透传客户?此决策会回过头影响"商业 API 是否可用"。

---

## Commit Strategy

本文档本身在 `.sisyphus/` 下,不进 git(由 Prometheus 维护)。
TODO 2 / TODO 3 的搬运动作产生的提交按标准单任务提交原则走。

---

## Success Criteria

- [ ] 本预研文档保存成功
- [ ] 用户能从三个 P0 选项中明确选一
- [ ] 如果用户同意搬运,TODO 2 / TODO 3 完成
- [ ] 后续任何"换 embedding"的 PR 都能引用复核清单

---

## 附录 A:本轮后台调研失败记录

为未来复现保留:

- 3 个 `librarian` / `explore` 后台任务全部启动成功
- 经历 7 次模型降级:`claude-sonnet-4-6 → gpt-5.4-mini-fast → qwen3.5-plus → minimax-m2.7-highspeed → minimax-m2.7 → claude-haiku-4-5 → gpt-5.4-nano`,前 6 档均 "Model not found"
- 最终 `gpt-5.4-nano` 上"完成"但返回空结果
- 改走本地代码实证 + 网络搜索 + 本地文档回溯

**经验**:调研依赖多 agent 综合判断 + 本地 model routing 不稳定时,优先走 **本地扫描 + 受控网络搜索**,不要无限等 agent。
