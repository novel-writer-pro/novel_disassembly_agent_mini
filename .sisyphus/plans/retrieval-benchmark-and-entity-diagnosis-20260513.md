# 检索基准报告 + entity 抽取诊断备忘 — 2026-05-13

## TL;DR

> **Quick Summary**:把今天 jiebacfg 实测数据(3 个分支)归档为正式报告,同时把"上游 entity 抽取噪声是新瓶颈"的发现写成诊断备忘 — 两份文档,1 个 commit。**不改代码** — 修复路径要等诊断结论被人审过。
>
> **Deliverables**:
> - `docs/foundation-optimization/retrieval-benchmark-report-20260513.md`(三分支实测 + 结论 + 行动项)
> - `docs/foundation-optimization/entity-extraction-noise-diagnosis-20260513.md`(噪声样本归类 + 假设 + 推荐排查动作)
> - `docs/foundation-optimization/README.md` 索引追加 2 行
>
> **Estimated Effort**: 0.5 人天,1 个 atomic commit
> **Critical Path**: Prometheus 写计划 → executor 写两份 doc + commit

---

## Context

### Original Request

用户原话(在 P0 三选一里选 "1+2 顺序" 后,看到 benchmark 数据立刻指出新瓶颈):
> "好的,遵循你的建议进行开发"

我建议的两步:
1. 把 benchmark 数据 + 两层信号沉淀成报告
2. 直接深挖上游问题(诊断而非立刻修)

### 实测数据(2026-05-13,本机 PG 实跑)

#### 三个分支的 retrieval-benchmark CLI 输出

**Branch 72da24e9 (103 docs)** — `key_entities` 干净
| Config | MRR | R@1 | R@3 | R@5 | R@10 | 延迟 |
|--------|-----|-----|-----|-----|------|------|
| simple | 0.188 | 0.133 | 0.184 | 0.276 | 0.327 | 3.2ms |
| **jiebacfg** | **0.560** | **0.439** | **0.592** | **0.735** | **0.827** | 4.3ms |
| jiebaqry | 0.489 | 0.378 | 0.520 | 0.643 | 0.735 | 4.8ms |
| Δ(jiebacfg − simple) | +0.371 | +0.306 | +0.408 | +0.459 | +0.500 | +1.0ms |

**Branch 2cd9c1ff (59 docs)** — `key_entities` 含噪声
| Config | MRR | R@1 | R@5 | R@10 | 延迟 |
|--------|-----|-----|-----|------|------|
| simple | 0.017 | 0.017 | 0.017 | 0.017 | 3.0ms |
| jiebacfg | 0.060 | 0.052 | 0.069 | 0.069 | 4.6ms |
| jiebaqry | 0.060 | 0.052 | 0.069 | 0.069 | 3.1ms |
| Δ | +0.043 | +0.034 | +0.052 | +0.052 | +0.1ms |

**Branch e5becabd (57 docs)** — `key_entities` 含噪声
| Config | MRR | R@1 | R@5 | R@10 | 延迟 |
|--------|-----|-----|-----|------|------|
| simple | 0.069 | 0.069 | 0.069 | 0.069 | 3.1ms |
| jiebacfg | 0.164 | 0.155 | 0.172 | 0.172 | 3.2ms |
| jiebaqry | 0.095 | 0.086 | 0.103 | 0.103 | 3.4ms |
| Δ | +0.095 | +0.086 | +0.103 | +0.103 | +0.1ms |

JSON evidence 已备份到:
- `.sisyphus/evidence/retrieval-bench-72da24e9-20260513.json`
- `.sisyphus/evidence/retrieval-bench-2cd9c1ff-20260513.json`
- `.sisyphus/evidence/retrieval-bench-e5becabd-20260513.json`

#### Entity 噪声实样(从 chapter_artifacts.payload_json 直接读)

