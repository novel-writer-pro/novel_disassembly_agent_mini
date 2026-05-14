# Kernel vs SOTA Gap Assessment — 2026-05-14

> **范围**:novel-analyzer 内核能力(60 个 service + retrieval/embedding/rerank + LLM 编排)对照 2025-2026 SOTA 的横向评估。
> **目标**:在外部对接(Dify/n8n/Letta/...)展开**之前**,把内核优先级排清楚。
> **不做**:具体实施;仅给"差距评分 + 优先级 + 推荐路径"。

---

## TL;DR

| 域 | 当前能力(0-10) | 离 SOTA 距离 | 1 个月内可动的 P0 |
|---|---|---|---|
| 1. 检索(retrieval) | 7 | ~1 档 | **真正激活 jieba 词典 + 加 contextual-retrieval 前缀** |
| 2. RAG QA(防剧透/分支 QA) | 6.5 | ~1 档 | **query expansion 链路接 anti-spoiler 时间窗** |
| 3. 仿写(章/整本) | 6 | ~1.5 档 | **Loom carry-over 从 shadow → enabled 真跑 20 章对照** |
| 4. Loom 信号 | 6.5 | ~1 档 | **Reward model 真用 pairwise 数据训一次** |
| 5. 风险审计 | 6 | ~1.5 档 | **risk_audit_service 拆分(2156 行 → 4 子服务)+ 语义触发器从规则升 LLM-judge** |
| 6. 读者模拟 | 5.5 | ~2 档 | **persona 4 视角对真实读者反馈做相关性回归** |

**主结论**:内核**不是"差很多"而是"差关键的最后一档"**——多数模块在 4-7 分之间,SOTA 在 7-9 分之间。差距集中在 4 件事:

1. **大 service 文件没拆**(risk_audit 2156 行 / imitation_harness 1851 行 / novel_assistant 1639 行 / analysis 1567 行) → 阻碍每一项后续优化
2. **shadow 模式下的 Loom/Reward 没真跑过对比实验** → 信号在,但闭环没合
3. **检索链路上的 jieba 领域词典生成了但没真消费** → BM25 召回率被低估
4. **风险/QA 触发器很多还是规则,没升 LLM-as-judge** → 长窗语义无法下沉

---

## 1. 评估方法

### 1.1 评分锚点

每个域用 0-10 分,锚点定义:

| 分数 | 含义 |
|---|---|
| 9-10 | 头部/SOTA(论文+benchmark 双双佐证) |
| 7-8 | 主流 production 水准(对标 Dify/LlamaIndex/Letta) |
| 5-6 | 工程跑得通,信号能用,但闭环没合 |
| 3-4 | 单点 PoC,缺评估 |
| 0-2 | 没做或仅 stub |

### 1.2 SOTA 参考点(仅 2024-2026)

精简到每域 3-5 条:

- **检索**:RAPTOR(EMNLP 2024 hierarchical clustering)、Contextual Retrieval(Anthropic 2024 chunk 前置上下文)、GraphRAG(MSFT 2024 实体图谱召回)、BGE-M3(2024 多向量+稀疏+稠密一体)
- **RAG QA**:NarrativeQA / NovelQA / LongBench v2(长篇 QA benchmark)、FActScore(原子事实校验)、TimeQA(时间约束 QA)
- **仿写/续写**:Re3(Yang 2022 plan-write-revise)、RECURRENTGPT(2023 长篇外存)、Doc(Yang 2023 outline-conditioned)、LongLaMP(2024 个人化长文)
- **Loom/规划**:MCTS-Story(2024)、Plot Writer 系列、Dramatron(DeepMind)
- **风险/一致性**:FActScore、SelfCheckGPT(EMNLP 2023)、SAFE(Google 2024 long-form factuality)、CharacterEval(2024 角色评估)
- **读者模拟**:PersonaChat / RoleLLM / Character-LLM、AgentSims、UserSim(综合多 persona 评估)

### 1.3 当前内核事实表(基于代码扫描)

