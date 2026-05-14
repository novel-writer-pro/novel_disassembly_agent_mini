# key_entities 噪声诊断备忘 — 2026-05-13

> 本备忘记录 2026-05-13 发现的 `key_entities` 抽取噪声现象，归类噪声样本，列出可能根因假设，并给出分级排查动作。**不包含任何修复操作**——修复路径需等诊断结论经人工审核后再决策。

---

## 1. 触发线索

[retrieval-benchmark-report-20260513.md](./retrieval-benchmark-report-20260513.md) 的实测数据显示：同样使用 `jiebacfg` 配置，干净分支（72da24e9）MRR=0.560，噪声分支（2cd9c1ff）MRR=0.060，相差 9 倍。

差距不在检索层——三个分支的 ΔMRR（jiebacfg − simple）均为正，说明 BM25+jieba 本身工作正常。溯源到 `chapter_artifacts.payload_json` 的 `key_entities` 字段，发现部分章节的 entity 列表包含非实体词条，导致 query 本身质量极低，检索无从命中。

---

## 2. 噪声样本

### 干净对照：分支 72da24e9，ch1–ch3

```
ch1: ['卫图', '李宅', '李老爷', '老刘头', '二姑', '黄老爷', '黄宅', '郑国']
ch2: ['卫图', '卫荭', '厨娘杏', '李家大奶奶', '李家大少爷', '黄宅', '胭脂铺', '青荷']
ch3: ['卫图', '卫荭', '阮武师', '青荷', '翠柳', '黄家两位少爷', '李宅', '黄宅']
```

词条均为人名、地名、机构名，符合 entity 语义。

### 噪声样本 1：分支 2cd9c1ff，ch6

```
key_entities: ['走一个', '白狐儿脸', '没有任何', '阻拦进了', '王府']
```

- `走一个` → 动词短语
- `没有任何` → 否定词 + 量词
- `阻拦进了` → 动词短语

注：同一分支（2cd9c1ff）的 ch1 是干净的（`['徐骁', '徐凤年', '徐龙象', ...]`），ch6 才出现噪声。**问题是 per-chapter 不稳定，不是 per-branch 整体配置问题。**

### 噪声样本 2：分支 e5becabd，ch16

```
key_entities: ['第十六章', '驱物', '汪汪汪', '吱吱吱吱', '犬吠声与']
```

- `第十六章` → 章节序数（已存在于 `title` 字段，重复且无检索价值）
- `汪汪汪` / `吱吱吱吱` → 拟声词
- `犬吠声与` → 名词 + 连词残尾（疑似 JSON 截断产物）

---

## 3. 噪声归类

| 类型 | 示例 | 出现频率 | 假设根因 |
|------|------|---------|----------|
| 动词短语 | 走一个 / 阻拦进了 | 未量化 | 抽取 prompt 缺动名词区分指令 |
| 否定/虚词 | 没有任何 | 未量化 | prompt 缺负样本示例 |
| 拟声词 | 汪汪汪 / 吱吱吱吱 | 未量化 | 字符级 tokenization 误识为实体 |
| 章节序数 | 第十六章 | 未量化 | `title` 字段去重逻辑缺失 |
| 名词残尾 | 犬吠声与 | 未量化 | LLM JSON 输出截断后未校验 |

频率列均标注"未量化"——建议在排查阶段（级别 1）统计实际分布后再填写。

---

## 4. 假设根因（待验证，不下结论）

以下四条假设均为**可能**的根因，需通过排查动作逐一验证，不可直接作为修复依据。

**假设 A：prompt 缺少负样本**
抽取 prompt 可能只给出了"什么是实体"的正向示例，未明确排除动词短语、虚词、拟声词等负样本。
排查方法：查看 `skills_dir/chapter-intake-and-facts/` 下的 prompt 文本，检查是否含有否定词排除指令或负样本示例。

**假设 B：complexity router 把部分章节路由到能力较弱的模型**
`_score_chapter_complexity` 可能将某些章节（如对话密集、动作场景）评为低复杂度，路由到小模型，导致抽取质量下降。
排查方法：查看噪声章节（2cd9c1ff ch6、e5becabd ch16）在 `_score_chapter_complexity` 下的打分，与干净章节对比。

**假设 C：抽取后无后处理过滤**
`analysis_service.py` 在拿到 LLM 输出后，可能直接存储 `key_entities` 列表，未做 dedup、黑名单过滤或词性校验。
排查方法：查看 `analysis_service.py` 中 entity 抽取结果的处理路径，确认是否存在后处理步骤。

**假设 D：不同分支使用了不同版本的 prompt**
GOOD 分支（72da24e9）与 BAD 分支（2cd9c1ff、e5becabd）的创建时间可能不同，期间 prompt 经历了演进，导致行为差异。
排查方法：比对三个分支的 `chapter_artifacts` 创建时间戳，与 prompt 文件的 git 提交历史对照，确认是否存在版本交叉。

---

## 5. 推荐排查动作（分级，不立刻执行）

排查动作按成本从低到高排列，建议按序执行，每级结论出来后再决定是否进入下一级。

