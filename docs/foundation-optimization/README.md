# 底座优化专题

> 核心思路：**小模型 + 精准上下文 > 大模型 + 粗糙上下文**。步数可以多，但每步的输入质量必须极高。

---

## 架构定位

```
┌─────────────────────────────────────────────────────┐
│              LLM Layer (deepseek-v4-flash)           │
│  intake+facts → evidence+analysis → guard           │
└───────────────────────┬─────────────────────────────┘
                        │ 依赖
┌───────────────────────▼─────────────────────────────┐
│              底座层 (本专题优化目标)                    │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  分词层   │  │ Embedding│  │  Context 压缩层   │  │
│  │ 领域词典  │  │ 语义检索  │  │  query expansion │  │
│  │ BM25增强  │  │ 向量召回  │  │  arc compression │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Prompt层  │  │ 验证层   │  │  缓存层          │  │
│  │ few-shot  │  │ grounding│  │  alias cache     │  │
│  │ schema强化│  │ auto-fix │  │  corroboration   │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## 优化环节总览

| 环节 | 优先级 | 必要性 | 当前状态 | 目标 |
|------|--------|--------|---------|------|
| 分词领域词典 | P0 | 极高 | **已实现** ✓ | 自动从分析结果构建领域词典 |
| Embedding query expansion | P0 | 高 | **已实现** ✓ | 1-hop 图邻居扩展 + 别名扩展 |
| Prompt few-shot | P1 | 高 | **已实现** ✓ | 动态注入上一章真实输出 |
| Context 压缩率 | P1 | 中高 | **已实现** ✓ | confidence-weighted 动态压缩 |
| Calibration 批量化 | P2 | 中 | **已实现** ✓ | batch corroboration + contradiction |
| Entity Resolution 缓存 | P2 | 中 | **已实现** ✓ | 增量版本缓存 |

---

## P0-1: 分词领域词典

### 为什么必要

小模型的 BM25 检索是主力召回路径。通用分词器会把"卫图"切成"卫"+"图"，导致：
- BM25 搜索"卫图"时匹配不到
- ClaimGroundingService 的关键词匹配失效
- Entity Resolution 的 label 比较精度下降

### 优化方案

从已分析章节的 `key_entities` + `GraphNode.label` 自动构建领域词典：
1. 每次 materialization 后，收集新出现的实体名
2. 写入 `.cache/novel-analyzer/domain-dict.txt`
3. BM25 分词时加载该词典

### 实现步骤

1. 新建 `novel_analyzer/services/domain_dictionary_service.py`
2. 在 materialization 后调用 `update_dictionary(branch_id)`
3. `RetrievalService._fts_config_name()` 加载词典

### 预期收益

- BM25 召回率 +20-30%（专有名词不再被错误切分）
- Claim grounding 精度 +15%

---

## P0-2: Embedding Query Expansion

### 为什么必要

当前 adaptive retrieval 的 relevance 策略用字符匹配，不是语义匹配。当用户问"那个少年后来怎样了"，如果 fact 里只有"卫图"，字符匹配完全失效。

### 优化方案

在查询前，用已有的 entity_resolution alias_map 和 graph 关系扩展查询：
1. 原始查询 → 别名扩展（已有）
2. 别名扩展 → 关联实体扩展（从 graph edges 找 1-hop 邻居）
3. 扩展后的查询集合 → 多路召回 → RRF 融合

### 实现步骤

1. 在 `ContextService.adaptive_fact_context_json` 中加入 graph-based expansion
2. 从 GraphEdge 找与 query_entities 相连的 1-hop 实体
3. 将扩展实体加入 queries set

### 预期收益

- 远距离实体召回率 +25%
- QA 回答相关性提升

---

## P1-1: Prompt Few-shot 强化

### 为什么必要

deepseek-v4-flash 是小模型，对 prompt 格式极度敏感。纯指令式 prompt 容易导致：
- 输出格式偏离（缺字段、多字段）
- 内容质量不稳定（有时详细有时空洞）
- 对"不要做什么"的指令遵从度低

### 优化方案

在 merged prompt 中加入 1 个真实的完整输入→输出示例：
- 不是通用示例，而是从已分析章节中提取的真实 good case
- 动态选择与当前章节最相似的历史 good case 作为 few-shot

### 实现步骤

1. 在 `AnalysisService` 中加入 `_select_few_shot_example(branch_id, chapter_index)` 方法
2. 从已完成章节中选择 quality_gate 评分最高的一章作为示例
3. 将其 intake+facts 输出作为 few-shot 注入 prompt

### 预期收益

- 输出格式一致性 +40%
- 内容质量稳定性提升
- Fallback 触发率降低

---

## P1-2: Context 信息密度压缩

### 为什么必要

小模型 context window 有限（deepseek-v4-flash ~32K）。当前 adaptive context 可能注入大量低价值信息（如远距离低置信度 facts），挤占有限的 token 预算。

### 优化方案

按信息密度排序，优先注入高价值 context：
1. 高置信度 + 高相关性的 facts 优先
2. 低置信度的 facts 只保留 label，不注入 evidence
3. Arc memory 的 distant tier 进一步压缩（只保留因果链相关的）

### 实现步骤

1. 在 `_compact_prior_context_json` 中加入 confidence-weighted 排序
2. 低置信度 facts 只输出 `{label, chapter_index}`，省略 evidence
3. 总 token 预算控制在 2000 chars 以内

### 预期收益

- 有效 context 密度 +30%
- 小模型注意力集中在高价值信息上

---

## P2-1: Entity Resolution 增量缓存

### 为什么必要

当前每章 materialization 后都调用 `build_alias_map(branch_id)`，全量扫描所有 character nodes。50+ 章后这个操作会变慢。

### 优化方案

- 维护一个 branch-level alias cache（内存 + 文件持久化）
- 每章只处理新增的 character nodes，增量更新 cache
- 只在 cache miss 时全量重建

### 预期收益

- Entity resolution 耗时从 O(N^2) 降到 O(N)

---

## 执行顺序

```
Week 1: P0-1 (分词词典) + P0-2 (query expansion)
Week 2: P1-1 (few-shot) + P1-2 (context 压缩)
Week 3: P2-1 (entity cache) + 30 章稳定性验证
```

---

## 与 SOTA 主线的关系

底座优化不改变 pipeline 结构，只提升每个环节的输入质量：

| SOTA 主线能力 | 底座优化如何增强 |
|--------------|----------------|
| Adaptive Context | 分词词典 → BM25 更准；query expansion → 召回更全 |
| Foreshadowing | 分词 → 伏笔 label 匹配更准 |
| Entity Resolution | 缓存 → 更快；词典 → 切分更准 |
| Causal Graph | 分词 → 因果关键词匹配更准 |
| Claim Grounding | 分词 → 关键词提取更准 |
| Self-evaluation | context 压缩 → 小模型判断更准 |
| Auto-repair | 所有底座提升 → 需要修复的问题更少 |