**GOOD 分支 72da24e9 ch1-3**(干净示例)
- ch1: `['卫图', '李宅', '李老爷', '老刘头', '二姑', '黄老爷', '黄宅', '郑国']`
- ch2: `['卫图', '卫荭', '厨娘杏', '李家大奶奶', '李家大少爷', '黄宅', '胭脂铺', '青荷']`
- ch3: `['卫图', '卫荭', '阮武师', '青荷', '翠柳', '黄家两位少爷', '李宅', '黄宅']`

**BAD 分支 2cd9c1ff ch6**(噪声示例)
- key_entities: `['走一个', '白狐儿脸', '没有任何', '阻拦进了', '王府']`
- 噪声分类:
  - "走一个" → 动词短语
  - "没有任何" → 否定 + 量词
  - "阻拦进了" → 动词短语

**BAD 分支 e5becabd ch16**(噪声示例)
- key_entities: `['第十六章', '驱物', '汪汪汪', '吱吱吱吱', '犬吠声与']`
- 噪声分类:
  - "第十六章" → 章节序数(已在 title 字段,重复)
  - "汪汪汪" / "吱吱吱吱" → 拟声词
  - "犬吠声与" → 名词 + 连词残尾

观察:同一个分支(2cd9c1ff)的 ch1 是干净的(`['徐骁', '徐凤年', '徐龙象', ...]`),ch6 才出问题。**说明问题是 per-chapter 不稳定,不是 per-branch 整体配置问题。**

### 关键解读(两层信号)

1. **jieba 接入 BM25 是无条件的 win** — 三个分支都是 ΔMRR > 0,且延迟代价 ≤ +1ms
2. **绝对 MRR 上限被 entity 抽取质量决定** — 同样跑 jiebacfg,GOOD 分支 0.560,BAD 分支 0.060。差 9 倍。修底座(换 embedding)不能救这种 query 本身就是噪声的场景

---

## Work Objectives

### Must Have

- 报告**真诚**:三个分支的所有数字真实,不平均化/不掩饰
- 报告**给出明确结论**:jiebacfg 应该作为生产默认 + 上游 entity 抽取是下一个瓶颈
- 诊断**只诊断不修复**:列出可能根因 + 推荐排查路径,不写"应该这样改"
- 索引可达:`docs/foundation-optimization/README.md` 追加两行
- 1 个 atomic commit Lore 格式

### Must NOT Have (Guardrails)

- 不修代码(包括 prompt、过滤器、抽取逻辑)
- 不删除现有 artifact / retrieval_documents 数据
- 不"建议立刻重新跑分析"— 这是后续单独决策
- 不在文档里跨章节复制 — 跨链接,不重复
- 不把 jiebaqry < jiebacfg 的差异引申为"jiebaqry 不可用",只陈述事实
- 不引入新的依赖

### Verification Strategy

- 文档落地后,索引项可点开
- 报告里所有数字与 `.sisyphus/evidence/*.json` 严格对应(executor 必须读 JSON 校对)
- markdown-only,无 lsp/test 验证

---

## TODOs

### Phase 1 — 检索基准报告