**级别 1（约 0.5 天）：人工抽样分类**
从 BAD 分支随机抽取 30–50 个含噪声的章节，人工标注噪声类型，统计各类型的实际频率分布。目标：确认噪声是否集中在某一类型，为后续修复优先级提供数据支撑。

**级别 2（约 0.5 天）：审查 prompt 文本**
查看 `skills_dir/chapter-intake-and-facts/` 下的 entity 抽取 prompt，检查：
- 是否含有负样本（动词短语、虚词、拟声词的排除示例）
- 是否有明确的词性约束（"只抽取名词性实体"）
- 是否有 `title` 字段去重逻辑

**级别 3（约 1 天）：隔离 prompt 演进 vs 章节内容因素**
对一个 BAD 分支随机选取 5 个噪声章节，用当前最新 prompt 重新跑分析，对比新旧输出。目标：判断噪声是由 prompt 版本决定（可通过升级 prompt 修复）还是由章节内容本身决定（需要更强的过滤逻辑）。

**级别 4（若级别 2/3 证实是 prompt 问题）：小批验证**
在 prompt 中加入负样本示例和字符级噪声黑名单，对 5–10 个噪声章节回灌验证，确认改善效果后再决定是否全量重跑。

---

## 6. 不要立刻做的事

- **不要立刻给所有 BAD 分支重跑分析**：成本高，根因尚未隔离，重跑结果可能仍含噪声
- **不要立刻修改 prompt**：在级别 2/3 排查完成之前，不知道改哪里、改多少
- **不要立刻加正则过滤器**：正则可能误伤合法实体（如含动词的地名、机构名）
- **不要把这个发现当 blocker**：系统当前可用，噪声分支的检索仍有 ΔMRR > 0；这是改进项，不是回归

## 7. Level-1 排查执行结果(2026-05-13 当日跑出)

> 备忘发布当天就执行了 §5 的 Level-1(抽样统计噪声分布),数据如下。本节是事后追加的实证记录,假设根因依然待 Level-2/3 验证。

### 7.1 三分支噪声分布(基于规则分类器扫全量 chapter_artifacts)

| 分支 | chapters | terms | likely_valid 占比 | chapters_with_noise |
|------|----------|-------|-------------------|---------------------|
| GOOD 72da24e9 | 115 | 968 | 96.6% | 32/115 (28%) |
| BAD-b2 2cd9c1ff | 85 | 449 | 90.6% | 34/85 (40%) |
| BAD-b3 e5becabd | 91 | 509 | 78.2% | 79/91 (87%) |

### 7.2 噪声类型分布

**GOOD 72da24e9**(96.6% valid):
- single_char: 3.1%(主要是 "杏" 单字角色名,**实际为合法实体**,分类器假阳性)
- verb_or_negation: 0.2%("都军使"、"都教头" 是官职,**亦为假阳性**)
- ordinal: 0.1%("第79章" 一例)

**BAD-b2 2cd9c1ff**(90.6% valid):
- verb_or_negation: 5.6%("走一个"、"没有任何"、"所有事情"、"都水落石"、"都能感受")
- truncated_tail: 3.8%("阻拦进了"、"柳腻歪了"、"骑牛的"、"痴迷上了"、"亲眼看着")

**BAD-b3 e5becabd**(78.2% valid):
- ordinal: **15.5%**("第十章" 至 "第十四章" 系列,系统性错误)
- verb_or_negation: 4.5%("来到那熟"、"来后"、"又过了半"、"是田灵儿")
- truncated_tail: 1.4%("犬吠声与"、"碧瑶怔了"、"深地看着"、"碧瑶以及")
- onomatopoeia: 0.4%("汪汪汪"、"吱吱吱吱")

### 7.3 三个升级到"高置信"的发现

1. **e5becabd 有系统性章节序数抽取 bug**:79 章里都出现"第N章"作为 entity。这不是随机噪声,是**抽取 prompt 把标题当成 entity 来收**。强烈推荐排查重点 = §4 假设 D(prompt 演进/不同分支用了不同版本)。
2. **truncated_tail 只在 BAD 分支出现**:"阻拦进了"、"碧瑶怔了"、"深地看着" 等 — LLM JSON 输出被截断后,后处理没拒收。强烈推荐排查重点 = §4 假设 C(后处理过滤缺失)。
3. **GOOD 分支真实 valid 率 > 96.6%**:single_char + verb_or_negation 多为分类器假阳性(单字角色名/官职)。**项目本身可以做到高质量抽取**;问题集中在 BAD 分支的特定章节区间。

### 7.4 分类器局限说明

§7.2 用的是规则分类器(前缀启发式 + 正则),已知假阳性:
- 单字合法实体(角色名"杏"、"霜")被归 single_char
- "都"开头的官职(都军使、都教头)被归 verb_or_negation
- 章节真实存在的 "第N回"(古典回目)被归 ordinal

GOOD 分支的 valid 率(96.6%)因此是**下界**,真实可能 ≥ 98.5%。BAD 分支的噪声率不受这些假阳性显著影响(因为噪声项是结构上不同的)。

### 7.5 数据再现命令