| 项 | 现状 |
|---|---|
| Service 数量 | 60 个 .py(novel_analyzer/services/) |
| 最大 service | export(2539)、risk_audit(2156)、imitation_harness(1851)、novel_assistant(1639)、analysis(1567)、whole_book_imitation(1339)|
| 检索链路 | FTS + similarity + like + keyword + entity_exact + vector → RRF → rerank |
| Embedding | bge-m3 ONNX(本地)/ HTTP-TEI 可切 |
| Rerank | bge-reranker-v2-m3 ONNX cross-encoder / DisabledRerankProvider fallback |
| LLM | deepseek-v4-flash(单 provider)+ stage merging 5→3 |
| Loom | Phase 1-5 服务全部存在,**默认 shadow 模式** |
| Foundation | Phase 1-4 全部存在(adaptive context、stage merge、foreshadowing、complexity router、batch、entity resolution、arc memory、causal graph、confidence calibration、self-eval) |
| 词典 | DomainDictionaryService 生成 `.cache/novel-analyzer/domain-dict.txt`,**但 BM25 没加载** |

---

## 2. 域 1:检索(Retrieval)

### 2.1 现状

| 子能力 | 文件 | 评分 |
|---|---|---|
| 多路召回(BM25 / trigram / like / keyword / entity_exact / vector) | `retrieval_service.py` (959 行) | 8 |
| RRF 融合 | `retrieval_service.py` | 7 |
| 实体解析(coreference) | `entity_resolution_service.py` | 7 |
| 领域词典构建 | `domain_dictionary_service.py` | 6 |
| Cross-encoder rerank | `rerank/service.py` | 7 |
| Adaptive context 三策略(relevance/recency/foreshadowing) | `context_service.py` | 7 |
| 章节级检索粒度 | retrieval_service | 6 |

**总分:7/10**

### 2.2 距 SOTA 的差距

| 维度 | 我们 | SOTA | 差距 |
|---|---|---|---|
| 分块粒度 | 章节 + 段(固定) | 语义切分 + 滑窗 + 标题树 | 中 |
| 上下文增强 | 朴素 chunk text | **Contextual Retrieval**:每 chunk 注入 50-100 tok 章节级上下文 | **大** |
| 层级召回 | 章节级 + RRF | RAPTOR 树状聚类(章 → 卷 → 全书摘要) | 中 |
| 图谱召回 | 1-hop alias 扩展 | GraphRAG 社区检测 + 主题路径 | 中 |
| 词典消费 | 生成了**没接 FTS** | jieba/zh-paoding 加载领域词典 | **大(白捡)** |
| Embedding | bge-m3 单路 | bge-m3 dense+sparse+colbert 三路并发 | 小 |

### 2.3 可动 P0(本月)

1. **Activate jieba dict**:`DomainDictionaryService.export_to_postgres()` → 在 PG 用 `CREATE TEXT SEARCH DICTIONARY` 加载;`retrieval_service._fts_config_name()` 切到自定义 config。预期 BM25 召回 +20-30%。已在 `foundation-optimization-priority-research-20260512.md` 立项,**未启动**。
2. **Contextual chunk prefix**:每个 retrieval_chunk 入库前,前置一个 50-tok 上下文(章节 + 紧邻段摘要)。无需改 embedding,只改 chunk text。Anthropic 报告召回错误率 -49%。
3. **bge-m3 三路融合**:把 dense / sparse / colbert 三个分数 RRF 进现有 6 路。`embedding/service.py` 加 `encode_full()` 接口。

### 2.4 可动 P1(下月)

- RAPTOR 章 → 卷 → 全书三层摘要节点入 retrieval_chunks,sort key 加层级;改 ContextService 用层级路径召回。
- GraphRAG 主题路径:在 graph_service 上加 louvain 社区,query 时按社区扩展候选。

---

## 3. 域 2:RAG QA(防剧透 / 分支 QA)

### 3.1 现状

| 子能力 | 文件 | 评分 |
|---|---|---|
| 流式问答 | `qa_service.py` (506 行) | 7 |
| 引用回链 | qa_service + window_artifact | 7 |
| 防剧透(≤当前章节) | `routers/reader.py` + qa_service | **6.5** |
| 4 视角读者评分 | `reader_simulation_service.py` | 6 |
| 反馈聚合 | `reader_feedback_service.py` | 6 |