- [ ] 1. **创建 `docs/foundation-optimization/retrieval-benchmark-report-20260513.md`**

  **What to do**:

  结构(必须 5 章节):

  ```
  # 检索基准首份实测报告 — 2026-05-13

  ## 1. 测试方法
  - retrieval-benchmark CLI(已落地于 commit 94dd73e)
  - Ground truth: 每章 query_hints 自标注,正确答案是该 chapter_index
  - FTS configs 对比: simple vs jiebacfg vs jiebaqry
  - K values: 1, 3, 5, 10
  - PG 已装 pg_jieba(jieba-user-dict.txt 加载,见 pg-jieba-userdict-ops.md)

  ## 2. 三分支实测数据
  三个表格(从 plan §Context 抄数字,不可改)+ 一张 ΔMRR 总览

  ## 3. 关键解读
  - 信号 1: jieba 接入 BM25 是无条件的 win,延迟代价 ≤ +1ms
  - 信号 2: 绝对 MRR 上限被 entity 抽取质量决定(同样 jiebacfg,0.560 vs 0.060)
  - 注意点: jiebaqry 在三个分支都没赢过 jiebacfg(query-mode 切分过细) — 现状 retrieval_service._fts_config_name() 已优先 jiebacfg,无需改

  ## 4. 行动建议
  - 短期(P0):pg_jieba + jiebacfg 在生产 PG 部署到位 — 见 pg-jieba-userdict-ops.md
  - 中期(P0,新发现):上游 key_entities 抽取质量诊断 — 见 entity-extraction-noise-diagnosis-20260513.md
  - 已落地:retrieval-benchmark CLI 可重复跑(命令示例)
  - 不建议:换 embedding 模型(在 entity 噪声修好之前没意义)

  ## 5. 数据存档
  指向 .sisyphus/evidence/retrieval-bench-*.json 文件
  ```

  **Must NOT do**:
  - 不复制 ROI 研究里的全套决策表 — 只引用
  - 不推断超出 3 分支数据的结论(如"全行业都这样")

  **Acceptance Criteria**:
  - [ ] 5 章节齐全
  - [ ] 三个分支数字与 evidence JSON 完全一致(executor 必须 cat 文件核对)
  - [ ] 行动建议明确分短/中期 + "不建议" 项

- [ ] 2. **创建 `docs/foundation-optimization/entity-extraction-noise-diagnosis-20260513.md`**

  **What to do**:

  结构(必须 6 章节):

  ```
  # key_entities 噪声诊断备忘 — 2026-05-13

  ## 1. 触发线索
  - retrieval-benchmark 数据显示同样 jiebacfg 在三分支差 9 倍
  - 链接到 retrieval-benchmark-report-20260513.md
  - 不是 retrieval 层问题,溯源到 chapter_artifacts.key_entities

  ## 2. 噪声样本(plan §Context 直接抄过来)
  - 干净对照: 分支 72da24e9 ch1-3 entities
  - 噪声样本 1: 分支 2cd9c1ff ch6 (走一个/没有任何/阻拦进了)
  - 噪声样本 2: 分支 e5becabd ch16 (第十六章/汪汪汪/吱吱吱吱/犬吠声与)
  - 同分支 2cd9c1ff ch1 干净 vs ch6 脏 — per-chapter 不稳定

  ## 3. 噪声归类
  | 类型 | 示例 | 出现频率 | 假设根因 |
  |------|------|---------|----------|
  | 动词短语 | 走一个/阻拦进了 | ? | 抽取 prompt 缺动名词区分 |
  | 否定/虚词 | 没有任何 | ? | prompt 缺负样本 |
  | 拟声词 | 汪汪汪/吱吱吱吱 | ? | 字符 tokenization 误识 |
  | 章节序数 | 第十六章 | ? | title 字段去重缺失 |
  | 名词残尾 | 犬吠声与 | ? | LLM JSON 截断 |
  
  频率列写"未量化",建议排查阶段统计

  ## 4. 假设根因(待验证,不下结论)
  - 假设 A: prompt 没有负样本 → 排查方法: 看 skills_dir/chapter-intake-and-facts/* 的 prompt 文本
  - 假设 B: complexity router 把简单章节路由到小模型 → 排查方法: 看 _score_chapter_complexity 对噪声章的打分
  - 假设 C: 没有后处理过滤 → 排查方法: 看 analysis_service.py 抽取后是否有 dedup/blacklist
  - 假设 D: 不同分支用了不同 prompt 版本(prompt 在演进) → 排查方法: 比对 GOOD vs BAD 分支创建时间

  ## 5. 推荐排查动作(分级,不立刻执行)
  - 级别 1(0.5 天): 抽样 30-50 个噪声章节,人工分类噪声类型分布
  - 级别 2(0.5 天): 看 skills_dir prompt 是否含负样本和否定词排除
  - 级别 3(1 天): 对一个 BAD 分支随机 5 章重跑分析,看新跑出来是否仍噪声(隔离 prompt 演进 vs 章节内容因素)
  - 级别 4(若证实是 prompt): 加负样本 + 字符级噪声黑名单,小批回灌验证

  ## 6. 不要立刻做的事
  - 不要立刻给所有 BAD 分支重跑分析(成本高,先排查)
  - 不要立刻改 prompt(没诊断完不知道改哪)
  - 不要立刻加正则过滤器(可能误伤合法实体)
  - 不要把这个发现当 blocker(系统当前可用,这是改进项不是回归)
  ```

  **Must NOT do**:
  - 不在备忘里贴出修复 PR 草案
  - 不引入"AI 抽取永远不可靠"等绝对论断
  - 不修改抽取代码

  **Acceptance Criteria**:
  - [ ] 6 章节齐全
  - [ ] 噪声样本与 plan §Context 一致
  - [ ] 假设根因 4 项 + 排查方法每项可执行
  - [ ] 推荐动作分级清晰