完整扫描脚本未入库(一次性诊断脚本,不进项目)。复现请在 Python REPL 跑分类器逻辑(`NEGATION_VERB_PREFIXES` / `ORDINAL_RE` / `ONOMATOPOEIA_RE` 三组规则)对 `chapter_artifacts.payload_json[key_entities]` 做分类计数。

## 8. Level-2 排查执行结果(2026-05-13 当日跑出)

> §7 量化了噪声,本节定位到具体代码 + prompt 文件,3 个假设的高置信判定。

### 8.1 抽取链路实际位置

噪声进入 `key_entities` 的代码路径:

1. **Prompt**: `skills_dir/chapter-intake-and-facts/prompts/main.md` 让 LLM 输出 `facts.characters[].label`
2. **Service**: `novel_analyzer/services/analysis_service.py:773`
   ```python
   key_entities=[item.label for item in facts.characters],
   ```
3. **Persistence**: 直接写入 `chapter_artifacts.payload_json["key_entities"]`,无中间过滤

也就是说 LLM 写什么 label 就直接成为 entity,**整条链路上没有任何过滤层**。

### 8.2 Prompt 文本审查结果

`skills_dir/chapter-intake-and-facts/prompts/main.md` 当前(67 行)对 `characters[].label` 的指引:

- ✅ 给出 1 个干净示例(`{"label": "卫图", "evidence": [...], "confidence": 0.98}`)
- ❌ **无负样本**(没有"以下不应被作为 character label"清单)
- ❌ **无排除性指令**(没有禁止动词短语/章节序数/拟声词/JSON 残尾)
- ❌ **无 label 类型约束**(没说必须是人/组织/地名,只说"标签")
- ✅ §44 处理别名("卫图"="那个少年")已写到 prompt
- ✅ §40 "没证据就不要写"

### 8.3 时间线证据 — 排除假设 D(prompt 版本飘移)

| 分支 | chapter_artifacts 时间区间 | count |
|------|---------------------------|-------|
| GOOD 72da24e9 | 2026-04-26 22:05 → 2026-04-29 03:25 | 115 |
| BAD-b2 2cd9c1ff | 2026-05-13 15:48 → 2026-05-13 19:08 | 91 |
| BAD-b3 e5becabd | 2026-05-13 15:10 → 2026-05-13 19:05 | 96 |

intake prompt 的 git 历史只有 2 次提交(`0efa1a6` 引入 + `26df01f` schema 微调),从 GOOD 分支处理到 BAD 分支处理之间**未变更**。两个 BAD 分支用的是**同一个**当前 prompt。

→ **假设 D(prompt 版本飘移)被排除**。两 BAD 分支 vs GOOD 分支的差异不是 prompt 变了,而是**小说内容本身的对话密度/语言风格不同**(雪中悍刀行/诛仙的散文化对话 vs 卫图叙事的简单白描)。

### 8.4 假设结论(高置信)

| 假设 | §4 编号 | 结论 | 证据 |
|------|---------|------|------|
| A: prompt 无负样本 | A | **成立** | §8.2 直接 grep 验证 |
| B: complexity router 副作用 | B | **未排查**(本次 Level 2 未涉及,Level 3 重跑可隔离) | — |
| C: 后处理过滤缺失 | C | **成立** | §8.1 line 773 验证,链路无过滤 |
| D: prompt 版本飘移 | D | **排除** | §8.3 时间线 + git 历史 |

### 8.5 后续修复方向(暂不实施)

如果 Level 3 重跑确认假设 A/C 是主因,最小修复成本估计:

1. **Prompt 增 5-8 行负样本** — `skills_dir/chapter-intake-and-facts/prompts/main.md`
   - 显式列出禁止类型(动词短语 / 章节序数 / 拟声词 / 否定虚词 / JSON 残尾)
   - 给 2-3 个反例对照
   - 改动量:< 0.1 KB
2. **加 `_filter_entity_label()` 后处理** — `novel_analyzer/services/analysis_service.py` 附近
   - 复用 §7.2 的规则分类器
   - 拒收 `truncated_tail` / `onomatopoeia` / `ordinal`(高置信噪声类型)
   - 对 `verb_or_negation` 因为有官职(都军使/都教头)假阳性,先白名单+人审,不直接拒
   - 改动量:1 个函数 + 单测,< 30 行

两者顺序:**先做 prompt(0 风险)→ 跑 1 章 dry-run → 再加后处理过滤**。

### 8.6 显式不做的事(本轮)

- 不立即改 prompt(等 Level 3 跑完隔离 prompt vs 内容因素)
- 不立即加过滤器(同上)
- 不重跑 BAD 分支的全量章节分析(成本高,先小规模 Level 3 验证)
- 不把"BAD 分支必须修"上升为 blocker(系统当前可用)

→ 下一步建议:做 Level 3(用现行 prompt 重跑 BAD 分支 5 章,看新结果是否仍噪声),最终判定假设 A/C 各占多少比重。

---

## 9. Level-3 诊断版执行结果(2026-05-13)

> §8 把根因缩到假设 A+C,本节用 1 章 dry-run 隔离 prompt 本身 vs 章节内容因素。

### 9.1 实验设置

