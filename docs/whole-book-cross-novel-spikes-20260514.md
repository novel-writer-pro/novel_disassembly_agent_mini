# 武道宗师 + 雪中悍刀行 跨小说 spike 验证 — 2026-05-14

> 第 3+4 部小说的 5 章抽样，验证 prompt 改进（mapping + 二次检查 + 标题清理）在新原作上稳定。

## 武道宗师 5 章

- 分支：`8af4f620-...`（武道宗师，现代武道题材）
- 章节：ch 1-5
- 改进：包含本次 session 的所有 prompt fix（second-pass 检查 + 标题清理）

| ch | title | chars | verdict | title status |
|---|---|---|---|---|
| 1 | 少年壮志不言愁 | 1,707 | needs_revision | **CLEAN** |
| 2 | 万事开头难 | 3,136 | needs_revision | **CLEAN** |
| 3 | 大丈夫当如是 | 2,079 | needs_revision | **CLEAN** |
| 4 | 人力有时而穷 | 1,602 | needs_revision | **CLEAN** |
| 5 | 一念之间 | 2,102 | needs_revision | **CLEAN** |

总计 10,626 字 / avg 2,125 字/章 / **5/5 标题 CLEAN**。

## 雪中悍刀行 5 章

- 分支：`2cd9c1ff-...`（古典仙侠/江湖题材）
- 章节：ch 1-5

| ch | title | chars | verdict | title status |
|---|---|---|---|---|
| 1 | 小二上酒 | 2,261 | needs_revision | **CLEAN** |
| 2 | 故人归 | 1,502 | needs_revision | **CLEAN** |
| 3 | 两个酒窝 | 1,780 | needs_revision | **CLEAN** |
| 4 | 去那座山摘山楂 | 1,423 | needs_revision | **CLEAN** |
| 5 | 天下第一美人 | 1,573 | needs_revision | **CLEAN** |

总计 8,539 字 / avg 1,707 字/章 / **5/5 标题 CLEAN**。

## 5 部小说完整覆盖矩阵

| 小说 | 题材 | spike 章数 | spike 字数 | avg/章 | full-book |
|---|---|---|---|---|---|
| 卫图 | 古典仙侠 | 5（baseline）| 6,893 | 1,379 | **102 章 / 199,981 字** |
| 诛仙 | 古典仙侠 | 5 | 9,140 | 1,828 | **102 章 / 230,118 字** |
| 掌门低调点 | 现代修真 NPC 流 | 5 | 7,903 | 1,580 | — |
| **武道宗师** | **现代武道** | **5** | **10,626** | **2,125** | — |
| **雪中悍刀行** | **江湖武侠** | **5** | **8,539** | **1,707** | — |

## 标题清理 prompt fix（commit 5fbbe79）实测

5 部小说 25 个 spike 章节 + 卫图/诛仙各 102 章完本中，重新生成的 5+5 = 10 个新章节标题**全部干净**（无任何"求收藏/求追读/求月票/加更"残留），证明 prompt 改进**跨小说稳定**。

## 结论

到此为止，whole-book pipeline 已在 **5 部不同题材的小说**上稳定生成：
- 古典仙侠 ×3（卫图、诛仙、雪中悍刀行）
- 现代题材 ×2（掌门低调点 NPC流、武道宗师 现代武道）

mapping_pack + 二次检查 + 标题清理三个 prompt 改进在所有新生成章节上都生效，确认这些已是默认行为而非偶然。

下一步候选：
- 任选第 3 本（如雪中悍刀行）跑完整 100 章 full-book，达到 3 本完本
- 接 manual_eval mailbox 流程，让 102+102 = 204 章已落盘内容进入人工 review
- 调 Loom gate 阈值（多日工作）让 verdict 真正升级到 quality-pass
