# 风险审查 fresh10 真库核验结果（2026-05-02）

## 1. 核验目标

对样例小说前 10 章执行一次 **fresh PostgreSQL 真库复跑**，验证：

1. 风险审查主链是否能在全新/正式 Alembic schema 下跑通
2. 前 10 章的风险卡结论是否稳定
3. 当前真实阻塞是内容问题还是系统实现问题

---

## 2. 本次运行对象

- 源文本：`/home/user/txt111/novel.txt`
- 新鲜 run：`ac9449b9-7326-474f-bb72-4416375a7491`
- 新鲜 branch：`62e636f0-c901-4167-aa1c-aff3da9c83ef`

最终状态：

- `completed_chapters = 10`
- `failed_jobs = 0`
- `running_jobs = 0`
- `next_chapter = 11`

---

## 3. 真环境前置条件结果

### PostgreSQL / pgvector

- `database_exists=true`
- `can_connect=true`
- `initialized_schema=true`
- `installed_extensions=pg_trgm,vector`
- `ok=true`

### LLM

当前配置：

- provider: `vip1129`
- model: `gpt-5.4-mini`

最小实调用返回：`OK`

### Embedding

- ONNX `bge-m3` smoke 通过

---

## 4. 前10章 fresh 风险卡结果

## A. 低风险、无明确异常的章节

- 第 1 章
- 第 4 章
- 第 5 章
- 第 10 章

这些章节的 risk card 结论均为：

- `overall_risk_level = low`
- 无 top risk
- 当前更接近“覆盖度不足/早期信息不足”，不是确认异常

## B. 出现低风险人工复核候选的章节

- 第 2 章
- 第 3 章
- 第 6 章
- 第 7 章
- 第 8 章
- 第 9 章

### 第 2 章

- `character_ooc.relationship_shift_candidate`
- `plot_logic_consistency.transition_support_gap`

### 第 3 / 6 / 7 / 8 / 9 章

- `character_ooc.character_resolution_support_gap`
- `plot_logic_consistency.resolution_support_gap`

这些风险全部为：

- `severity = low`
- advisory-only
- 需要人工复核，不是自动确认崩坏

---

## 5. 内容结论

基于 fresh 真库结果，前 10 章可以给出如下结论：

### 人物 OOC

**未发现明确成立的人物 OOC。**

### 规则 / 世界观冲突

**未发现明确规则冲突。**

### 剧情逻辑

存在少量 `transition_support_gap / resolution_support_gap` 类型的低风险提示，但它们更像：

- 当前证据绑定不够强
- 推进描述与支撑证据之间有轻微缺口

而不是：

- 剧情已崩坏
- 时间线已错乱
- 设定已冲突

### 总体连续性

**前 10 章整体稳定。**

---

## 6. 这轮 fresh 复跑暴露出的真实系统问题

### A. 已修复的生产阻塞

1. Alembic 多 head / 分叉问题
2. `risk_semantic_signals / risk_signal_links / risk_signal_clusters` 缺失

修复后，fresh 真库风险审查主链已能完整跑通。

### B. 仍存在但非阻断的问题

small-model pipeline 存在 schema 漂移：

1. `continuity_notes` 返回 dict，但 schema 期望 string
2. 第 10 章 `ChapterIntakeOutput` 缺 `chapter_index`，给了 `chapter_id`

当前影响：

- small-model 路径会报 validation error
- 但 `monolithic_fallback` 会兜底
- 不阻断章节完成与 risk card 生成

因此当前结论是：

> 这是 **非阻断稳定性债**，不是主链不可用问题。

---

## 7. 一句话结论

> 样例小说前 10 章已经在 fresh PostgreSQL 真库中完整跑通；内容层面未见明确 OOC / 规则冲突 / 崩坏，仅存在少量 low 级人工复核候选，系统层面剩余问题主要是 small-model schema 收口，而不是主链不可生产。