**总分:6.5/10**

### 3.2 距 SOTA 的差距

| 维度 | 我们 | SOTA | 差距 |
|---|---|---|---|
| 时间约束 QA | chapter_index 上界过滤 | **TimeQA**:时间锚 + 否定证据消歧 | 中 |
| 原子事实校验 | confidence_calibration 四因子 | **FActScore / SAFE**:LLM 拆解 → 单条事实查表 | **大** |
| 幻觉检测 | self_evaluation 5 项 | SelfCheckGPT 多采样一致性 | 中 |
| 引用最小集 | RRF top-K | minimal-evidence:LLM-as-judge 选最小覆盖集 | 中 |
| 反例处理 | 没有显式反证机制 | counterfactual probe | 中 |

### 3.3 可动 P0

1. **Anti-spoiler 时间窗硬接 query expansion**:目前 entity 扩展不带 chapter_index 上界,可能拉到未来章节的别名;在 EntityResolutionService 加 `as_of_chapter` 参数,context_service 调用处穿透传入。
2. **FActScore-lite**:QA 答案出来后,用 LLM 拆解为原子陈述 → 每条回 retrieval_chunks 找证据 → 标 grounded/unsupported。挂一个 `qa_factscore` 信号,先 shadow 落库不暴露 UI。
3. **3-sample 一致性投票**:温度 0.3 跑 3 次,disagreement-rate > 0.4 则降级提示"答案不确定"。

---

## 4. 域 3:仿写(章节级 / 整本)

### 4.1 现状

| 子能力 | 文件 | 评分 |
|---|---|---|
| 章节级仿写 | `chapter_imitation_service.py` (649) | 7 |
| 整本编排 | `whole_book_imitation_service.py` (1339) | 6 |
| Harness 控制器 | `imitation_harness_service.py` (1851) | 6 |
| 修复通道 | `repair_service.py` + `auto_repair_service.py` | 6 |
| Steering 库 | `steering_library_service.py` | 6 |
| Carry-over 状态 | shadow 模式 + memory_assembler | **5.5** |
| Innovation experiment ledger | docs/architecture/imitation-control-plane | 7 |

**总分:6/10**

### 4.2 距 SOTA 的差距

| 维度 | 我们 | SOTA | 差距 |
|---|---|---|---|
| 风格保真 | style_calibration_service(stub 级) | LongLaMP / Persona-conditioned LM:风格特征向量 + 少样本对比 | **大** |
| 长程一致 | carry_over_state(shadow) | RECURRENTGPT 外存 + 反思层 | 中 |
| Plan-Write-Revise | next_chapter_planner_service | Re3:三阶段循环 + critic | 中 |
| 评估闭环 | pairwise_eval_service(数据少) | Reward model fine-tune 后 reuse | **大** |
| Repair 决策 | 规则 + checker | self-rewrite + critic chain | 中 |

### 4.3 可动 P0

1. **Loom carry-over 从 shadow → enabled,跑 20 章对照**:`loom_memory_mode=enabled` 跑卫图样例,记录 character_ooc 触发率前后差。这是 Loom Phase 1 acceptance 中**唯一未验**的硬指标。
2. **Imitation_harness 拆分**:1851 行 → 按 `session / queue / execution / governance / digest` 5 个 Registry 拆 5 个文件。架构图已经画了(`imitation-commercial-agent-control-plane-architecture-20260509.md`),但 service 没拆。这是后续所有 imitation 优化的瓶颈。
3. **Style calibration 真接 quantitative metric**:从 docs/loom/sota-imitation-progression-checklist B 段 `style_drift_score` 抓起。先用 ngram-overlap + sentence-length distribution + punctuation profile 三个简单特征,LLM-judge 对比作 weak label。

---

## 5. 域 4:Loom 信号 / 规划

### 5.1 现状

