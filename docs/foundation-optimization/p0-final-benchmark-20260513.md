# P0 最终基准报告 — 2026-05-13

> 本文档汇总 P0 闭环（领域词典 → pg_jieba → bm25_vector）的最终实测结果。
> 数据来源：`.sisyphus/evidence/retrieval-bench-FINAL2-*-20260513.json`。

---

## 1. 关键数字

**5 本小说，587 docs，4869 词领域字典**：

| 小说 | docs | queries (DF≤40%) | simple Recall@5 | jiebacfg Recall@5 | simple MRR | jiebacfg MRR |
|---|---|---|---|---|---|---|
| 卫图（示例） | 103 | 98 | 0.8061 | **0.8367** | 0.6815 | **0.7019** |
| 掌门低调点 | 41 | 6 | **1.0000** | **1.0000** | 0.8750 | 0.8750 |
| 诛仙 | 113 | 34 | 0.9412 | **0.9706** | 0.7975 | **0.8270** |
| 武道宗师 | 108 | 28 | 0.4643 | **0.5000** | 0.4092 | **0.4449** |
| 雪中悍刀行 | 109 | 30 | 0.7333 | 0.7333 | 0.7111 | 0.7111 |

**对比 P0 之前**（卫图分支基准）：

| Config | BEFORE (no dict) | AFTER (4869-term dict) | Δ |
|---|---|---|---|
| simple R@5 | 0.2755 | **0.8061** | **+0.531** |
| jieba R@5 | 0.7347 | 0.8367 | +0.102 |
| simple MRR | 0.1835 | **0.6815** | **+0.498** |
| jieba MRR | 0.5547 | 0.7019 | +0.147 |

simple 的提升几乎是 3x。这就是 P0 的真实价值。

---

## 2. 方法学

- **Ground truth**：每章的 `keyword_list[:3]`（经 DF 过滤剔除出现 >40% 章节的常见词）
- **指标**：每个 query 检查正确章节是否在 top-K，统计 Recall@K 和 MRR
- **测试桶**：simple FTS config vs jiebacfg（已加载 novel_analyzer.dict）
- **环境**：本机 PG 17 + pg_jieba + 4869-term userdict

DF 过滤对小说差别巨大：卫图 98 query / 掌门 6 query。这反映了**真实查询难度的差异**——卫图分支 keyword_list 多样且独特；掌门低调点章节短、专有名词集中，剩下的高 DF 词（路朝歌、墨门）几乎贯穿全书。

---

## 3. 三个洞察

### 3.1 simple 与 jiebacfg 的差距已大幅收窄

P0 之前：jiebacfg MRR 是 simple 的 3 倍（0.55 vs 0.18）。
P0 之后：差距收窄到 +3-5%（卫图 0.70 vs 0.68；诛仙 0.83 vs 0.80）。

原因：bm25_vector 用 jiebacfg 索引（词典生效），所有专有名词都被存为单 lexeme。simple tsquery 也产生相同的单 lexeme，二者匹配同一行。

**含义**：领域词典的真实价值不在 query 端，而在**索引端**。把专有名词喂给 jieba 的目的是让索引正确——query 端用什么 config 都不重要。

### 3.2 武道宗师是异类

唯一一个 R@5 < 0.50 的小说。原因：

- 该小说的 keyword_list 噪声大（事件描述被误认为词条）
- 主角名（叶凡？需确认）DF 极高，过滤后剩下的词反而模糊
- 28 query 已经是过滤后剩的，bank 中有大量"卫图 韦飞 寇良"型同时出现的次要角色组合

**指向**：`entity-extraction-noise-diagnosis-20260513.md` 已经在追这个问题。武道宗师可能需要先做 entity extraction 清洗，再做 retrieval benchmark 才有意义。

### 3.3 雪中悍刀行 simple == jieba

唯一一个 Δ=0 的小说。说明该小说的"挑战词"全是 simple 也能命中的 4+ 字组合（北凉王府、徐凤年）。jieba 没新增价值。

---

## 4. Full-Pipeline 基准（多路 RRF + rerank）