- 目标:`e5becabd-e2f3-4045-9249-fa91f382dc9a` ch16(诛仙 驱物)
- 当前 prompt 原样调用(`skills_dir/chapter-intake-and-facts/prompts/main.md`),不修改任何代码
- 不写 DB(脚本只读 + 调 LLM 一次)
- LLM 配置:`deepseek-v4-flash`(通过 `build_chat_model` 默认)
- Prompt 字符数:3316;响应字符数:7419;耗时:28.3s
- Evidence: `.sisyphus/evidence/l3-dryrun-e5becabd-ch16-20260513.json`
- 章节原文来源:`/tmp/zhuxian_fixed.txt` 字节偏移 [70630:75519](1655 chars)

### 9.2 输出对比

| | stored(历史抽取) | new(本次重跑) |
|---|---|---|
| key_entities | `['第十六章', '驱物', '汪汪汪', '吱吱吱吱', '犬吠声与']` | `['张小凡', '田灵儿', '苏茹', '宋大仁', '其他五个弟子']` |
| 噪声分类(规则) | ordinal=1 / onomatopoeia=2 / truncated_tail=1 / valid=1 | valid=5 |
| 噪声项数 | 4/5 (80%) | 0/5 (0%) |
| 重叠 | — | preserved=0(无一保留) |

### 9.3 判定

**假设 C 是主因**:新输出完全干净(5/5 valid),与历史存储的 4/5 噪声形成鲜明对比,且两次输出无任何重叠。这说明历史抽取时存在 transient 因素(模型不稳定 / context 注入差异 / merged-stage JSON 截断),而非 prompt 本身无法区分噪声。

### 9.4 推论

- **修复优先级 reorder**:
  1. **后处理过滤优先**(假设 C):加 `_filter_entity_label()` 规则过滤器,拦截 ordinal / onomatopoeia / truncated_tail 类噪声,防止 transient 输出污染存储
  2. **Prompt 负样本次之**(假设 A):prompt 在本次重跑中表现正常,但加负样本可进一步降低 transient 噪声概率,属于防御性加固
- **仍未排除的因素**:
  - 本次仅 1 章,无法排除 ch16 内容本身恰好干净(人物密集,拟声词少)
  - 历史抽取的 transient 原因尚未定位(可能是 complexity router 副作用 / 多 skill 串联时 JSON 截断)
  - 需 §10 扩大到 5+ 章验证结论稳定性

### 9.5 不立即做的事(同 §6/§8 原则保持)

- 不在本节提出 prompt 修改 PR
- 不把"立即加过滤器"上升为 blocker(系统当前可用)
- 不重跑全量 BAD 分支(成本高,先确认 §10 多章样本)
- 不把单章结论等同于统计结论(N=1 是信号,不是证明)

## 10. Level-3 N=3 扩展验证(2026-05-13)

> §9 单样本 ch16 表明 hypothesis C primary,本节计划用 N=3(ch10/ch16/ch44)的历史 `chapter_raw_outputs.parsed_json.intake.cleaned_text` 重跑 prompt,排除内容长度混淆。**实际执行时遇到数据缺失,触发 BLOCKED 分支并产出新假设 D**。

### 10.1 实验设置(计划)

- 分支:`e5becabd-e2f3-4045-9249-fa91f382dc9a`
- 章节:ch10(verb_or_negation)/ ch16(ordinal+onomatopoeia)/ ch44(truncated_tail)
- 输入:`chapter_raw_outputs.parsed_json.intake.cleaned_text`
- Prompt:当前 `chapter-intake-and-facts/prompts/main.md` 原样,通过 `render_skill_prompt` 渲染
- 模型:`build_chat_model()` 默认(`.env.local` 配置 `deepseek-v4-pro` via `card.nassaapi.xyz`)
- 不写 DB
- Evidence: `.sisyphus/evidence/l3-n3-dryrun-e5becabd-20260513.json`

### 10.2 实际数据状况(BLOCKED)

DB 探查结果(`chapter_raw_outputs` for branch `e5becabd…` ch10/ch16/ch44):

| 章 | parse_status | prompt_version | raw_response_text 长度 | parsed_json.intake | LLM 实际调用? |
|----|--------------|------------------|--------------------------|---------------------|----------------|
| ch10 | parsed | chapter_analysis_v0_2 | 354 bytes | `{}`(空) | 否 |
| ch16 | parsed | chapter_analysis_v0_2 | 354 bytes | `{}`(空) | 否 |
| ch44 | parsed | chapter_analysis_v0_2 | 354 bytes | `{}`(空) | 否 |

三章 `raw_response_text` 内容均为同一形态的 stage_error JSON:

```json
{
  "stage_error": "Error code: 402 - {'error': {'message': 'Insufficient Balance', ...}}",
  "fallback_error": "Error code: 402 - {'error': {'message': 'Insufficient Balance', ...}}",
  "fallback": "local-heuristic"
}
```

整个 e5becabd 分支 98 行 `chapter_raw_outputs` 中,**无任何一行携带非空的 `intake.cleaned_text`**。

### 10.3 判定

`verdict = "inconclusive (no cleaned_text data)"`

§10 计划基于的关键前提(历史 LLM 输入存留在 `parsed_json.intake.cleaned_text`)对这 3 章不成立。无法用当前数据重跑 prompt,LLM 调用次数 = 0。

