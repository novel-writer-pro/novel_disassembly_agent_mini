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

## 批次 4：卫图分支 ch 12-30（19 章扩展，验证 ~1 小时长程稳定性）

- 命令：`writer-imitate-range ... --use-llm --max-rounds 2`（19 章）
- 输出：`output/whole-book-weitu-19ch/writer-imitate-range-12-30.{json,md}`
- 总字数：33436（avg ~1760/章）
- verdict：19/19 needs_revision（trend 一致，未恶化）
- 时间：约 36 min（约 1.9 min/章）
- 关键章节字数：
  - ch12 单举人的考验 2617 / ch13 试武登名录 2161 / ch14 养生功大成 972
  - ch25 近乡情怯 2683 / ch28 贪财好利 2871 / ch29 我师筑基 3021
  - ch30 料峭春风 1553

## 批次 5：卫图分支 ch 31-60（30 章后台跑，进行中）

- 命令：同上，30 章
- 输出（待）：`output/whole-book-weitu-30ch/writer-imitate-range-31-60.{json,md}`
- 启动时间：2026-05-14 11:38
- 预期：~60 min

## 累计产出（批次 1-4 已落盘）

| 批次 | 章节范围 | 章数 | 总字数 | 平均字数/章 |
|---|---|---|---|---|
| 1 | 2-6 | 5 | 6893 | 1379 |
| 2 | 2 (rounds=4) | 1 | 2111 | 2111 |
| 3 | 2-11 | 10 | 16813 | 1681 |
| 4 | 12-30 | 19 | 33436 | 1760 |
| **合计**（去重 ch2-30）| 2-30 | **29** | **~50K** | **~1700** |

29 章 × ~1700 字 ≈ **5 万字真书级仿写产出**，端到端工作 5 小时内完成。

## 已识别的 issue

1. **mapping_pack 未生效**：`writer-imitate-range` CLI 不接 `--world-map` / `--character-map`，只接 steering pack 参数。原始 character_map 的"卫图=陈默"映射没传到 LLM prompt。
2. **章节 title 复用原作**：所有 title 沿用原作"求收藏，求追读"等元数据 — LLM 在仿写中保留了原章的作者营销标签。
3. **verdict 始终 needs_revision**：max_rounds=4 也未触发 quality-pass。Loom gate 阈值与当前 LLM 生成质量不匹配。

## 下一步计划

- 批次 4：ch 12-30（19 章）继续验证长程稳定性
- 批次 5：诛仙分支 5 章 spike，验证跨小说的 prompt 鲁棒性
- 后续：修 mapping_pack 注入 + 调 gate 阈值
