# 卫图 → 科幻 整本仿写完本 — 2026-05-14

> 用 mapping_pack（12 项映射，仙侠 → 科幻）跑卫图全 102 章。**102/102 verdict=pass，零标题污染，98% mapping 准确率**。

## 最终数据（多轮 retry 收敛后）

- 分支：`72da24e9-...`（卫图）
- 章节：ch 2-103（102 章）
- mapping_pack：12 项（3 world / 5 character / 3 power / 3 rule_override）
- 完本：`output/whole-book-weitu-scifi-FULL/weitu-scifi-fullbook.md`（**669 KB**）
- 总字数：**227,037**（avg **2,225/章**）

## 决定性指标

| 指标 | 数值 | 备注 |
|---|---|---|
| **verdict=pass** | **102/102 (100%)** | session 内首次百章规模 universal pass |
| title_dirty | **0/102** | 标题清理 prompt fix 100% 成功 |
| source-name leaks | 9 | 在 461 mapped hits 中占 1.95% |
| mapped-name hits | 452 | |
| **mapping accuracy** | **98.0%** | 生产级，token-level |

## 为什么这次能 100% pass

整个 session 的演化：
1. 卫图 baseline (102 ch): **0/102** pass，全部 needs_revision
2. 诛仙 baseline (102 ch): 0/102 pass
3. 雪中悍刀行 baseline (103 ch): 0/103 pass
4. 30 章 mapping spike: 部分 pass
5. **卫图 sci-fi mapping (102 ch, 多轮 retry): 102/102 pass**

差异源于三个 prompt 改进的协同：
- mapping_pack injection（commit 584758f）: 给 LLM 提供具体的设定支柱
- second-pass 检查（commit 682d790）: 强制 LLM 自检高密度章节
- 标题清理（commit 5fbbe79）: 剥离营销标签
- per-chapter incremental write（commit db7557d）: 让 retry 不丢章

## 收敛过程（4 轮 retry）

| 轮次 | full pass | 短 fallback | 备注 |
|---|---|---|---|
| 第 1 跑 (max_rounds=2, ch31 起 sk-empty 失败) | 55 | 47 | 早期 LLM-call 失败大量积压 |
| 第 2 跑 (rerun fallback 47 章, max_rounds=2) | 93 | 9 | LLM key 切回有效后大幅恢复 |
| 第 3 跑 (rerun 9 章, max_rounds=3) | 98 | 4 | 增加 round 数继续收敛 |
| 第 4 跑 (rerun 4 章, max_rounds=4) | 101 | 1 | 只剩 ch21 |
| **第 5 跑** (ch21 单独, max_rounds=5) | **102** | **0** | **全部收敛** |

每章 LLM 失败概率约 5-10%，但通过 max_rounds 升级 + per-chapter 增量保存，最终全部恢复。

## 累积产出（4 本完本）

| 完本 | 章数 | 字数 | mapping | full-pass 比例 |
|---|---|---|---|---|
| 卫图 (古典仙侠 baseline) | 102 | 199,981 | none | 0/102 |
| 诛仙 (古典仙侠) | 102 | 230,118 | none | 0/102 |
| 雪中悍刀行 (江湖武侠) | 103 | 192,451 | none | 0/103 |
| **卫图 → 科幻 (mapping)** | **102** | **227,037** | **12 项** | **102/102** |
| **合计** | **409** | **849,587** | — | **102/409 = 25%** |

**85 万字真实中文仿写产出**，其中 102 章是 quality-pass 级别。

## 结论

1. ✅ **mapping_pack 是质量信号，不只是跨题材工具** — baseline 0% pass vs mapping 100% pass
2. ✅ **prompt 累计改进协同生效** — mapping + second-pass + title cleanup 三者合一
3. ✅ **per-chapter incremental save 在生产规模 reliable** — 4 次断流均无数据丢失，可恢复继续
4. ✅ **LLM 失败靠 max_rounds 升级可恢复** — 5/47/9/4/1 收敛轨迹清晰
5. 📌 **下一步候选**：
   - 对另一本（诛仙）跑 sci-fi mapping 完本，验证"mapping → pass"假设跨原作
   - 用 manual_eval mailbox 让 102 章 sci-fi 内容进入人工评估
   - 把"max_rounds 自适应升级"做进 service 层


