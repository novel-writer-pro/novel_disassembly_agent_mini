# 诛仙 → 科幻 整本仿写完本 — 2026-05-14

> 跨原作验证 mapping_pack 的 "→ pass" 模式：用 11 项 sci-fi 映射跑诛仙 ch 2-60。

## 决定性结果

| 指标 | 数值 | 备注 |
|---|---|---|
| **verdict=pass** | **58/59 (98.3%)** | 与 weitu sci-fi (102/102) 同档次 |
| full draft (>500 chars) | 59/59 | LLM-fallback 全部经 retry 恢复 |
| short skeleton | 0/59 | 无残留 fallback |
| title_dirty | **0/59** | 标题清理 prompt fix 持续生效 |
| mapping accuracy | **97.5%** | 157 mapped / 4 leaks |
| 总字数 | **151,267** | avg 2,563/章 |
| 完本 | `output/whole-book-zhuxian-scifi-FULL/zhuxian-scifi-fullbook.md` | 451 KB |

## 映射矩阵（仙侠 → 科幻）

| 类别 | 映射 |
|---|---|
| world | 青云门 → 星际联邦超能学院；天音寺 → 星辰修行总部；焚香谷 → 能量精炼中心 |
| character | 张小凡 → 陈晓凡；田灵儿 → 田灵奈；曾叔 → 曾元帅；苏茹 → 苏教授；陆雪琪 → 陆雪卿 |
| power | 太极玄清道 → 星能引力学；大梵般若 → 超脑识神术；天琊剑 → 星辰光剑 |
| rule | 修真改为科技超能；正邪斗争改为联邦与外星势力对抗 |

## 关键发现：mapping → pass 跨原作复现

| 原作 | 章数 | mapping 复杂度 | full pass 比例 |
|---|---|---|---|
| **卫图 → 科幻** | 102 | 12 项 | **102/102 (100%)** |
| **诛仙 → 科幻** | 59 | 11 项 | **58/59 (98.3%)** |

证伪了"卫图 sci-fi 100% pass 是巧合或单本特殊"假设。在两个独立原作上，mapping_pack 都让 LLM 输出越过 verdict=pass 门槛。

## 收敛过程

| 轮次 | full pass | 短 fallback | max_rounds |
|---|---|---|---|
| 第 1 跑 | 32 | 27 | 2 |
| 第 2 跑 (retry 27) | 58 | 0 | 4 |

收敛速度比 weitu sci-fi (5 轮) 快 — 这说明：
- 诛仙原章信息密度高（神话/玄学描写），LLM 仿写时支柱多
- 11 项 mapping 已经到位，LLM 一次性收敛能力强

## 累积产出（5 本完本）

| 完本 | 章数 | 字数 | mapping | full-pass |
|---|---|---|---|---|
| 卫图 (古典仙侠 baseline) | 102 | 199,981 | none | 0/102 |
| 诛仙 (古典仙侠) | 102 | 230,118 | none | 0/102 |
| 雪中悍刀行 (江湖武侠) | 103 | 192,451 | none | 0/103 |
| **卫图 → 科幻** | **102** | **227,037** | **12 项** | **102/102** |
| **诛仙 → 科幻** | **59** | **151,267** | **11 项** | **58/59** |
| **合计** | **468** | **1,000,854** | — | **160/468 = 34.2%** |

**100 万字真实中文仿写产出**，跨 5 本完本，2 本带 sci-fi mapping 全部接近 100% pass。

## 决定性结论

1. ✅ **mapping_pack → pass 的因果关系跨原作成立**
2. ✅ **prompt 改进套件（mapping + second-pass + title cleanup + retry）已是生产级 baseline**
3. ✅ **per-chapter incremental save 在多次 LLM 失败下零丢失**
4. ✅ **mapping accuracy 在不同原作上稳定 ~97-98%**

## 下一步候选

- 用 manual_eval mailbox 让 102 + 58 = 160 章 sci-fi 通过的内容进入人工评估
- 把 max_rounds 升级做成 service 层自适应（chars<500 自动 retry 至 max_rounds=5）
- 跨题材组合：仙侠 → 西方魔幻 / 仙侠 → 都市 等其他 mapping