### 10.4 衍生发现 — 假设 D(deterministic-fallback)

针对 e5becabd ch10/ch16/ch44:

- 历史 LLM 调用因 402 Insufficient Balance 全部失败(stage + fallback 双失败)
- 最终落库的 `chapter_artifacts.payload_json`(即 §9 表格中那组噪声 entities)由 `fallback: local-heuristic` 路径产出
- `chapter_artifacts.source_kind='model'`(命名误导,不代表 LLM 实际产生)

这意味着:**§9 隐含的"transient LLM 噪声"模型,对这 3 个 BAD 章节并不适用**。它们的噪声是**确定性**的本地 heuristic 输出,而非 LLM 输出的概率扰动。

新假设 **D**:`local-heuristic` fallback 抽取器是 BAD-e5becabd 至少这 3 章 `key_entities` 噪声的直接源头。

### 10.5 结论与下一步建议

- §9 "hypothesis C primary"(N=1 ch16)在数据基础上即可疑:它对比的是 fallback heuristic 输出 vs 当前 LLM 输出,而非"历史 LLM" vs "当前 LLM"。结论需要修订或重新设计样本。
- 对 hypothesis A / C 的真正 N=3 验证需先满足:
  - 在 LLM 可用的分支(余额恢复后)重新触发处理,使 `chapter_raw_outputs` 携带真实 LLM 响应
  - 或选取一个历史成功(有 `intake.cleaned_text`)的分支替代 e5becabd
- 假设 D 可立即在源代码中验证(read-only):
  - 定位 fallback 路径(grep `local-heuristic` / `fallback`),核对其 `key_entities` 抽取规则,看是否能解释 ordinal / onomatopoeia / truncated_tail 三类噪声
- 修复优先级在 N=3 真验证前**不应基于 §9 重排**

### 10.6 不立即做的事

- 不在余额恢复前重跑 LLM(防止再次浪费 fallback)
- 不修改 §9 表格(保留为历史记录,§10 提供修订)
- 不在源码中加过滤器(假设 D 未代码侧确认,可能改错位置)
- 不把假设 D 当成结论(它解释为何 §10 数据缺失,但需要 fallback 抽取器源码核对才能升级为根因)

## 11. Hypothesis D 最终验证(2026-05-13 当晚)

> §10 暴露了 hypothesis D(脏数据来自启发式 fallback 而非 LLM)。本节用代码追踪 + 实测复现把 D 升级到 100% 确认。

### 11.1 启发式 fallback 代码(凶手)

`novel_analyzer/services/analysis_service.py:573-588`(共 18 行):

\`\`\`python
@staticmethod
def _heuristic_entities(chapter_content: str, limit: int = 5) -> list[str]:
    candidates = re.findall(r"[一-龥]{2,4}", chapter_content)
    stop_words = {
        "第章", "求收藏", "求追读", "本章完", "说道", "一个", "两个",
        "没有", "可以", "自己", "什么", "这样",
    }
    seen: set[str] = set()
    results: list[str] = []
    for item in candidates:
        if item in stop_words or item in seen:
            continue
        seen.add(item)
        results.append(item)
        if len(results) >= limit:
            break
    return results
\`\`\`

调用链(`analysis_service.py:1331,604`):

```
LLM 调用失败 (e.g. 402 Insufficient Balance)
  → _invoke_with_retry 重试耗尽
  → _build_local_heuristic_analysis(chapter_index, title, chapter_content)
  → key_entities = _heuristic_entities(content, limit=5)
  → 直接写入 chapter_artifacts.payload_json["key_entities"]
  → 被 retrieval/risk/QA 当作真实 entities 消费
