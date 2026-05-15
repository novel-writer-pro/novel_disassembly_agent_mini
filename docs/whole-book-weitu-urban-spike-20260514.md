# 卫图 → 都市修真 10 章 spike — 2026-05-14

> 同时验证两件事：(1) 跨题材到都市/现代场景，(2) 服务层自动 retry（commit 7feb888）。

## 设置

- 分支：`72da24e9-...`（卫图）
- 章节：ch 2-11（10 章）
- mapping_pack：12 项（仙侠 → 都市修真）

## 结果

| 指标 | 数值 |
|---|---|
| chapters generated | 10 |
| 总字数 | **21,370**（avg **2,137/章**） |
| **verdict=pass** | **10/10 (100%)** |
| short skeleton | 0/10 |
| title_dirty | 0/10 |
| mapping accuracy | 96.1%（49 mapped / 2 leaks） |
| **auto-retry recovered** | **2/10 chapters**（ch4 attempt 3/3, ch6 attempt 2/3） |

## 关键验证

1. ✅ **mapping_pack 跨题材稳定**：在第三个目标题材（都市修真）上首次跑通，10/10 pass
2. ✅ **auto-retry 在生产中生效**：2 章（20%）在第一次 LLM 调用产出 thin draft，service 层自动 retry 到第 2-3 次成功，operator 不再需要手动 rerun
3. ✅ **mapping accuracy 跨题材一致**：96-98% 范围（科幻 vs 都市同档次）

## 都市修真映射矩阵

| 类别 | 映射 |
|---|---|
| world | 郑国 → 华夏现代社会；庆丰府 → 江城；青木县 → 临海区 |
| character | 卫图 → 陈墨；卫荭 → 陈瑶；杏 → 小杏；李童氏 → 李董；卫豹 → 陈山 |
| power | 养生功 → 养气调息术；龟息养气功 → 吐纳静坐法；大器晚成 → 资质觉醒型 |
| rule | 封建奴籍替换为雇佣合同；武举改为体校特长生选拔；修真门派改为隐世武学传承社团 |

## 累积产出（5 本完本 + 2 个 spike）

| 完本/spike | 章数 | 字数 | mapping | full pass |
|---|---|---|---|---|
| 卫图 baseline | 102 | 199,981 | none | 0/102 |
| 诛仙 baseline | 102 | 230,118 | none | 0/102 |
| 雪中悍刀行 baseline | 103 | 192,451 | none | 0/103 |
| 卫图 → 科幻 | 102 | 227,037 | 12 | 102/102 |
| 诛仙 → 科幻 | 59 | 151,267 | 11 | 58/59 |
| **卫图 → 都市修真 (本 spike)** | **10** | **21,370** | **12** | **10/10** |
| **总计** | **478** | **1,022,224** | — | **170/478 = 35.6%** |

## 结论

mapping_pack 的"→ pass"模式在 3 种不同题材（仙侠 / 科幻 / 都市）上都成立。auto-retry feature shipping 后，原本需要手动 rerun 的 10-20% 章节现在自动恢复，operator 工作流大幅简化。