| 子能力 | 文件 | 评分 |
|---|---|---|
| 张力(tension) | `tension_service.py` (400) | 7 |
| 冲突密度(conflict_density) | tension + dialogue_signal | 6.5 |
| 钩子密度(hook_density) | rhythm_analysis_service | 6.5 |
| 节奏分析 | `rhythm_analysis_service.py` | 6 |
| 对话质量 | `dialogue_signal_service.py` | 6 |
| 角色认知基(persona) | `character_agent_service.py` (372) | 6 |
| Pairwise 评估 | `pairwise_eval_service.py` (362) | 6 |
| 多线调度 | `thread_scheduler_service.py` | 6 |
| Memory consolidation | `memory_consolidation_service.py` (392) | 7 |
| Memory assembler | `memory_assembler_service.py` (309) | 7 |

**总分:6.5/10**

### 5.2 距 SOTA 的差距

| 维度 | 我们 | SOTA | 差距 |
|---|---|---|---|
| Reward model | `loom/reward/reward-model-roadmap.md` 存在,**未训** | DPO/KTO + pairwise 数据回写 | **大** |
| 张力曲线 | per-chapter scalar | story arc curve fitting + 拐点检测 | 中 |
| Plot search | next_chapter_planner | MCTS-Story tree search + critic 剪枝 | **大** |
| 角色认知基 | structured json | Character-LLM finetune + introspection | 中 |
| 多线调度 | scheduler 服务存在 | Dramatron 多 act/scene 树 | 中 |

### 5.3 可动 P0

1. **训第一版 reward model**:用 pairwise_eval 收的对比数据(若 < 500 条则先补到 500),DPO 训一个 0.5B 小模型(qwen-0.5b 起步),作为 ranker 接入 imitation_harness 的多候选选择。
2. **Tension curve fitting**:把 per-chapter scalar 用 LOWESS / Savitzky-Golay 平滑,识别拐点(climax / valley);拐点 vs 章节 outline 错位 → 触发 alert。
3. **Character agent 引入 introspection**:`character_agent_service` 加一步"在生成前先 LLM 模拟该角色对当前情境的反应描述",再约束生成。这是 Character-LLM 论文核心 trick,改动很小。

---

## 6. 域 5:风险审计 / 一致性

### 6.1 现状

| 子能力 | 文件 | 评分 |
|---|---|---|
| 主审计入口 | `risk_audit_service.py` (**2156 行**) | 6 |
| 语义信号 | `risk_semantic_signal_service.py` (358) | 6 |
| 信号 store | `risk_signal_store_service.py` (465) | 7 |
| 信号 link | `risk_signal_link_service.py` | 6 |
| 信号 cluster | `risk_signal_cluster_service.py` | 6 |
| Cluster review 工作流 | `cluster_review_service.py` (326) | 7 |
| Foreshadowing 状态机 | `foreshadowing_service.py` | 7 |
| 因果图断裂检测 | `causal_graph_service.py` | 6.5 |
| 一致性服务 | `consistency_service.py` | 6 |
| 风险证据包 | `risk_evidence_pack_service.py` | 6 |
| 长篇健康度 | `long_book_health_service.py` | 6 |

**总分:6/10**

### 6.2 距 SOTA 的差距

| 维度 | 我们 | SOTA | 差距 |
|---|---|---|---|
| 主文件体量 | 2156 行 | **拆分** | 巨大(workflow 阻塞) |
| 触发器机制 | 规则 + 部分 LLM | LLM-as-judge 全覆盖 + structured-output | 中 |
| 长窗 linking | 5 章窗 + entity match | SAFE 全文 retrieval + 多跳事实图 | 中 |
| 角色 OOC 检测 | character_ooc 信号 + ruleset | CharacterEval-style 多维评分 + persona drift | 中 |
| 战力/规则漂移 | 规则匹配 | 规则 + LLM 漂移概率 | 中 |
| Verdict 仲裁 | 单模型 | Critic ensemble(generator vs critic 异源) | 中 |

### 6.3 可动 P0

1. **拆 risk_audit_service**:2156 → 4 个文件
   - `risk_audit_orchestrator.py`(入口、任务编排)
   - `risk_checker_runner.py`(规则 checker 执行)
   - `risk_semantic_runner.py`(语义触发器执行)
   - `risk_verdict_synthesizer.py`(verdict 合成 + 信号写入)
   保留 `risk_audit_service` 作 thin re-export 兼容。