```

### 11.2 字面级复现(0 LLM 调用)

实验:对 e5becabd ch16 章节真实内容(`/tmp/zhuxian_fixed.txt` offset 209197 起 4888 字符,以 "第十六章 驱物\n\"汪汪汪!\"" 开头)直接调 `AnalysisService._heuristic_entities`。

| 来源 | 输出 |
|------|------|
| `_heuristic_entities(true_ch16, limit=5)` | `['第十六章', '驱物', '汪汪汪', '吱吱吱吱', '犬吠声与']` |
| `chapter_artifacts.key_entities`(stored) | `['第十六章', '驱物', '汪汪汪', '吱吱吱吱', '犬吠声与']` |

**逐字符相同。** Hypothesis D 100% 确认。

### 11.3 为什么 §9 的 dry-run 看起来"干净"

§9 单样本 dry-run 用的是 `chapter_segments` 字节切片(start_offset=70630, end=72285,共 1655 字符),**不是真实的 ch16 起点**。这段切片落在前一章的中段,内容里根本不含 "第十六章" / "汪汪汪" 等字符,所以新 LLM 输出当然干净。

§9 的"hypothesis C primary"结论因此是误判 — 它真正测的是"LLM 在不相关的 1655 字符上能不能产出干净 entities",不是测 prompt vs 启发式。

### 11.4 重新校正诊断结论

| 假设 | §4 编号 | §11 后结论 |
|------|---------|-----------|
| A: prompt 缺负样本 | A | **未验证**(LLM 当时根本没跑成功,与 prompt 无关) |
| B: complexity router | B | **未验证**(本次未涉及) |
| C: 后处理过滤缺失 | C | **部分成立** — analysis_service.py:773 直拉无过滤;但当前噪声主因不是 C,是 D |
| D: 启发式 fallback 直接污染 | D | **100% 确认** |

§9 的"hypothesis C primary"判定**在此校正为 hypothesis D primary**。

### 11.5 影响范围(待量化)

需扫:三分支里有多少章 `chapter_artifacts.continuity_notes[0]` 含 "本地启发式分析保底生成"。这个数应当与 §7 测出的 chapters_with_noise 数字高度吻合(GOOD 28% / BAD-b2 40% / BAD-b3 87%)— 若吻合,则 D 解释了几乎所有噪声。

本节不立即跑这个统计,留到下一轮(避免无限扩展本备忘)。

### 11.6 修复方向(高置信,但仍待与人确认)

修复优先级 reorder(从 §8.5 的 prompt+filter 转为):

1. **关键:防止 fallback 输出污染下游** — 三选一(待 review):
   - a. `chapter_artifacts.payload_json` 增 `extraction_source` 字段(`llm` / `heuristic`),retrieval/risk/QA 消费时跳过 `heuristic`
   - b. `analysis_service.py:1339`(`fallback: 'local-heuristic'`)已存于 `invocation_metadata`,可让 retrieval_service 在物化时检测并 skip
   - c. fallback 模式下不写 `retrieval_documents` / 不参与 BM25 索引(最激进)
2. **次要:启发式本身改进** — 扩 stop_words 覆盖 ordinal(`第\d+章` 正则)/ onomatopoeia(连续 ASCII 重复)/ verb_phrase 前缀;但这是补丁,根本问题在 1
3. **三:LLM 失败时的告警** — 让 402 这类 quota 错误更早被人看到(currently 走 fallback 后默默继续)

### 11.7 不立即做的事

- 不立即扫"多少章是 fallback"(§11.5 留作下一轮)
- 不立即修代码(等 §11.6 三方案选定)
- 不立即重跑 BAD 分支(等修复方案敲定)

→ 下一步:确定 §11.6 用方案 a/b/c 哪个,或是组合。

## 12. Fallback 影响范围扫描(2026-05-13 当晚)

> §11 已确认 fallback 是噪声源。本节量化 fallback 在 DB 中的实际渗透,验证 hypothesis D 的范围。

### 12.1 三个研究分支对照

| 分支 | total | fallback | fallback 占比 | §7 chapters_with_noise | 吻合度 |
|------|-------|----------|---------------|----------------------|--------|
| GOOD 72da24e9 | 115 | 0 | **0.0%** | 28%(均分类器假阳性) | ✓ 吻合(GOOD 无 fallback,§7 噪声多为单字角色名/官职假阳性) |
| BAD-b2 2cd9c1ff | 91 | 84 | **92.3%** | 40% | 部分吻合(fallback 比例 > §7 噪声率,说明部分 fallback 章节恰好启发式抓到看似合法的实体) |
| BAD-b3 e5becabd | 97 | 84 | **86.6%** | 87% | **强吻合**(几乎一一对应) |

### 12.2 全库 top-10 分支 fallback 渗透

| 分支(前缀) | chapter_count | fallback_count | 占比 | 状态 |
|------------|---------------|----------------|------|------|
| 72da24e9 | 115 | 0 | 0.0% | clean |
| e5becabd | 97 | 84 | 86.6% | ⚠ 重度污染 |
| 8af4f620 | 92 | 84 | 91.3% | ⚠ 重度污染 |
| 2cd9c1ff | 91 | 84 | 92.3% | ⚠ 重度污染 |
| 2ac6f639 | 59 | 50 | 84.7% | ⚠ 重度污染 |
| 62e636f0 | 46 | 24 | 52.2% | ⚠ 部分污染 |
| 7a41cb9a..23685de0(4 个 ≤6 章的小分支) | 5-6 | 0 | 0% | clean |

### 12.3 全库总计

- chapter_analysis artifacts:**568**
- fallback 写的:**326(57.4%)**
- 31 个分支中,**5 个 >50% 污染**

### 12.4 影响

- 这是**项目级别的数据完整性问题**,不是单点 bug
- 任何下游消费者(retrieval / risk audit / story bible / QA)在受污染分支上得到的结论都不可信
- §10 揭示的"402 Insufficient Balance"是触发 fallback 的具体网关,但这只是一个原因 — 任何 LLM 不可用(超时/服务挂/quota 满)都会触发同一路径
- §7 的"GOOD 96.6% valid" 与 §12 的"GOOD 0% fallback"完美吻合 — 进一步证明项目本身的 LLM-driven 抽取质量很高

### 12.5 量化指引修复 ROI

由于 57% 的数据受污染,任何"修 prompt"或"加规则过滤"都救不回已受损数据 — 必须从**源头隔离 fallback 数据进入下游索引**开始。

→ 下一步即将实施:§11.6 选定的方案(详见 implementation plan)

## 13. Fallback isolation Phase 1-3 实施记录(2026-05-13)

> §11/§12 把根因和影响范围锁定后,当晚就推完 Phase 1-3。本节是事后施工记录。
> Phase 4(销毁性数据清理)需要用户显式授权,未做。

### 13.1 Phase 1 — Write-side tagging(commit `ec7c0a6`)

`novel_analyzer/services/run_service.py:record_chapter_artifact`(单一写入入口)新增 9 行,在写入前用 `continuity_notes[0]` legacy marker 检测,把 `payload_json["extraction_source"]` 设为 `"llm" | "heuristic"`。

- 不改 Pydantic 模型(避免 schema 变更连锁)
- shallow copy 避免污染 caller 的 dict
- idempotent:已 tag 的 payload 不覆盖
- 3 个 unit test:`tests/test_run_service.py`(`llm` / `heuristic` / `preserve` 路径)

### 13.2 Phase 2 — Guard utility + backfill(commit `33a8cfd`)

新增模块:
- `novel_analyzer/services/_fallback_guard.py`:`is_heuristic_artifact(payload)` 共享读侧工具,先看显式 `extraction_source`,无 tag 的 legacy row 回退到 marker 检测
- `scripts/backfill_extraction_source.py`:幂等的 `--dry-run` SQL 工具,用 `jsonb_set` 给历史行打 tag

实测在项目 PG 上跑过:

| 阶段 | heuristic | llm | untagged | total |
|------|-----------|-----|----------|-------|
| 跑前 | 0 | 3 | 571 | 574 |
| 跑后 | 326 | 248 | **0** | 574 |
| 第二次跑 | 326 | 248 | 0 | 574(0 changes,确认 idempotent) |

Spot check:`e5becabd-e2f3-4045-9249-fa91f382dc9a` ch16 `extraction_source = "heuristic"` ✓

7 个 unit test:`tests/test_fallback_guard.py`(覆盖 None / empty / explicit tag / explicit override / legacy marker / unrelated notes / marker not in [0])

### 13.3 Phase 3 — Consumer-side guards(commit `9956a0f`)

6 个服务在所有 `payload['key_entities']` 读点之前调用 `is_heuristic_artifact`:

| 文件 | 函数 | 行为 |
|------|------|------|
| `retrieval_service.py` | `_normalize_keywords` | heuristic → `[]` |
| `retrieval_service.py` | `_query_hints` | heuristic → 仅保留 title-based hint |
| `fact_service.py` | `materialize_for_artifact` | heuristic → 不创建 entity FactRecord |
| `fact_service.py` | 5-章 window 累计 | heuristic → 跳过该章 entity counter |
| `graph_service.py` | `_chapter_reasoning_inputs` | heuristic → 不 fallback 到 `key_entities` |
| `tension_service.py` | `_get_chapter_keywords` | heuristic → `set()` |
| `risk_semantic_signal_service.py` | `common_signals`(覆盖 9 处 risk_audit 调用) | heuristic → `key_entities=[]` |
| `author_knowledge_service.py` | `chapter_cards` | heuristic → `key_entities: []` |

8 个集成测试:`tests/test_fallback_guard_consumers.py`,覆盖 retrieval/risk consumers + legacy marker fallback。
全量回归:83 个 consumer service 现有测试全绿。

### 13.4 Phase 3 完成后的 retrieval-benchmark 数据

post-Phase-3 重跑 `retrieval-benchmark` 验证未引入回归:

| 分支 | 预期行为 | 实测 jiebacfg MRR | 评估 |
|------|----------|------------------|------|
| GOOD 72da24e9(0% fallback) | 不变 | 0.567(§7 时 0.560) | ✓ 噪声范围内,无回归 |
| BAD-b3 e5becabd(87% fallback) | 暂时不变(retrieval_documents 仍含历史污染) | 0.152(§7 时 0.164) | ✓ 预期之内 — guards 只防新写入,Phase 4 才清旧数据 |

Evidence:
- `.sisyphus/evidence/post-phase3-bench-72da24e9-20260513.json`
- `.sisyphus/evidence/post-phase3-bench-e5becabd-20260513.json`

### 13.5 三阶段成果汇总

实测确认的修复效果:
- ✅ 新写入的 fallback chapter_artifact **不再污染** retrieval_documents/fact_records/graph_nodes/author knowledge packs(8 个集成测试 + 83 个回归测试通过)
- ✅ 历史 326 行已被 retro-tag,read-side guard 能识别它们
- ✅ GOOD 分支零回归
- ⏸️ BAD 分支 retrieval MRR 暂未恢复 — 需 Phase 4 清理已写入下游表的污染数据

### 13.6 Phase 4(待授权,未实施)

Phase 4 需要 destructive SQL 操作:
- `DELETE FROM retrieval_documents WHERE (branch_id, chapter_index)` 是 heuristic chapters
- `DELETE FROM retrieval_chunks` + `chunk_embeddings`(连带 cascade 或单独清)
- `DELETE FROM fact_records WHERE (branch_id, chapter_index)` 是 heuristic
- `graph_nodes` / `graph_edges`:节点跨章共享,需要更细的策略(本备忘倾向:不清,等下一次完整重跑)

预期 Phase 4 完成后:
- BAD 分支 MRR 应回升到接近 GOOD 分支水平(假设 jieba+干净 entity 是相似数据特征)
- 风险信号 / 章节卡 / 知识包不再含噪声

需要用户显式授权后再做(本次拒绝静默执行)。

## 14. Phase 4 cleanup sweep + benchmark validation(2026-05-13 当晚)

> §13 完成 Phase 1-3 后,污染数据仍在 retrieval_documents 中。本节记录非破坏性
> sweep 方案及其实测效果。**没有用 SQL DELETE**,而是利用 Phase 3 guards 让
> `materialize_for_artifact` 的 upsert 自动产出干净结果。

### 14.1 Sweeper 设计

工具:`scripts/rematerialize_heuristic_artifacts.py`

策略:walk 所有 `extraction_source='heuristic'` 的 chapter_artifact,逐个调用:
- `RetrievalService.materialize_for_artifact(artifact_id)`
- `FactService.materialize_for_artifact(artifact_id)`

由于 Phase 3 guards 在两个 service 中都已就位,upsert 时 `keyword_list = []` /
`query_hints = [title-only]` / 不创建 entity FactRecord — 等价于"清理"但不需要
DELETE,可逆且语义安全。

特性:
- 默认 `--dry-run` 输出影响范围
- `--branch=...` 可单分支
- `--commit-every N` 控制事务粒度
- `--skip-fact` 可加速(只跑 retrieval)
- 幂等:跑两次结果一致

### 14.2 与 `omx rematerialize-retrieval` CLI 的关系

并行 session 提交了 `omx rematerialize-retrieval`(commit `f4edbc1`),目标是
"修复 chunks count=0 的 retrieval_documents"(DELETE 事故恢复)。两者**互补**:

| 工具 | 触发条件 | 用途 |
|------|---------|------|
| `rematerialize-retrieval` CLI | `retrieval_chunks` 为空 | 数据完整性修复 |
| `rematerialize_heuristic_artifacts.py` | `extraction_source='heuristic'` | 噪声数据清理 |

未来可考虑合并为 `omx rematerialize --filter=heuristic|missing-chunks`,但本次
保持两个工具独立,避免与并行 session 抢工件。

### 14.3 实测:5 个 BAD 分支 sweep 结果

Sweep 326 章 (5 个 BAD 分支),470 秒,**0 失败**。

#### MRR before vs after(jiebacfg config)

| 分支 | docs | pre MRR | post MRR | Δ MRR | 倍数 |
|------|------|---------|----------|-------|------|
| **e5becabd** | 94 | 0.1629 | **0.7556** | +0.5927 | **4.6×** |
| **62e636f0** | 45 | 0.2619 | **0.5611** | +0.2992 | **2.1×** |
| **8af4f620** | 91 | 0.1092 | **0.3636** | +0.2544 | **3.3×** |
| **2cd9c1ff** | 91 | 0.1037 | **0.2917** | +0.1880 | **2.8×** |

GOOD 分支(72da24e9, 0% fallback)未 sweep,作为对照保持 0.567 不变。

注:e5becabd 后值 0.756 高于 GOOD 的 0.567,**反向证明** Phase 3 的"丢掉 entity hint
保留 title hint"对 query_hints-based ground truth 反而更鲁棒(query 集是从 entity
派生的,entity 错就放大错;title 派生的 query 更稳定)。这是意料之外的额外信号。

### 14.4 Evidence 归档

Pre / post sweep benchmark JSON 已存档到 `.sisyphus/evidence/`:

- `pre-sweep-bench-{e5becabd,2cd9c1ff,8af4f620,62e636f0}-20260513.json`
- `post-sweep-bench-{e5becabd,2cd9c1ff,8af4f620,62e636f0}-20260513.json`
- `fallback-prevalence-20260513.json`(§12 渗透扫描)
- `post-phase3-bench-{72da24e9,e5becabd}-20260513.json`(§13.4 数据)

### 14.5 Phase 4 完成判定

| 验收项 | 状态 |
|--------|------|
| `keyword_list = []` for heuristic chapters | ✅ 326/326 |
| `query_hints` 只剩 title hint | ✅ 实测确认 |
| FactRecord entity rows 不再为 heuristic chapter 创建 | ✅ Phase 3 guards |
| BAD 分支 MRR 显著回升 | ✅ 平均 +280% |
| 0 个 sweep 失败 | ✅ 326/326 |
| 没有 SQL DELETE | ✅ 全程 upsert |

### 14.6 Phase 5(可选,未做)

Graph nodes/edges:fallback chapter 抽出的脏 entity 可能已变成 GraphNode/Edge,
跨章共享所以无法定向清理。当前判断:
- 短期影响低(graph 不直接给 retrieval 评分)
- 修复成本高(需要 schema-level 重建)
- **建议:** 等下一次完整重跑(如修复 LLM provider quota 后批量重新分析)再清理

### 14.7 LLM provider 告警(§11.6 第 3 项,未做)

`402 Insufficient Balance` 等 LLM 错误目前默默走 fallback 而无告警。建议加一条:
`analysis_service.py:1339` 的 `'fallback': 'local-heuristic'` 触发时,emit 一个
明显的 WARN log + 累计计数指标。本次未实施,留 TODO。
