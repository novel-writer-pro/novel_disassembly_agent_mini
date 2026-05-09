# AI 小说助手商业化、护城河与 SOTA 路线分析（2026-05-08）

## 1. 这份文档回答什么

这份文档集中回答 5 个问题：

1. 我们之前规划里的 **P1 / P2 / P3** 现在分别处于什么状态  
2. 未来商业化时，我们真正的**护城河**应该是什么  
3. 距离各方面 **SOTA** 还差哪些关键难题  
4. **开源系统 + 自留核心模型/数据** 的策略是否成立  
5. 未来是否应该为**不同类型小说应用不同 skills / 约束包**，以及怎么规划

---

## 2. 先给结论

### 2.1 当前方向总体是对的
你现在的总体方向是正确的：

- **系统/工作流/技能层开源**
- **核心 embedding / rerank / LLM / 评测数据 / 人工反馈资产自留**
- 开源版可跑、可用、可验证
- 商业版在：
  - 效果
  - 稳定性
  - 延迟
  - 多书样本
  - 评测闭环
  - 行业 know-how
  上形成明显差距

这是一个典型的：

> **Open-core + private models/data/evals + workflow moat**

路线。

### 2.2 但真正的护城河不是“模型名字”
真正的护城河不只是：
- embedding 模型
- rerank 模型
- LLM 权重

而是：

1. **模型 + 数据 + 工作流 + 评测闭环** 一起形成的系统壁垒  
2. **受控生成 + 风险门控 + 读者反馈回流** 的平台级能力  
3. **多书、多类型、多阶段** 的持续积累能力

也就是说：

> 你应该卖的是“小说生产基础设施的质量差”，而不是“单个模型更强”。

---

## 3. 当前 P1 / P2 / P3 状态

## 3.1 P1：当前最直接影响商业效果的能力

### 当前状态
P1 基本已经从“概念”进入“有主链、有样例、有文档”的阶段，但还没到完全打满。

当前 P1 主要包括：

1. **retrieval/search 主链**
   - 当前已有：
     - RRF
     - diagnostics
     - benchmark
     - vector / entity-exact 基础接入
   - 当前短板：
     - rerank 真正改序收益证据密度还不够
     - query bank 规模还不够

2. **author-facing knowledge / story bible**
   - 当前已有：
     - facts
     - graph/state
     - author knowledge pack
     - future chapter outline
   - 当前短板：
     - 产品层表达还不够顺手
     - 还不像头部产品那样真正成为作者每天都会用的控制面

3. **chapter imitation 主链**
   - 当前已有：
     - harness
     - repair lanes
     - reader-sim
     - steering pack
     - 本地 trope/worldview/audience 文档库装配
   - 当前短板：
     - provider-backed 大规模成功样例还不够
     - 多轮真实创作实验密度不够

4. **whole-book success evidence**
   - 当前已有：
     - sandbox
     - provider-backed rerun success sample
     - readiness / run / handoff 文档
   - 当前短板：
     - 成功样例密度不够
     - 跨更多题材/更多长度的稳定证据不足

### 判断
P1 不是“没做”，而是：

> **主链已成立，但商业化前最需要的是“证据密度”和“作者可消费表达层”。**

---

## 3.2 P2：决定从“能用”到“更强” 的能力

### 当前状态
P2 主要是让系统从“结构上正确”升级到“体验与收益更强”。

包括：

1. **baseline vs steering 对照实验**
2. **innovation delta / risk delta**
3. **reader-sim 对创新接受度评估**
4. **next-chapter / whole-book 更深消费 author knowledge**
5. **risk semantic 长窗口质量评估**
6. **统一运营指标 / capability scorecard 持续量化**

### 当前判断
P2 是最容易把你从“工程上像平台”推进到“产品上像 SOTA”的阶段。

因为很多系统不是缺主链，而是缺：
- 精准对照
- 解释能力
- 实验复盘
- 更细颗粒度的收益判断

---

## 3.3 P3：决定长期平台壁垒的能力

### 当前状态
P3 更偏长期：

1. **轻量 RAG -> 更真实的 RAG surface**
2. **多 reader persona**
3. **genre-specific policy packs**
4. **真正强 story bible / codex 产品层**
5. **更多自动化 experiment / governance / scoring**

### 当前判断
P3 现在不该抢掉 P1/P2 的资源，但必须保持架构预留。

因为长期真正拉开差距的，往往不是“再多一个功能”，而是：

> 你能否让不同题材、不同长度、不同用户角色在同一平台上得到稳定高质量结果。

---

## 4. 我们的护城河应该是什么

## 4.1 第一层护城河：结构化知识中台

当前最像护城河的部分是：

- chapter analysis
- facts
- retrieval
- graph / state
- author knowledge
- branch report

这层能力的价值在于：
- 不依赖单次生成
- 可反复复用
- 可被编辑、作者、运营共同消费