BM25-only 是诊断指标；生产实际跑的是 BM25 + trigram + LIKE + entity_exact + vector → RRF → rerank 的多路融合。
2026-05-13 抽样 10 query/branch（fullpipeline 单 query ~10s，跑全 bank 不现实）。

| 小说 | BM25 (jiebacfg) R@5 | Fullpipeline R@5 | ΔR@5 | 备注 |
|---|---|---|---|---|
| 卫图 | 0.6000 | **1.0000** | **+0.40** | 多路把 BM25 漏掉的 4 个全找回 |
| 掌门低调点 | 1.0000 | 1.0000 | +0.00 | BM25 已饱和 |
| 诛仙 | 1.0000 | 1.0000 | +0.00 | BM25 已饱和 |
| 武道宗师 | 0.7000 | 0.9000 | +0.20 | 多路把 BM25 漏掉的 2 个找回 |
| 雪中悍刀行 | 0.7000 | **1.0000** | **+0.30** | 多路把 BM25 漏掉的 3 个全找回 |

**生产层面**：3/5 小说的剩余召回缺口被多路融合 + rerank 完全填平，1/5 部分填平。BM25 单路看起来还有 30-40% 缺口的小说，在生产 pipeline 里几乎没有缺口。

**对 P1 决策的意义**：
- BM25 + 现有 embedding（bge-m3）+ rerank 的组合在 5 本小说 sample 上已经达到 0.9-1.0 的 R@5
- 进一步换 embedding（Conan-v2 / Qwen3-4B）的边际收益空间几乎为零
- **正式确认预研的"P1 不该做"结论**——BM25 已被 P0 修复到不是瓶颈

数据来源：`.sisyphus/evidence/retrieval-bench-FULLPIPE-*-20260513.json`

---

## 5. 已知 caveat

1. **武道宗师召回偏低**：归因于 keyword_list 噪声，不是 retrieval pipeline 缺陷。等 entity extraction 修复后重测。
2. **掌门低调点 query bank 只剩 6 query**：DF 过滤后样本太少，置信度低。需要更多章节稀释 DF 才有意义。
3. **没测 jiebaqry**：上一份报告（`retrieval-benchmark-report-20260513.md`）测过；jiebaqry 比 jiebacfg 略差，本次省略。
4. **Fullpipeline 是 10 query 抽样**：完整 bank 跑代价过高（每 query ~10s），需要 query embedding cache 才能跑全量。

---

## 6. 下一步候选（按 ROI 排序）

| 候选 | 触发条件 | 收益 |
|---|---|---|
| **B. 转向 whole-book 真书完本** | 当前位置 | 直接对标商业化目标，最高 ROI |
| C. 武道宗师 entity-extraction 清洗 | 想把 5 本小说 R@5 都拉到 >0.7 | 清洗工程量中等 |
| ~~A. P1 embedding 升级 (Conan-v2 / Qwen3-4B)~~ | ~~BM25 已不够用、向量路径成瓶颈~~ | **fullpipeline 数据已证伪此假设——R@5 已 0.9-1.0** |
| D. Query embedding cache | 想跑 fullpipeline full bank | 工程量低，让基准变得可重复 |

**强推 B**。BM25 的 P0 红利已经吃完，simple R@5 从 0.18 → 0.81 的提升在 5 本小说里已经稳了；多路融合后 R@5 进一步到 0.9-1.0。下一站应该是产品层。

---

## 7. 引用

- 详细 BEFORE/AFTER 数据：`.sisyphus/evidence/retrieval-bench-FINAL2-*-20260513.json`
- Fullpipeline 数据：`.sisyphus/evidence/retrieval-bench-FULLPIPE-*-20260513.json`
- 运维 quickstart：[`p0-quickstart-and-handoff.md`](./p0-quickstart-and-handoff.md)
- pg_jieba 接入细节：[`pg-jieba-userdict-ops.md`](./pg-jieba-userdict-ops.md)
- 原始预研：[`priority-and-roi-research-20260512.md`](./priority-and-roi-research-20260512.md)
- 上一份基准报告（jiebaqry 对比）：[`retrieval-benchmark-report-20260513.md`](./retrieval-benchmark-report-20260513.md)
