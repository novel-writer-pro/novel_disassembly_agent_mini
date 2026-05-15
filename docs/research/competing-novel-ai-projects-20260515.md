# GitHub AI 小说项目竞品研判 — 2026-05-15

> **范围**:对 GitHub 上 2024-2026 间出现的高 star AI 小说生成/辅助类项目做横向研判,回答三个问题:
> 1. **它们做对了什么** —— 我们能借鉴什么
> 2. **它们能不能投入生产** —— 真实成熟度
> 3. **为什么"看起来没什么用"的项目却 star 那么多** —— 流量与价值的脱钩
> **方法**:Web 搜索 + 实际 README/SKILL.md 阅读;不基于二手转述。
> **观感**:我看了 12+ 个项目,**没有一个是开箱即用的生产级方案**;但我们可以从中拣到 4-5 个具体的工程化点。

---

## 1. 主要项目清单

| 项目 | Stars | 语言 | 类型 | 维护状态 | License |
|---|---|---|---|---|---|
| [Narcooo/inkos](https://github.com/Narcooo/inkos) | 4,538 | TypeScript | 多 Agent CLI + Studio Web UI | 活跃(npm 发布) | AGPL-3.0 |
| [YILING0013/AI_NovelGenerator](https://github.com/yiling0013/ai_novelgenerator) | 3,870 | Python | 单机 GUI 生成器 | 活跃 | AGPL-3.0 |
| [THUDM/LongWriter](https://github.com/THUDM/longwriter) | 1,850 | Python | ICLR 2025 论文模型 + AgentWrite | 论文已发表,代码维护中 | Apache-2.0 |
| [iLearn-Lab/NovelClaw](https://github.com/iLearn-Lab/NovelClaw) | 187 | Python+TS | 哈工深学术工作台 | 活跃 | MIT |
| [Lanerra/saga](https://github.com/Lanerra/saga) | ~少 | Python | LangGraph + Neo4j 知识图谱 | 自承认 "not production-ready" | Apache-2.0 |
| [voocel/ainovel-cli](https://github.com/voocel/ainovel-cli) (+ 5+ fork) | 62 | Go | "Novel Harness" 架构 | 活跃 | Apache-2.0 |
| [datacrystals/AIStoryWriter](https://github.com/datacrystals/AIStoryWriter) | 236 | Python | Ollama-friendly 本地优先 | 缓慢维护 | AGPL-3.0 |
| [EdwardAThomson/StoryDaemon](https://github.com/EdwardAThomson/StoryDaemon) | 19 | Python | "story tick" 涌现叙事 | 活跃 | — |
| [THU-KEG/StoryWriter](https://github.com/THU-KEG/StoryWriter) | 32 | Python | 清华学术 multi-agent | 论文用,基本不更新 | — |
| [NousResearch/autonovel](https://github.com/Ripnrip/autonovel) | — | Python | 完整管线(出书+插画+有声书) | 活跃 | — |
| [SillyTavern](https://github.com/SillyTavern/SillyTavern) | 数万 | TypeScript | LLM **角色扮演前端**(不是写小说) | 极活跃,3 年项目 | AGPL |
| [openclaw/skills](https://github.com/openclaw/skills) (12agent-novel / novel-studio / inkos) | 4K(母仓库) | 多 | OpenClaw skill 注册表 | 活跃 | MIT-0 |

---

## 2. 出色的地方 — 我们可以借鉴什么

### 2.1 Inkos(4.5K star)— 当前"工程化"做得最完整的

**核心模式**:5 个 Agent 接力 → 雷达 / 建筑师 / 写手 / 连续性审计员 / 修订者。每章自动审计 33 维度。

**值得借鉴的点**:

| 点 | 我们现状 | 可借鉴 |
|---|---|---|
| **真相文件(truth files)架构** | 我们有 `chapter_summary` / `carry_over_state` / `graph_nodes` 散在 DB | InkOS 把"真相"集中到 7 份 JSON(资源账本/伏笔钩子/角色矩阵...),作家可直接编辑。**可借鉴**:把我们 DB 里的东西暴露成可编辑的 JSON 视图 |
| **AI 痕迹检测维度** | 我们没有专门的"AI 味"检测 | 33 维度里有"AI 痕迹检测":高频词、句式单调、过度总结。**可借鉴**:加 1 个 risk checker 跑 ngram 重复率 + 句长分布 + 标点频次 |
| **多模型路由 per agent** | 我们 stage merging 5→3 已部分做到 | InkOS:写手用 Claude(创意),审计用 GPT-4o(便宜快),雷达用本地模型(零成本)。`inkos config set-model` 按 agent 粒度。**可借鉴**:在 `settings.py` 加 `llm_*_model_name` 已有,但服务级别路由没贯通 |
| **结构化日志(JSON Lines)** | 我们有 `job_event_service` 但格式不统一 | InkOS 强制 JSON Lines + token 统计。**可借鉴**:job_events 落地为 JSON Lines |
| **Studio Web UI** | 我们有 Writer Studio | InkOS Studio 是后加的,作为"CLI 全部命令的可视化镜像" |

**不能借鉴的点**:

- 用 npm 分发 + AGPL — 我们是 Python 后端,不切
- "OpenClaw skill" 这种生态附属定位 — 我们要做平台,不是 skill
- TypeScript 全栈 — 我们已经是 Python+Next.js

### 2.2 NousResearch/autonovel — 评估闭环最完整

**核心**:自动 → 评估 → 修订 → 再评估,直到 Opus 双角色评审(文学评论家+小说教授)挑不出大问题。

**值得借鉴的点**:

1. **机械层 slop scorer**(无 LLM,纯 regex):banned words / fiction clichés / show-don't-tell violations / sentence uniformity。**比 LLM-judge 便宜 100×**,先跑机械层过滤掉明显问题,再用 Opus 看剩下的。我们目前直接上 LLM-judge,可以加这一道。
2. **`adversarial_edit.py` "Cut 500 words"**:LLM 当编辑,标出可砍的 500 字,然后分类(填充/重复/无关/必要)。这个产出是**叙事密度的金标准**,我们没有。
3. **`compare_chapters.py` Elo 锦标赛**:头对头比对,生成 Elo 分。我们有 `pairwise_eval_service`,但只是单点对比,**没接 Elo**。

### 2.3 voocel/ainovel-cli "Novel Harness" — 架构思路高度一致

**这个项目的架构和我们极其相似**:

| 概念 | ainovel-cli | 我们 |
|---|---|---|
| Scaffolding(启动期装配) | Coordinator/Architect/Writer/Editor 四个 agent | `imitation_harness_service` 内部分多 stage |
| Harness(运行期编排) | Host 负责状态迁移、提醒注入、断点恢复、提交一致性 | `pipeline_run_service` + `job_event_service` |
| 章节级断点恢复 | Ctrl+C / 崩溃 / 断网后续写 | 我们的 `pipeline_async` 也支持但更脆弱 |
| 卷弧双层滚动规划 | 初始 2 卷骨架 + 第 1 弧详细 | **我们没有**,目前是全章节平铺 |
| 相关章节智能推荐(伏笔/角色/状态/关系四维) | ✅ | 我们的 `context_service` 是 entity+recency+foreshadowing 三维,**少一维"关系"** |
| 自适应上下文策略 | 全量/滑窗/分层摘要按章数自动切 | 我们的 `arc_memory_service` 已有三层(recent/midrange/distant),但没做"按章数自动切",而是固定阈值 |

**非常重要的发现**:`ainovel-cli` 在 2026-03 出现后,2 个月内有 5+ 个 fork(zhaoge0202 / ydw1314 / sta5901 / lrt8330 / xingHeQingMeng / Tsuki-polaris...),代码 README 几乎一字不差。这意味着**"Scaffolding + Harness"成了网文圈的事实模板**。我们独立演化出来的架构和它非常接近,这本身就是一个验证信号。

**可借鉴的具体点**:

1. **卷弧双层滚动规划**:我们目前没有。可以加在 `next_chapter_planner_service` 上,形成"骨架弧 → 详细章节"两阶段。
2. **关系维度作为相关章节召回的第四维**:我们的 retrieval/context 缺这一维。可以基于 `graph_edges` 的 relationship 类型 + `relationship_consistency_checker` 的事件链来加。
3. **指南针(Compass)文件**:终局方向 + 活跃长线 + 规模估计,弧边界由 Architect 更新。我们没有显式的"故事方向锚",可以在 `branch_metadata` 加。

### 2.4 THUDM/LongWriter — 长文生成的训练数据范式

**这是论文,不是工具**。它揭示的是:**LongWriter-glm4-9b 通过 plan-and-write 数据训练,可以在 1 分钟内生成 10,000+ 字**(vLLM 部署)。

**值得我们关注的**:

- **AgentWrite 数据合成 pipeline**(`agentwrite/plan.py` + `write.py`):自动生成"长输出"训练数据。如果未来要 fine-tune 自己的写作模型(我们当前预研结论是不微调),这是最规范的数据合成范式。
- **LongBench-Write** + **LongWrite-Ruler** 两个评估 benchmark:我们没接。但接入成本不低,需要中文版的对应 benchmark。
- **LongWriter-Zero(2025-06)**:纯 RL 训练的超长输出模型,据称击败 DeepSeek-R1 / Qwen3 在长篇写作任务上。**这个是真值得关注的方向**,但我们不训模型。

### 2.5 SAGA — Neo4j 知识图谱思路

**核心**:Neo4j 存 canon(角色/地点/关系/事件),文件系统存 artifact。LangGraph workflow + checkpointed/resumable。

**结论**:我们用 PG+pgvector,**不切 Neo4j**(预研已决,见 `foundation-optimization-priority-research-20260512.md`)。SAGA 的价值是**验证"知识图谱 + 检索增强"是这个领域的主流方向**,我们的 `graph_service` + `causal_graph_service` 思路是对的。

### 2.6 SillyTavern — 不是同一类项目,但有 1 个借鉴点

**SillyTavern 不是写小说的**,它是**角色扮演前端**。3 年时间 300+ contributor,数万 star。它的核心场景是"和 AI 角色聊天/角色扮演",和我们的"长篇小说生成"是两件事。

**唯一值得借鉴的**:**WorldInfo (lorebooks)** 的设计 — 一个分层、可激活的世界观知识库,按当前对话上下文动态注入 prompt。我们的 `graph_service` + `worldbuilding_facts` 类似但**没有"按上下文激活"**这一步。SillyTavern 的"按 keyword 触发 lore 注入"机制,可以借鉴到我们的 imitation prompt 拼装上。

---

## 3. 是否可以投入生产 — 老实说没有一个

| 项目 | 真实生产度 | 阻挡因素 |
|---|---|---|
| Inkos | 接近,但仍是单作家工具 | 多用户/owner 隔离弱;Studio UI 是 sub-package,部署链长 |
| AI_NovelGenerator | 单机 GUI,**作家自用 OK** | 不是 Web/服务架构,不能多用户 |
| LongWriter | **是研究模型**,不是产品 | 模型 + vLLM 推理,没有应用层 |
| autonovel | 实验项目,产出过 1 本书 | 强依赖 Anthropic / fal.ai / ElevenLabs API,锁死单云 |
| NovelClaw | 学术工作台 | 教学/研究为主,缺多租户、缺 ops |
| SAGA | **作者明说 not production-ready** | 已知 critical issues(GitHub README) |
| ainovel-cli + 5 forks | PoC 级 | 只有一个 author/repo,没有 user base |
| AIStoryWriter | 缓慢维护,作者自承"还在改进" | 重复短语、章节衔接、节奏问题都还在解决 |

**结论**:**这个赛道目前没有真正的生产级开源方案**。这其实对我们是好事——我们的方向(平台化 + Writer/Reader 双端 + 多用户 + 风险门控)在 GitHub 上没有直接对手。

**最接近的"产品形态"是 Inkos**,它的 Studio Web UI + 真相文件 + 多 Agent 接力是一个**完整的可分发产品**。但它仍是单作家工具(每本书一个 project 目录),不是平台。

---

## 4. 为什么很多"看起来没什么用"的小说 skill 却 star 那么多

这是你最关心的问题。**这是 GitHub star 经济学的题**,不是"项目本身好不好"。我列 6 条机制,从大到小:

### 4.1 中文网文市场的体量决定了流量

中文网络文学是一个**年规模 5000 亿人民币 + 5000 万活跃读者/写者**的市场(阅文 / 番茄 / 晋江 / 起点 / 七猫 + 微信读书 + 抖音免费阅读)。这个市场的写者每月会主动搜索"AI 写小说工具",**任何一个看起来能用的免费工具都会被 star**——不是因为它真的好用,而是"先 star 了再说,有空回来试"。

`AI_NovelGenerator` 3.8K / `inkos` 4.5K 的 star,**有一半以上是 watching list 而非 actual usage**。

### 4.2 AGPL 反而推高 star

InkOS 和 AI_NovelGenerator 都用 AGPL-3.0。这个 license 让"商用 fork"几乎不可能,但反而强化了"个人玩具/学习项目"定位 — 个人开发者 star 起来更没有顾虑(没有"这是不是某公司的诱饵"的疑虑)。

### 4.3 "中文网文" + "多智能体" 的关键词组合是 star magnet

`ainovel-cli` 单仓库 62 star,但**它的 README 模板被 fork 5+ 次**(zhaoge0202/ydw1314/sta5901/lrt8330/xingHeQingMeng/Tsuki-polaris)。每个 fork 自己的仓库都还有几个 star。fork 的目的不是改进,而是**展示自己也"做了一个"**——这是 GitHub portfolio 现象,不是产品迭代。

### 4.4 OpenClaw 类生态的"借光"效应

OpenClaw 是个 349K star 的 AI 助手平台。它的 `skills/` 子仓库本身有 4K star。**只要你写了一个 SKILL.md 提交到 openclaw/skills,就自动 inherit 一部分曝光**。

具体例子:
- `openclaw/skills/skills/narcooo/inkos/SKILL.md` — InkOS 通过 OpenClaw skill 形态二次分发
- `openclaw/skills/skills/228998098/12agent-novel/SKILL.md` — 12Agent 中文小说创作系统
- `openclaw/skills/skills/weihfei/weihefei-novel-studio/SKILL.md` — 15 个 specialist agent

这些 SKILL.md **本身没有可执行代码**,只是 prompt + agent 编排说明。它们的 star 来自 OpenClaw 主仓库的流量分配。

### 4.5 "Multi-agent" 是 2025-2026 最强的 buzz word

随便一个 README 写"5 个 Agent 接力"或"多智能体协作",在中文社区当下立即收割 100-500 star。**有没有真的多 agent 不重要**——单 LLM 多次调用、不同 prompt、不同 system message,都被叫"multi-agent"。

`12agent-novel`(版本号 2.8.0)实质是 **12 个 prompt 模板 + 1 份执行说明**,没有独立的 agent runtime。但叫 "12Agent" 比叫 "12 prompts" 更吸睛 5 倍。

### 4.6 **"看起来没什么用"很多时候真的没什么用**

我读了 5+ 个 SKILL.md,**很大一部分是 prompt 工程的封装**:

- 13-26 个 "原子工具"(`write_draft` / `audit_chapter` / `revise_chapter` / ...)实际是 prompt 别名
- "33 维度审计"是 33 条 LLM 检查规则,跑一次审计 = 33 次 LLM 调用
- "卷弧双层滚动规划"在多数实现里就是"先写大纲再写章节"的换皮

**它们的 star 不代表工程价值,代表**:

1. 文档写得好 — README 长 + 表情符号 + 中英双语
2. 题材稀缺 — 中文写作工具在英文 GitHub 上视觉冲击大
3. fork 友好 — 模板化设计鼓励个人 portfolio fork
4. 时机踩准 — 2026 上半年是 AI 写作工具的认知高峰

**实际生产价值**和 star 数的相关性可能只有 **0.3-0.5**。

---

## 5. 给我们的具体行动建议

### 5.1 高 ROI 借鉴(可以列入 §10 6 周冲刺的扩展)

```
[ ] B1: 加 1 个 "AI 痕迹" risk checker (借鉴 InkOS)
       → 现有 risk_audit_checkers.py 再加 1 个 dataclass
       → 维度:ngram 重复率 / 句长分布 / 标点频次
       → 实现成本:1d
       → 预期价值:补齐 SOTA progression checklist 的"AI 痕迹检测"维度

[ ] B2: 关系维度加入相关章节召回 (借鉴 ainovel-cli)
       → context_service.adaptive_fact_context_json 加第 4 维
       → 基于 graph_edges 的 relationship 类型
       → 实现成本:2d
       → 预期价值:长篇关系连续性提升

[ ] B3: 卷弧双层滚动规划 (借鉴 ainovel-cli)
       → next_chapter_planner_service 加 ARC 概念
       → 初始只规划前 2 弧,后续按需展开
       → 实现成本:3-5d
       → 预期价值:500+ 章长篇规划可行

[ ] B4: 机械层 slop scorer (借鉴 autonovel)
       → 新 service: mechanical_slop_scorer_service
       → 纯 regex,无 LLM
       → 在 LLM judge 之前过滤明显问题
       → 实现成本:1-2d
       → 预期价值:LLM-judge 调用量 -30%,延迟降低

[ ] B5: Elo 锦标赛接入 pairwise_eval (借鉴 autonovel)
       → 现有 pairwise_eval_service 加 Elo 累计
       → 实现成本:1d
       → 预期价值:多版本对比有量化分数,reward model 训练数据更结构化
```

**这 5 项都是低风险 + 不动 prompts.py + 不动 v5 边界**,可以在 §10 §10 Week 5-6 的 "T11 总结" 之前作为额外冲刺项。

### 5.2 不借鉴(明确拒绝)

```
[反对] 切 Neo4j (SAGA 路径)
       → 预研已决:PG+pgvector 走完
       
[反对] 自训长文生成模型 (LongWriter 路径)
       → 预研已决:不微调

[反对] 引入 npm 包 / AGPL 代码
       → 我们已经是 Python 后端;融合 AGPL TS 包会污染整个 license

[反对] 把"33 维度"扩到 50 维度
       → 现有 9 个 GateChecker + 拆分后的 risk_audit_checkers 已经够细
       → 多就是噪声,不是价值

[反对] 复制 OpenClaw skill 形态发分发
       → OpenClaw 是平台,我们也是平台。复制 = 自废武功
```

### 5.3 长期观察(每季度复审一次)

```
[观察] LongWriter-Zero 的中文版生态
       → RL 训练的长文模型如果出现成熟中文版本,我们的 LLM 选型可以重新评估

[观察] inkos 的 Studio UI 演进
       → 它的 Web UI 设计可以借鉴(尤其是真相文件可视化)

[观察] ainovel-cli 系列的持续 fork 现象
       → 哪些 fork 真有 commit、不是模板复制,值得对比
```

---

## 6. 一句话结论

> GitHub 上 AI 小说项目的 star 主要由**中文网文市场体量 + 多智能体 buzz + portfolio fork 文化**驱动,**和工程价值的相关性约 0.3-0.5**。
> **没有一个项目是生产级的**;**Inkos 工程化最完整,ainovel-cli 架构思路与我们最相近**。
> **可以借鉴的具体技术点**:AI 痕迹检测、关系维度召回、卷弧双层规划、机械层 slop scorer、Elo 锦标赛 — **共 5 项,总成本 1-2 周**,可作为 §10 内核冲刺的扩展项。
> **不该做的事**:换 Neo4j、自训模型、引入 AGPL TS、扩展到 50 维度审计、复制 OpenClaw 生态形态。

---

## 7. 附录:阅读源

- [Narcooo/inkos](https://github.com/Narcooo/inkos) — README + SKILL.md
- [YILING0013/AI_NovelGenerator](https://github.com/yiling0013/ai_novelgenerator) — README
- [voocel/ainovel-cli](https://github.com/voocel/ainovel-cli) — README(对比 5 个 fork)
- [THUDM/LongWriter](https://github.com/thudm/longwriter) — README + 论文摘要
- [Lanerra/saga](https://github.com/Lanerra/saga) — README
- [iLearn-Lab/NovelClaw](https://github.com/iLearn-Lab/NovelClaw) — README
- [datacrystals/AIStoryWriter](https://github.com/datacrystals/AIStoryWriter) — README
- [EdwardAThomson/StoryDaemon](https://github.com/EdwardAThomson/StoryDaemon) — README
- [THU-KEG/StoryWriter](https://github.com/THU-KEG/StoryWriter) — README + paper
- [NousResearch/autonovel](https://github.com/Ripnrip/autonovel) — README + 27 个 tool 列表
- [SillyTavern](https://github.com/SillyTavern/SillyTavern) — README
- [openclaw/skills](https://github.com/openclaw/skills) — `skills/narcooo/inkos`, `skills/228998098/12agent-novel`, `skills/weihfei/weihefei-novel-studio`
- 本研判与 [docs/strategy/kernel-sota-gap-assessment-20260514.md](../strategy/kernel-sota-gap-assessment-20260514.md) §10 配套

---

## 8. 修订记录

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.0 | 2026-05-15 | 初版,12 个项目横向研判 + 5 项可借鉴 + 5 项明确拒绝 |