### 为什么这是护城河
因为很多竞品更像“写作器”，但不一定有：
- 长文本结构化理解
- 可消费的知识中台
- 多下游统一复用面

---

## 4.2 第二层护城河：受控生成，而不是自由生成

你的仿写能力如果最后只是：
- prompt 一下直接写

那很难形成护城河。

真正的护城河在于：
- harness
- repair lanes
- risk gate
- reader-sim
- steering pack
- whole-book handoff

也就是：

> **不是“让模型写”，而是“让系统持续把它写对”。**

这点对商业化尤其重要，因为 B 端买单更看重：
- 可控
- 可解释
- 可复盘
- 可交接

---

## 4.3 第三层护城河：私有模型 + 私有数据 + 私有评测

你说：
- embedding / rerank / llm 等核心模型自己训练和积累
- 开源出去的只是系统默认能力
- 别人能用，但效果不会和你一样

这个方向本身是合理的。

但要注意，真正应当私有的，不只是模型权重，还包括：

1. **高质量查询/评测集**
2. **reader feedback 数据**
3. **experiment 对照数据**
4. **genre/trope/worldview 高质量文档库**
5. **人工修稿与成功案例库**

### 因为真正护城河是数据飞轮
别人即使拿到你的开源系统：
- 能跑
- 能试
- 能看懂架构

但如果没有你的：
- 私有模型
- 私有语料
- 私有评测
- 私有反馈闭环

就很难得到同等效果。

---

## 4.4 第四层护城河：治理与交接

这个点经常被低估，但实际上很值钱。

你现在已经有：
- sample bundle
- freeze gate
- handoff docs
- release contract
- verification / manifest / delivery package

这意味着：
- 你不是只有“能力”
- 还有“能力如何被交付、复用、复盘”

对真正平台化商业化来说，这是很强的差异点。

---

## 5. 距离 SOTA 还差哪些难题

## 5.1 拆书 / 理解层

### 你们现在做得好的
- 结构化拆书已经明显强于很多纯生成产品
- facts / graph / retrieval 主链已成

### 距离 SOTA 还差的难题
1. **更多题材上的稳定性**
   - 男频修仙、女频、悬疑、科幻、轻小说、同人
   - 各题材抽取重点不同

2. **复杂长线人物关系的稳定抽取**
   - 尤其是长篇多势力、多时序、多视角小说

3. **隐含规则 / 潜规则 / 气氛规则抽取**
   - 这类最容易漏

### 举例
修仙小说里，真正重要的未必是“功法名”，而是：
- 修炼资源分配规则
- 宗门地位差
- 婚姻/家族绑定规则
- 表面礼法与真实利益之间的缝

这些抽不好，后面的仿写都会偏保守或偏假。

---

## 5.2 检索 / RAG 层

### 现在做得好的
- 已有 RRF
- 已有 diagnostics
- 已有 benchmark
- 已有 vector / entity-exact 基础能力

### 距离 SOTA 还差的难题
1. **多路召回的真实收益密度**
2. **rerank 在真实长篇创作场景中的稳定收益**
3. **作者可理解的检索摘要层**
4. **genre-aware retrieval**

### 举例
同样是“主角突破”，
修仙文读者要找的是：
- 资源
- 境界
- 师承
- 代价

而悬疑文作者要找的是：
- 线索回收
- 嫌疑链
- 证据冲突

如果 retrieval 仍是统一平铺逻辑，就离 SOTA 还有距离。

---

## 5.3 风险门控层

### 现在做得好的
- risk checker
- semantic signal
- review workflow
- explainable gate

### 距离 SOTA 还差的难题
1. **长窗口 adjudication**
2. **复杂矛盾时的自动裁决**
3. **创新 vs 越界 的平衡评分**
4. **不同题材的风险 profile**

### 举例
男频修仙里“突然大机缘”未必直接算错，
但需要判断：
- 是伏笔兑现
- 还是硬塞外挂

这类问题不是通用 checker 能完全吃透的。

---

## 5.4 仿写 / 续写层

### 现在做得好的
- harness
- repair lanes
- steering pack
- batch innovation experiment

### 距离 SOTA 还差的难题
1. **创新不失真的稳定度**
2. **多章连续创新的一致性**
3. **reader delight 而不只是 reader acceptance**
4. **从“像”升级到“有新 IP 感”**

### 举例
现在最容易做到的是：
- 不写崩
- 基本像

最难的是：
- 既像原始底层逻辑
- 又让读者觉得这是一个值得单独追的新故事

这一步才是商业化真正的大难点。

---

## 5.5 whole-book 层

### 现在做得好的
- whole-book orchestration 已有骨架
- readiness / run / handoff 已有

### 距离 SOTA 还差的难题
1. **多轮 provider-backed 成功样例密度**
2. **跨 100+ 章的一致性证据**
3. **长书中期疲软的自动发现与修复**
4. **卷级节奏 / 弧线节奏 / payoff 节奏**