2. **LLM-judge 全语义触发器**:目前一部分语义触发器还是规则;改成统一的 `judge_with_schema(prompt, schema)` 框架,所有规则触发器变 weak label,语义触发器变 LLM strong label,二者 disagreement → 入 cluster review。
3. **Foreshadowing 状态机加 maturity decay**:planted 超过 N 章未 reinforced 自动降到 dormant,避免长篇里 100+ 个未回收伏笔污染 alert 列表。

---

## 7. 域 6:读者模拟 / 反馈

### 7.1 现状

| 子能力 | 文件 | 评分 |
|---|---|---|
| 4 视角 persona 评分 | `reader_simulation_service.py` | 6 |
| 反馈聚合 | `reader_feedback_service.py` | 6 |
| 1-5 星 + 评论 | apps/web ReaderFeedbackPanel | 6 |
| 反馈与 LLM 评分相关性 | **未做** | — |
| Engagement metric | hook_density(间接) | 5 |

**总分:5.5/10**

### 7.2 距 SOTA 的差距

| 维度 | 我们 | SOTA | 差距 |
|---|---|---|---|
| Persona 真实度 | 4 个 prompt-only persona | RoleLLM / Character-LLM finetune | **大** |
| 真实-模拟相关性 | **未量化** | persona 分 vs 真实读者 1-5 星 Pearson | **大** |
| 多样性 | 4 视角 | UserSim 多元(年龄/口味/阅读量) | 中 |
| 长篇耐读度 | 单章评分 | engagement curve(注意力衰减/重读) | 中 |

### 7.3 可动 P0

1. **真实-模拟相关性回归**:把 reader_feedback 的 1-5 星 vs reader_simulation 的 4-视角分,跑一个 Pearson + Spearman,把相关系数当 Loom 报告里的 KPI 之一。低于 0.5 → persona prompt 需要重写。
2. **Persona prompt 资源化**:目前 4 视角 prompt 散在 reader_simulation_service;迁到 `prompts.py` 同等位置,变成 versioned prompt + few-shot 例子。
3. **Engagement curve**:per-paragraph 而非 per-chapter 的 hook_density,生成 attention 曲线供 Writer Studio Loom 侧栏可视化。

---

## 8. 跨域横切问题(P0 阻塞型)

### 8.1 大文件未拆 — 最高优先级

| 文件 | 行数 | 拆分提案 |
|---|---|---|
| `risk_audit_service.py` | 2156 | 4 子文件(见 6.3) |
| `imitation_harness_service.py` | 1851 | 5 Registry 子文件(见 4.3) |
| `novel_assistant_service.py` | 1639 | 按"章节问答 / 人物事件 / 全书检索"3 段 |
| `analysis_service.py` | 1567 | intake / facts / evidence / analysis 4 段(stage merging 已有线索) |
| `whole_book_imitation_service.py` | 1339 | dryrun / sandbox / export / readiness 4 段 |
| `export_service.py` | 2539 | 按 export 类型 5 段 |

**这一项不解,所有内核 P0 都被卡。**

### 8.2 LLM 调用观测缺口

- `novel_analyzer/llm/client.py` 直连,**Helicone proxy 配了未启用**(`llm_base_url_override` 字段存在但 .env.example 注释掉)
- 一次 imitation 几十次调用,目前没有任何 trace
- 见 `docs/observability/helicone-vs-langfuse.md`,组合方案早已论证完毕,**没落**

### 8.3 评估数据回流

- `pairwise_eval_service` + `eval_governance_service` 存在
- `loom-collect-pairs` CLI 存在
- 但**没有"训 reward → reuse → 闭环"**这一步;所有评估变成日报,没回到 imitation 决策

### 8.4 Schema-strict prompt

- `novel_analyzer/llm/prompts.py` 8KB,模板化但没用 `response_format=json_schema`
- DeepSeek/OpenAI 都支持;改完 self-eval 失败率显著降

---

## 9. 优先级矩阵

按 ROI(收益 / 工作量)+ 阻塞度排序。