### Phase 2 — README 索引

- [ ] 3. **更新 `docs/foundation-optimization/README.md` 的 "专题备忘录" 表**

  追加两行:
  ```
  | [retrieval-benchmark-report-20260513.md](./retrieval-benchmark-report-20260513.md) | 检索基准首份实测:三分支 simple/jiebacfg/jiebaqry 对比 + 上游瓶颈发现 |
  | [entity-extraction-noise-diagnosis-20260513.md](./entity-extraction-noise-diagnosis-20260513.md) | key_entities 噪声诊断:噪声分类 + 假设根因 + 排查动作清单 |
  ```

  **Acceptance Criteria**:
  - [ ] README 含两条新链接
  - [ ] 不改其他章节

---

## Commit Strategy

**1 个 atomic commit**(两个 doc + README 一起):

```
docs(foundation): retrieval benchmark report + entity noise diagnosis

First measured retrieval benchmark across three branches reveals
jiebacfg unconditionally beats simple FTS (ΔMRR +0.04 to +0.37,
latency cost ≤+1ms) but absolute ceiling is set by upstream
key_entities quality. Companion diagnosis memo classifies the
noise (verb phrases / function words / onomatopoeia / chapter
ordinals / truncated nouns) and lists 4 hypotheses with bounded
investigation actions — no fix applied yet.

Constraint: numbers must match .sisyphus/evidence/retrieval-bench-*.json verbatim
Constraint: diagnosis is observation-only, no prompt or extraction code changed
Rejected: re-run analysis on bad branches as a fix | premature, root cause not isolated
Confidence: high (data) / medium (hypotheses)
Scope-risk: narrow
Directive: run retrieval-benchmark on any new branch before claiming retrieval improvements
Tested: cross-checked all 9 numbers in report against evidence JSONs
Not-tested: noise frequency distribution (deferred to investigation step 1)
```

---

## Success Criteria

- [ ] 两份新文档存在且章节齐全
- [ ] README 索引可达
- [ ] 1 个 atomic commit Lore 格式
- [ ] 报告里所有数字 = evidence JSON 数字(逐个核对)
- [ ] 诊断备忘没引入修复行动(只诊断)

---

## Notes for the Executor

1. 必须 `cat .sisyphus/evidence/retrieval-bench-*.json` 校对每个数字 — 不许凭记忆抄
2. 数字四舍五入只到 3 位小数,与 plan 表里一致
3. 噪声样本不要"美化"或"补全"— 原样
4. 假设和事实分清楚 — "假设根因" 章节每条用 "假设" / "可能" / "待验证" 字眼
5. 写完后跑 grep 自检:报告里出现 "建议" / "应该" / "立即" 时必须看上下文,不能跑偏到立刻改代码
6. 报告:文件路径 + 行数 + commit hash + 数字核对截图(grep 输出)
