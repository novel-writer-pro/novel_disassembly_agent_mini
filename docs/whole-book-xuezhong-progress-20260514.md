# 雪中悍刀行整本仿写进度 — 2026-05-14

> 第三部完整生成的小说，单批次 103 章一次跑完。

## 单批次：ch 1-103（103 章江湖武侠主线）

- 完成时间：2026-05-14 18:56（耗时约 80 min，约 0.8 min/章）
- 输出：`output/whole-book-xuezhong-103ch/writer-imitate-range-1-103.{json,md}`
- 总字数：**192,451**（avg **1,868/章**）
- verdict：103/103 needs_revision（与前两本一致）
- **标题清理：0/103 dirty**（title cleanup prompt fix 在 100+ 章规模上零失败）
- 已 split 为 per-chapter writer-imitate-ch{1..103}.json

## 三本完本对比（截至 2026-05-14）

| 小说 | 题材 | 章数 | 字数 | avg/章 | 时间 | 平均速度 |
|---|---|---|---|---|---|---|
| 卫图 | 古典仙侠 | 102 | 199,981 | 1,960 | ~3.5h | 2.0 min/章 |
| 诛仙 | 古典仙侠 | 102 | 230,118 | 2,256 | ~80 min | 0.8 min/章 |
| **雪中悍刀行** | **江湖武侠** | **103** | **192,451** | **1,868** | **~80 min** | **0.8 min/章** |
| **合计** | — | **307** | **622,550** | **2,028** | — | — |

## 三本完本的产出物

聚合：`output/whole-book-xuezhong-FULL/`
- `xuezhong-imitation-fullbook.md` — 103 章串联（436 KB）
- `chapter-index.md` — 章节索引

合并三本完本：
- 卫图 fullbook (458 KB)
- 诛仙 fullbook (547 KB)
- 雪中悍刀行 fullbook (436 KB)
- 总计 ~1.4 MB 的中文仿写整本产物

## 关键观察

1. **标题清理（commit 5fbbe79）证伪了"偶然成功"假设**：在 103 章规模上零失败。这是 prompt-level fix 的价值证明。
2. **诛仙/雪中悍刀行 平均速度 (~0.8 min/章) 显著快于卫图 (~2 min/章)**：可能源于 LLM proxy 队列负载随时段变化，或源章长度差异。
3. **三本完本的 verdict 完全一致（needs_revision / blocking_issue_count=0）**：再次确认 Loom gate 阈值是全局问题，不是单本特性。
4. **总产出 622K 字 / 307 章**：达到三本商业小说级量级（约相当于一部 70-100 万字网文的预备稿底）。

## 下一步候选（按 ROI 排序）

| 候选 | 价值 | 成本 |
|---|---|---|
| **A. 接 manual_eval mailbox 流程** | 让 307 章已落盘内容进入人工 review，转化为可发布质量 | 取决于 reviewer 带宽 |
| B. 跑 第 4 本 / 第 5 本 完整完本 | 进一步证明跨原作鲁棒，但价值递减 | 各 ~80 min LLM |
| C. Loom gate 阈值调优 | 让 verdict 真正升级到 quality-pass | 多日工程，需仔细审查 |
| D. 跨题材完本（如卫图 → 科幻完整 102 章） | 证明 mapping_pack 在百章规模稳定 | ~2-3h LLM + 7 项 mapping |

**强推 A**：技术 pipeline 已经稳定，瓶颈在内容审核和质量循环。
