# Whole-Book 真书完本进度日志 — 2026-05-14

> 持续推进 LLM-driven 整本仿写，记录每个长批次的产出 + 观察。

## 批次 1：卫图分支 ch 2-6（5 章 spike）

- 命令：`writer-imitate-range ... --use-llm --max-rounds 2`
- 输出：`output/whole-book-weitu-5ch/writer-imitate-range-2-6.{json,md}`
- 总字数：6893 (avg ~1379/章)
- verdict：5/5 needs_revision
- 时间：~10 min

## 批次 2：卫图分支 ch 2-2（1 章 max_rounds=4 spike）

- 命令：`writer-imitate-range ... --max-rounds 4`
- 输出：`output/whole-book-weitu-rounds4/`
- 字数：2111 (vs max_rounds=2 的 1007，**翻倍**)
- verdict：needs_revision（gate 阈值偏高，但 blocking_issue_count=0）
- 结论：max_rounds 提升内容深度，但当前 gate 设计不会到 quality-pass

## 批次 3：卫图分支 ch 2-11（10 章稳定性测试）

- 命令：`writer-imitate-range ... --use-llm --max-rounds 2`（10 章并行）
- 输出：`output/whole-book-weitu-10ch/writer-imitate-range-2-11.{json,md}`
- 总字数：16813（avg ~1681/章）
- verdict：10/10 needs_revision
- 时间：~30 min（约 3 min/章）
- 章节分布：
  | ch | title | chars |
  |---|---|---|
  | 2 | 二姑卫荭 | 2809 |
  | 3 | 功法入门 | 1780 |
  | 4 | 珍惜眼下 | 1008 |
  | 5 | 婚事敲定 | 1195 |
  | 6 | 长鸣乡夜 | 1416 |
  | 7 | 不入祠堂 | 1637 |
  | 8 | 私塾考量 | 1139 |
  | 9 | 逼上绝境 | 1277 |
  | 10 | 抬起头来 | 2415 |
  | 11 | 脱去奴籍 | 2137 |

## 已识别的 issue

1. **mapping_pack 未生效**：`writer-imitate-range` CLI 不接 `--world-map` / `--character-map`，只接 steering pack 参数。原始 character_map 的"卫图=陈默"映射没传到 LLM prompt。
2. **章节 title 复用原作**：所有 title 沿用原作"求收藏，求追读"等元数据 — LLM 在仿写中保留了原章的作者营销标签。
3. **verdict 始终 needs_revision**：max_rounds=4 也未触发 quality-pass。Loom gate 阈值与当前 LLM 生成质量不匹配。

## 下一步计划

- 批次 4：ch 12-30（19 章）继续验证长程稳定性
- 批次 5：诛仙分支 5 章 spike，验证跨小说的 prompt 鲁棒性
- 后续：修 mapping_pack 注入 + 调 gate 阈值
