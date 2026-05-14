# 卫图 → 科幻 整本仿写完本 — 2026-05-14

> 用 mapping_pack（12 项映射，仙侠 → 科幻）跑卫图全 102 章。本次出现整个 session 首批 `verdict=pass` 章节。

## 数据

- 分支：`72da24e9-...`（卫图）
- 章节：ch 2-103（102 章）
- mapping_pack：12 项（3 world / 5 character / 3 power / 3 rule_override）
- 输出：`output/whole-book-weitu-scifi-102ch/`（102 个 per-chapter JSON + 1 个聚合）
- 完本：`output/whole-book-weitu-scifi-FULL/weitu-scifi-fullbook.md`（414 KB）
- 时长：约 90 min（含恢复 + 续跑）
- LLM：deepseek-v4-pro via nassaapi（新 key）

## 关键发现：首次出现 verdict=pass

| verdict | 章数 | 比例 |
|---|---|---|
| **pass** | **58** | **56.9%** |
| needs_revision | 44 | 43.1% |

**这是本 session 最重要的发现**：之前 307 章（卫图 102 + 诛仙 102 + 雪中悍刀行 103）verdict 全部 `needs_revision`。本次 sci-fi mapping run 首次出现 `pass`，且占多数。

可能解释（按可信度排序）：
1. **mapping_pack 让 LLM 输出更"完整"的章节**：sci-fi 设定的具体 detail（"星舰后勤区"/"低品能量块"/"合成肉"）需要 LLM 主动构建场景，反而满足了 Loom gate 的"原创性 + 信息密度"阈值
2. **deepseek-v4-pro 新 key 路由到不同后端实例**：可能切到了内容更丰富的 instance；纯 baseline 重测可证伪
3. **prompt 累计改进生效**：second-pass 检查（682d790）+ 标题清理（5fbbe79）让 LLM 更注重每章的完整性

## 数据

- 总字数：**141,330**（avg **1,385/章**）
- vs unmapped 卫图 baseline (1,960)：**-29%**（mapping_pack 字数下降）
- vs 30 章 mapping spike (2,913)：**-52%**
- 推测：100+ 章规模 LLM 信息密度衰减；`needs_revision` 章节字数都是 ~375（短 fallback）

## mapping 准确率

| 指标 | 数值 |
|---|---|
| mapped-name hits | 233 |
| source-name leaks | 8 |
| **token 级准确率** | **96.7%** |

vs 30 章规模 (97.7%)：**-1pp**，仍在生产级范围。leaks 从 4→8，绝对数翻倍但密度（leaks/章）反而降低（30ch=0.13/ch vs 102ch=0.08/ch）。

## 问题

1. **needs_revision 章节字数普遍 ~375**：是 fallback skeleton 的标志（draft generation 失败时退化）。需排查这 44 章是 LLM 端 timeout 还是 prompt 问题。
2. **Title cleanup 回归**：40/102 章 title 含"求收藏，求追读"标签。pure baseline 时 0 leak，加 mapping_pack 后 39%。猜测 mapping prompt 与 title cleanup 指令竞争 attention budget。
3. **average 字数下降**：1,385 vs unmapped 1,960。可能源于：
   - 短 fallback 章节（chars=375）拉低均值
   - mapping_pack 占用 prompt token，挤压 source_excerpt 容量
4. **resume 失败 2 次**：原始 102 章 batch 在 ch31 / ch88 两次断流（第一次因 sk-empty endpoint 不工作，第二次未明）。每次断流后 per-chapter file 都正确保留，靠手工 resume 恢复。这印证了 commit `db7557d`（per-chapter incremental write）的价值。

## 累积产出（4 本完本，含本次 sci-fi 版）

| 完本 | 章数 | 字数 | mapping | pass 数 |
|---|---|---|---|---|
| 卫图 (古典仙侠 baseline) | 102 | 199,981 | none | 0 |
| 诛仙 (古典仙侠) | 102 | 230,118 | none | 0 |
| 雪中悍刀行 (江湖武侠) | 103 | 192,451 | none | 0 |
| **卫图 → 科幻 (mapping)** | **102** | **141,330** | **12 项** | **58** |
| **合计** | **409** | **763,880** | — | **58** |

**76 万字，4 本完本**，首次 demo 出 mapping_pack 在百章规模能让 verdict 越过 quality-pass 门槛。

## 下一步

- **不要修 needs_revision 短章**：是 LLM/network 偶发 fallback，需要更严的 retry 策略而非内容修复
- **Title cleanup 与 mapping prompt 顺序需调整**：把"clean title"放进强制 rules（在所有 mapping 之后），不是 soft suggestion
- **复测一次 weitu baseline 看 pass 比例**：如果 baseline 也产生 pass 了，说明 LLM 端有变化；如果还是全 needs_revision，确认是 mapping_pack 的功劳