| # | 任务 | 收益 | 工作量 | 阻塞度 | 优先级 |
|---|---|---|---|---|---|
| 1 | 激活 jieba 领域词典(BM25) | 高 | XS(1d) | 中 | **P0-1** |
| 2 | risk_audit_service 拆分 | 高 | M(3-5d) | **巨大** | **P0-2** |
| 3 | imitation_harness 拆 Registry | 高 | M(3-5d) | **巨大** | **P0-3** |
| 4 | Loom carry-over 跑 20 章对照 | 极高 | S(1-2d, 全是跑) | 中 | **P0-4** |
| 5 | Helicone proxy 启用 | 中 | XS(0.5d) | 中 | **P0-5** |
| 6 | Contextual Retrieval chunk prefix | 高 | S(2-3d) | 低 | **P0-6** |
| 7 | FActScore-lite QA grounding | 高 | M(3-5d) | 低 | P1 |
| 8 | Reward model 训第一版(0.5B) | 极高 | L(1-2w) | 中 | P1 |
| 9 | Persona 真实-模拟相关性回归 | 中 | S(2d) | 低 | P1 |
| 10 | LLM-judge 统一语义触发器 | 高 | M(1w) | 低 | P1 |
| 11 | RAPTOR 层级摘要 | 中 | M(1w) | 低 | P2 |
| 12 | bge-m3 三路融合 | 中 | M(1w) | 低 | P2 |
| 13 | Plot MCTS | 极高 | XL(2-4w) | 中 | P3 |

---

## 10. 6 周内核冲刺路线(纯内核,不动外部)

```
Week 1-2  阻塞拆分 + jieba 词典激活
  ├─ T1: jieba 词典激活 + BM25 召回 benchmark   (1d)
  ├─ T2: Helicone proxy 启用 + trace 验真         (0.5d)
  ├─ T3: risk_audit_service 拆 4 子文件          (3d)
  └─ T4: imitation_harness 拆 5 Registry         (4d)

Week 3-4  Loom 闭环 + Contextual Retrieval
  ├─ T5: Loom carry-over enabled 跑 20 章对照     (3d, 大半在跑)
  ├─ T6: Contextual chunk prefix + 召回回归       (3d)
  ├─ T7: FActScore-lite + qa_factscore 信号      (4d)
  └─ T8: Persona 相关性回归报告                   (1d)

Week 5-6  Reward + 风险升级
  ├─ T9: pairwise → DPO 0.5B reward model         (2w)
  ├─ T10: LLM-judge 统一风险语义触发器             (5d, 并行)
  └─ T11: 6 周总结 + 内核 capability scorecard 升级 (1d)
```

**6 周后预期**:每域上一档(7→8 / 6→7 / 5.5→6.5),风险/imitation 大文件不再阻塞后续优化,Loom 闭环数据可量化。

---

## 11. 已知不在范围内(本评估**不**触碰)

- 商业 embedding API(预研已决:不走)
- Embedding fine-tune(预研已决:不走)
- 切换 LLM provider(deepseek-v4-flash 当前足够)
- 前端(apps/web)优化
- 新框架/ORM 引入

---

## 12. 评估佐证文档

- `docs/foundation-optimization/README.md`:Phase 1-4 现状
- `docs/loom/roadmap.md`:Phase 1-5 现状
- `docs/loom/sota-imitation-progression-checklist.md`:仿写主链推进
- `docs/architecture/imitation-commercial-agent-control-plane-architecture-20260509.md`:imitation 控制面架构
- `.sisyphus/plans/foundation-optimization-priority-research-20260512.md`:底座优先级预研
- `docs/observability/helicone-vs-langfuse.md`:观测组合方案
- `docs/research/fastgpt-vs-dify.md`:RAG 平台决策
- `docs/foundation-optimization/tei-integration-postmortem-20260512.md`:TEI 切换教训

---

## 13. 下一步

外部对接(Dify/n8n/Langfuse/Helicone/Letta/...)的 roadmap / checklist / 架构图见同目录:

- `docs/strategy/external-integration-roadmap-20260514.md`
- `docs/strategy/external-integration-checklist-20260514.md`
- `docs/architecture/external-integration-architecture-20260514.md`

**外部对接的前提是**:本文 §10 的 6 周冲刺至少完成 Week 1-2(阻塞拆分 + 观测启用),否则外部对接会卡在大文件上无法挂钩子。
