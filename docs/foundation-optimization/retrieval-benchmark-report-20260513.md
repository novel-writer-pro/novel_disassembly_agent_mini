# 检索基准首份实测报告 — 2026-05-13

> 本报告归档 2026-05-13 三分支实测数据，给出两条关键信号，并指向下一步行动。
> 数字来源：`.sisyphus/evidence/retrieval-bench-*.json`，与 JSON 逐字段核对。

---

## 1. 测试方法

- **工具**：`retrieval-benchmark` CLI（落地于 commit `94dd73e`）
- **Ground truth**：每章 `query_hints` 自标注，正确答案为该章的 `chapter_index`
- **FTS 配置对比**：`simple`（PostgreSQL 内置）vs `jiebacfg`（pg_jieba 文档模式）vs `jiebaqry`（pg_jieba 查询模式）
- **K 值**：1、3、5、10
- **指标**：MRR（Mean Reciprocal Rank）、Recall@K、平均查询延迟
- **环境**：本机 PG，pg_jieba 已装，`jieba-user-dict.txt` 已加载（运维细节见 [pg-jieba-userdict-ops.md](./pg-jieba-userdict-ops.md)）
- **运行时间**：2026-05-13，单次完整跑分

---

## 2. 三分支实测数据

### 分支 72da24e9（103 docs，98 queries）— `key_entities` 干净

| Config | MRR | R@1 | R@3 | R@5 | R@10 | 延迟 |
|--------|-----|-----|-----|-----|------|------|
| simple | 0.188 | 0.133 | 0.184 | 0.276 | 0.327 | 3.3ms |
| **jiebacfg** | **0.560** | **0.439** | **0.592** | **0.735** | **0.827** | 4.3ms |
| jiebaqry | 0.489 | 0.378 | 0.520 | 0.643 | 0.735 | 4.8ms |
| Δ(jiebacfg − simple) | **+0.371** | +0.306 | +0.408 | +0.459 | +0.500 | +1.0ms |

### 分支 2cd9c1ff（58 docs，58 queries）— `key_entities` 含噪声

| Config | MRR | R@1 | R@3 | R@5 | R@10 | 延迟 |
|--------|-----|-----|-----|-----|------|------|
| simple | 0.017 | 0.017 | 0.017 | 0.017 | 0.017 | 4.5ms |
| **jiebacfg** | **0.060** | **0.052** | **0.069** | **0.069** | **0.069** | 4.6ms |
| jiebaqry | 0.060 | 0.052 | 0.069 | 0.069 | 0.069 | 3.1ms |
| Δ(jiebacfg − simple) | **+0.043** | +0.035 | +0.052 | +0.052 | +0.052 | +0.1ms |

### 分支 e5becabd（58 docs，58 queries）— `key_entities` 含噪声

| Config | MRR | R@1 | R@3 | R@5 | R@10 | 延迟 |
|--------|-----|-----|-----|-----|------|------|
| simple | 0.069 | 0.069 | 0.069 | 0.069 | 0.069 | 3.2ms |
| **jiebacfg** | **0.164** | **0.155** | **0.172** | **0.172** | **0.172** | 3.2ms |
| jiebaqry | 0.095 | 0.086 | 0.103 | 0.103 | 0.103 | 3.4ms |
| Δ(jiebacfg − simple) | **+0.095** | +0.086 | +0.103 | +0.103 | +0.103 | +0.1ms |

### ΔMRR 总览（jiebacfg − simple）

| 分支 | docs | simple MRR | jiebacfg MRR | ΔMRR | entity 质量 |
|------|------|-----------|-------------|------|------------|
| 72da24e9 | 103 | 0.188 | 0.560 | **+0.371** | 干净 |
| 2cd9c1ff | 58 | 0.017 | 0.060 | +0.043 | 含噪声 |
| e5becabd | 58 | 0.069 | 0.164 | +0.095 | 含噪声 |

---

## 3. 关键解读

### 信号 1：jieba 接入 BM25 是无条件的 win

三个分支的 ΔMRR 全部为正（+0.043 到 +0.371），延迟代价最高 +1.0ms。无论 entity 质量如何，`jiebacfg` 都优于 `simple`。这一结论在三个独立数据集上一致成立。

### 信号 2：绝对 MRR 上限由 `key_entities` 抽取质量决定

同样使用 `jiebacfg`，干净分支（72da24e9）MRR=0.560，噪声分支（2cd9c1ff）MRR=0.060，相差 9 倍。检索层本身无法弥补上游 entity 噪声带来的 query 质量损失。在 entity 抽取问题修复之前，换 embedding 模型或调整检索策略对噪声分支的提升空间极为有限。

### 注意点：jiebaqry 在三个分支均未超过 jiebacfg

`jiebaqry`（查询模式）切分粒度更细，在所有分支的 MRR 均低于或等于 `jiebacfg`。当前 `retrieval_service._fts_config_name()` 已优先选择 `jiebacfg`，无需调整。

---

## 4. 行动建议

### 短期（P0，已有路径）

- **pg_jieba + jiebacfg 在生产 PG 部署到位**：运维步骤见 [pg-jieba-userdict-ops.md](./pg-jieba-userdict-ops.md)
- **`retrieval-benchmark` CLI 可重复跑**，命令示例：
  ```bash
  python -m novel_analyzer.cli retrieval-benchmark --branch-id <branch_id>
  ```

### 中期（P0，新发现）

- **上游 `key_entities` 抽取质量诊断**：噪声分类、假设根因、排查动作清单见 [entity-extraction-noise-diagnosis-20260513.md](./entity-extraction-noise-diagnosis-20260513.md)
- 诊断结论出来之前，不对噪声分支重跑分析（成本高，根因未隔离）

### 不建议（当前阶段）

- **不建议换 embedding 模型**：在 entity 噪声修好之前，embedding 层的改进无法触及根本瓶颈（见信号 2）。embedding/rerank 路线图见 [embedding-rerank-dictionary-guide.md](./embedding-rerank-dictionary-guide.md)
- **不建议调整 jiebaqry 权重**：数据显示 jiebaqry 无优势，现状配置正确

---

## 5. 数据存档

原始 JSON 证据文件（不可修改）：

- `.sisyphus/evidence/retrieval-bench-72da24e9-20260513.json`（103 docs，干净分支）
- `.sisyphus/evidence/retrieval-bench-2cd9c1ff-20260513.json`（58 docs，噪声分支）
- `.sisyphus/evidence/retrieval-bench-e5becabd-20260513.json`（58 docs，噪声分支）

JSON schema 版本：`retrieval-benchmark.v2`

> **数字核对说明**：本报告所有数字直接从上述 JSON 读取，四舍五入至 3 位小数。
> 与计划文档的偏差（以 JSON 为准）：
> - 2cd9c1ff `total_docs`=58（计划标注 59）；`simple` 延迟=4.5ms（计划标注 3.0ms）
> - e5becabd `total_docs`=58（计划标注 57）
> - 72da24e9 `simple` 延迟=3.3ms（计划标注 3.2ms）