### 举例
很多系统能写前 10 章不错，
但到 40 章后会出现：
- 重复
- 势力膨胀失控
- 升级节奏失衡
- 感情线突然失真

whole-book 的 SOTA 核心不是“能续写”，而是“能稳定写久”。

---

## 5.6 产品体验层

### 现在做得好的
- 系统层很强
- 文档与交接很强

### 距离 SOTA 还差的难题
1. **story bible / codex 产品层**
2. **作者日用控制面**
3. **编辑/运营视角统一看板**
4. **实验结果可视化**

### 举例
Novelcrafter / Sudowrite 之所以看起来接近 SOTA，
不只是模型，而是：
- 作者更容易“天天用”
- 更容易编辑和调整
- 更容易看到故事控制面

你们系统现在更像强中台，
但还要进一步变成“强中台 + 好操作面”。

---

## 6. 开源策略是否 OK

## 6.1 你的思路总体是 OK 的

建议保持：

### 开源的
- 系统骨架
- CLI / API / workflow
- skills / prompts / docs
- 默认 provider 适配
- 默认能力包

### 私有的
- 最强 embedding
- 最强 rerank
- 最强 LLM / router
- 私有评测集
- 私有反馈数据
- 私有 trope/worldview 语料库
- 私有实验结果库

这是合理的 open-core 路线。

---

## 6.2 但要注意 4 个边界

### A. 开源版不能“太废”
如果开源版只是能跑但几乎没价值，
很难形成生态，也不利于吸引开发者。

### B. 私有能力要通过接口隔离
不要把私有模型能力写死在业务代码里。
应该是：
- provider interface
- model registry
- configurable routing

### C. 私有优势要体现在“质量差”
而不是只体现在“参数名字不同”。

别人要清楚感受到：
- 默认版能用
- 你们自有版明显更强

### D. 最关键的是私有评测与反馈飞轮
真正最不该轻易外泄的，往往是：
- query bank
- judge set
- failure case library
- human revision corpus

---

## 7. 是否要针对不同小说类型绑定不同 skills / 约束包

答案是：**非常应该。**

但不要理解成“不同类型完全不同系统”，
而应该理解成：

> **同一系统骨架 + 不同 genre policy packs / steering packs / risk profiles**

---

## 7.1 推荐做 genre packs

例如：

### 男频修仙 pack
- 收益可见
- 阶层跃迁
- 章尾机会压力
- 资源 / 功法 / 地位强绑定

### 女频情感 pack
- 情绪递进
- 人物关系真实细腻
- 冲突更多靠关系与心理

### 悬疑推理 pack
- 线索公平
- 信息揭示顺序
- 推理闭环
- 反转不过度作弊

### 科幻 pack
- 世界规则一致
- 技术设定自洽
- 议题驱动

---

## 7.2 skills 该怎么分层

建议区分三层：

### A. 通用 skills
所有题材都用：
- intake
- fact extraction
- constraint pack
- draft-self-check
- reader-sim
- risk gate

### B. genre policy packs
按题材切换：
- trope axes
- worldview defaults
- taboo rules
- reader expectation notes

### C. 高阶 genre specialists
只在必要时挂：
- romance emotion pass
- xianxia resource ladder pass
- mystery clue fairness pass
- sci-fi rule consistency pass

这样做的好处是：
- 系统骨架统一
- 类型差异有约束
- 不会无限分叉成一堆完全不同流程

---

## 8. 我们的 SOTA 路线应该怎么理解

不要把 SOTA 只理解成：
- 单次生成更华丽
- 模型更大

对于你们这个系统，SOTA 应该至少拆成 4 维：

### A. 理解 SOTA
- 拆书、facts、graph、state 最稳定

### B. 控制 SOTA
- 风险门控、受控仿写、continuity 最稳定

### C. 创新 SOTA
- 不是只像原文，而是能有新底座、新抓手、新 IP 感

### D. 平台 SOTA
- eval
- governance
- handoff
- repeatability

如果只卷 A/B 而不卷 C/D，
那最多是强写作工具，不一定是强平台。

---

## 9. 最后的建议

### 现在最该做的，不是再加散点功能
而是继续做这三件事：

1. **扩 trope/worldview/audience 文档库**
2. **把 experiment 做成真正可对照、可解释、可复盘**
3. **把 genre packs 做出来**

### 因为商业化真正买单的不是“多一个 feature”
而是：
- 更稳定
- 更可控
- 更能复制
- 更有明显质量差

---

## 10. 一句话判断

### 我们现在做到的
- 已有强中台骨架
- 已有风险门控护城河
- 已有受控仿写骨架
- 已有创新 steering 起点

### 我们还需要做的
- 把这套创新与 genre 控制面做深
- 把私有模型/数据/评测的飞轮做强
- 把 story bible / codex / experimentation 产品层做顺

### 最终一句话

> 真正的护城河不是“我们也能写小说”，而是“我们能把小说写作这件事，做成一个可理解、可控制、可创新、可治理、可商业化复制的系统”。  

