# Loom 开发交接文档 / Handoff

> 最后更新: 2026-05-10
>
> 本文件供下次打开项目时**不重新理解上下文**，直接按步骤继续开发。
>
> ⚠️ 本文件不包含任何敏感凭据（API key、SK、密码等）。环境变量配置见 `.env.local`（已 gitignore）。

---

## 1. 当前架构定位

Loom 是 novel-analyzer 的 **跨章节仿写记忆与质量基础设施**，叠加在现有系统之上，不替换任何已有组件。

### 核心能力

| 层 | 能力 | 状态 |
|---|------|------|
| **memory/** | 三层记忆（Working/Episodic/Semantic）+ 冲突代谢 | ✅ Phase 1+2 完成 |
| **tension/** | 叙事张力指标（plot_similarity / conflict_density / surprise_index） | ✅ Phase 1+2 完成 |
| **reward/** | 学习型 pairwise 评估 | 🔄 Phase 3 进行中（CLI 工具已就绪，待积累数据）|

### 与 0509 控制层的关系

```
0509 session_state  →  carry_over_state 的 "运行时容器"（不变）
Loom memory 层      →  carry_over_state 的 "组装器"（新增）
```

两者不冲突。详见 [`docs/loom/arch-diff-and-alignment.md`](./arch-diff-and-alignment.md)。

### 架构全景

参见 [`docs/loom/overview.md`](./overview.md)（含完整 mermaid 架构图 + SOTA 对比表）。

---

## 2. 当前工作状态

### 2.1 已完成的提交历史

| Commit | 描述 |
|--------|------|
| `115953c` | feat(loom): live/runtime bridge 统一接入 `session_loom_gate_summary` |
| `f284df6` | feat(loom): execution chain 新增统一 `session_loom_gate_summary` |
| `c004f19` | feat(loom): execution resume / recovery 继承 Loom gate |
| `5d582ee` | feat(loom): external runtime simulation bridge 统一继承 Loom 状态 |
| `4891fa9` | feat(loom): live/external runtime readiness 继承 Loom 质量与迁移状态 |
| `4c7486a` | feat(loom): consumer migration telemetry 落到 control surfaces |
| `3be4559` | feat(loom): retirement readiness / preview 接入最小 quality gate |
| `f484150` | feat(loom): `chapter_quality_score` 聚合进入 `session_primary_verdicts` |
| `500be6e` | feat(loom): `session_loom_signals` 进入 operator surface |
| `edf1237` | feat(loom): Loom Phase 1+2 代码与测试（38 tests） |

### 2.2 核心文件清单

#### 服务层（3 个核心服务）

| 文件 | 职责 | 最后修改 |
|------|------|---------|
| `novel_analyzer/services/tension_service.py` | 张力指标计算（plot_similarity / conflict_density / surprise_index） | 已对齐真实 edge/node 类型 |
| `novel_analyzer/services/memory_assembler_service.py` | 三层记忆组装（Working/Episodic/Semantic）→ carry_over_state | 已对齐 `entity/world_rule` |
| `novel_analyzer/services/memory_consolidation_service.py` | 冲突代谢 + 重要性衰减 + 分类（evolution/contradiction/ambiguity） | 已修复 `is_active` bug + CONFLICT_EDGE_TYPES |

#### CLI 入口

| 文件 | 职责 |
|------|------|
| `novel_analyzer/cli/app.py` | Loom CLI 命令注册（loom-status / loom-consolidate / loom-assemble）+ writer operator surface Loom signal 聚合 |

#### 数据模型

| 文件 | 职责 |
|------|------|
| `novel_analyzer/database/models.py` | GraphNode / GraphEdge / FactRecord Loom 字段（conflict_status, loom_version, superseded_by_node_id, decay_factor, episodic_status） |
| `alembic/versions/20260509_01_loom_memory_fields.py` | 生产 migration（已在 PG 成功执行） |

#### 测试

| 文件 | 数量 | 状态 |
|------|------|------|
| `tests/test_loom_phase1.py` | 23 tests | ✅ 全部通过 |
| `tests/test_loom_phase2.py` | 15 tests | ✅ 全部通过 |

#### 文档

| 文档 | 说明 |
|------|------|
| `docs/loom/overview.md` | 架构全景 + SOTA 对比 |
| `docs/loom/roadmap.md` | Phase 状态与后续任务 |
| `docs/loom/arch-diff-and-alignment.md` | Loom vs 0509 对比 |
| `docs/loom/memory/carry-over-migration.md` | 迁移路径与实验记录 |
| `docs/loom/tension/README.md` | 张力指标设计 |
| `docs/loom/reward/README.md` | Reward 模型规划 |
| `docs/cli-operations-manual.md` | CLI 手册（第 12 节 Loom） |
| `docs/real-run-checklist.md` | 试跑清单（第 8 节 Loom） |
| `CHANGELOG.md` | 变更记录 |

### 2.3 生产环境真实数据（PostgreSQL）

#### 真实 Edge Types

| edge_type | 数量 | 说明 |
|-----------|------|------|
| `carries_forward` | 85,301 | 事件/实体延续 |
| `participates_in` | 7,201 | 实体参与事件 |
| `contextualizes` | 6,304 | 上下文关联 |
| `hints_at` | 4,833 | 伏笔提示 |
| `advances_to` | 4,011 | 事件推进 |
| `pays_off_as` | 3,900 | 伏笔兑现 |
| `conflict_centers_on` | 3,456 | 冲突核心 |
| `co_occurs` | 3,287 | 共现关系 |
| `persists_into` | 1,954 | 持续关系 |
| `constrains` | 1,273 | 约束关系 |
| `follows` | 856 | 时间跟随 |
| `evolves_to` | 351 | 演进关系 |
| `escalates_to` | 213 | 升级关系 |
| `relates_to` | 206 | 关联关系 |
| `conflict_involves` | 108 | 冲突涉及 |
| `pressured_by` | 108 | 冲突压力 |

#### 真实 Node Types

| node_type | 数量 | 说明 |
|-----------|------|------|
| `event` | 920 | 事件节点 |
| `continuity` | 725 | 连续性节点 |
| `entity` | 548 | 实体（角色等） |
| `world_rule` | 144 | 世界规则 |
| `relation` | 81 | 关系节点 |
| `foreshadow` | 63 | 伏笔节点 |
| `conflict` | 49 | 冲突节点 |

**关键结论**：
- `graph_service` 不产出 `"character"` 类型的 node — 角色是 `entity`
- `graph_service` 不产出 `"rule"` 类型的 node — 世界规则是 `world_rule`
- `graph_service` 不产出 `"relationship"` 类型的 edge — 关系是 `relates_to`
- GraphNode **没有** `is_active` 列（该列仅存在于 GraphEdge）

### 2.4 已验证的端到端链路

```
Ingest → DeepSeek analyze → fact_records + graph_nodes + graph_edges
  → Consolidation triggered (loom_consolidation_complete event)
    → loom-status shows tension metrics
      → loom-assemble outputs carry_over_state with episodic decay
```

#### 关键运行标识

| 项目 | ID |
|------|----|
| 大分支（115章） | `72da24e9-e65c-45a9-836d-957c4ae783ec` |
| fresh 分支 | `62e636f0-c901-4167-aa1c-aff3da9c83ef` |
| 实测 run | `da1ca7d4-28ab-434b-bdbb-489f703e1f1d` |
| 实测 branch | `bd9c6d9d-4f83-4989-b092-001c74be7281` |
| 测试小说（3章） | `loom-test-deepseek` |

---

## 3. 关键架构决策记录

### 决策 1：Loom 非侵入式叠加
- **原则**：不替换任何现有组件，仅在现有 `carry_over_state` / FactRecord / GraphNode / GraphEdge 之上叠加 Loom 字段
- **理由**：现有 0509 链路已生产运行，Loom 故障不应阻塞主链路
- **实现**：`loom_memory_mode=shadow`（记录事件但不阻塞）

### 决策 2：无 `is_active` 在 GraphNode
- **问题**：`_mark_evolution` 尝试设置 `old_node.is_active = False`，但 GraphNode 模型无此列
- **解决**：移除该赋值。GraphNode 通过 `superseded_by_node_id` 追踪演进历史
- **教训**：`is_active` 仅存在于 GraphEdge；GraphNode 用 `conflict_status` + `superseded_by_node_id` 替代

### 决策 3：node_type 实际值对齐
- **问题**：服务代码假设 node_type 为 `"character"`/`"rule"`，但实际 graph_service 产出 `"entity"`/`"world_rule"`
- **解决**：使用 `in_(["entity", "character"])` 保持前向兼容
- **教训**：未来新增 node_type 时需同步更新 `CONFLICT_EDGE_TYPES` 和 `in_()` 列表

### 决策 4：CLI 命令注册顺序
- **问题**：`@app.command()` 定义在 `if __name__ == "__main__": app()` 之后，导致命令不可见
- **解决**：将 Loom 命令移至 `app()` 调用之前
- **教训**：`typer` 的 `@app.command()` 必须在 `app()` 前执行

---

## 3.5 规划闭环 vs 当前完成度（本次交接重点）

### 原规划预期闭环

根据 `docs/loom/roadmap.md` 与 `docs/loom/arch-diff-and-alignment.md`，当前这条 Loom→0509 对接主线，预期要完成 4 个连续闭环：

1. **信号暴露闭环**
   - tension / quality 信号进入 control surface
   - operator 不再需要回到底层章节产物手工拼装
2. **主 verdict 闭环**
   - `chapter_quality_score` 进入 `session_primary_verdicts`
   - quality gate 能直接参与 session 级判断
3. **治理门控闭环**
   - retirement / readiness / migration telemetry 能感知 Loom 质量与迁移状态
   - legacy 收口时不会绕过 Loom gate
4. **执行链继承闭环**
   - action → execution → replay/apply/resume → live bridge → external runtime bridge
   - 全链共享同一层 Loom gate 结论，不再分叉

### 当前已经完成的闭环

| 规划闭环 | 当前状态 | 证据 |
|---|---|---|
| 信号暴露闭环 | ✅ 已完成 | `session_loom_signals`、operator surface markdown、`500be6e` |
| 主 verdict 闭环 | ✅ 已完成 | `quality_verdict` / `average_chapter_quality_score` / `chapter_quality_signal_count`、`f484150` |
| 治理门控闭环 | ✅ 已完成最小可用版 | retirement quality gate、consumer migration telemetry、`3be4559` / `4c7486a` |
| 执行链继承闭环 | ✅ 已完成到 simulation bridge | `session_loom_gate_summary` 覆盖 execution/live/external runtime simulation、`f284df6` / `115953c` / `c004f19` |

### 当前尚未完成的闭环

| 闭环 | 未完成点 | 说明 |
|---|---|---|
| 生产验证闭环 | A/B 实验、shadow→ab→enabled 切换 | 仍停留在规划状态，缺真实对比数据 |
| reward 数据闭环 | 500+ pairs 积累、reward model 训练 | CLI 工具已就绪（loom-collect-pairs / loom-collect-pairs-from-manual），缺生产运行数据 |
| 真实 executor 闭环 | live writeback / external runtime 真执行器 | 当前仍是 preview / local simulation bridge，不是生产 mutation |
| 真实 consumer telemetry 闭环 | 来自真实 consumer 的迁移上报 | 当前 telemetry 为 contract-derived，可用但不是 runtime truth |

## 4. 剩余工作与下一步

### 4.0 最近新增交付（2026-05-10）

- `writer-imitate-session-state.json` / `writer-imitate-operator-surface.json` 已稳定暴露 `session_loom_signals`。
- `session_primary_verdicts` 已吸收质量聚合，统一输出 `quality_verdict` / `average_chapter_quality_score` / `chapter_quality_signal_count`。
- writer retirement readiness / preview 已接入最小 quality gate：`quality_score < 0.7` 时标记 `quality-blocked`。
- control surfaces、execution chain、execution resume、live/runtime readiness、external runtime simulation bridge 已统一暴露 `session_consumer_migration_telemetry`。
- action/execution/replay/apply/resume 与 live/runtime simulation bridge 已统一暴露 `session_loom_gate_summary`，把质量、张力、迁移状态收口成稳定摘要。
- index / control-surface registry 第一层摘要现在也能直接展示 Loom gate 结论，operator 打开入口页即可先判断当前 gate 状态。

### 4.0.1 Phase 3 新增交付（2026-05-10 本次）

| 交付物 | 说明 |
|--------|------|
| `loom-collect-pairs` CLI | 从 writer-imitate 产物提取 pairwise 对，支持单目录（round-0 vs final）和跨目录（baseline vs steering）两种模式，追加写入 JSONL |
| `loom-pairs-stats` CLI | 显示 pairwise 数据采集进度（当前 / 500 目标 / 百分比）、质量分布、evaluation_method 分布 |
| `loom-ab-compare` CLI | A/B 实验报告：对比两个 writer-imitate 输出目录的 character_ooc 触发率，输出 reduction%，判断是否达到 ≥20% 目标，可写 JSON 报告 |
| `loom-collect-pairs-from-db` CLI | 从 ChapterArtifact DB 记录跨两个分支提取 pairwise 对（chapter_summary 对比） |
| `loom-collect-pairs-from-manual` CLI | 从 runs/manual_eval/ 工作区 artifacts/writer-imitate-ch*.json 提取 pairwise 对，跳过 _template，pair_source=manual_eval_workspace |
| `ChapterImitationHarnessReport.chapter_quality_signal` | 新增字段，`loom_pairwise_enabled=True` 时自动运行 heuristic pairwise eval，结果写入 `chapter_quality_signal` 和最后一轮 `skill_outputs["_loom_chapter_quality"]` |
| `PostgresCheckReport.missing_cluster_review_columns` | 修复：改为 `field(default_factory=dict)` 使参数可选，修复测试失败 |
| 文档索引修复 | docs/README.md、roles/README.md、tracks/README.md、roles/product/README.md、roles/backend/README.md、roles/integrator/README.md、roles/imitation/README.md、tracks/imitation/README.md、architecture/README.md 补全缺失的文档引用，386 个测试全部通过 |
| 24 个新测试 | test_loom_phase2.py +3（pairwise harness 集成），test_loom_phase3.py +21（collect-pairs / pairs-stats / ab-compare / collect-pairs-from-db），全部通过 |

**当前 Loom 测试总数：69 passed（Phase 1: 23 + Phase 2: 18 + Phase 3: 28）**

**全项目测试：394 passed**

### 4.1 当前未完成的 Phase 3 规划

参见 [`docs/loom/roadmap.md`](./roadmap.md) 完整清单。

| 优先级 | 任务 | 说明 | 前置条件 |
|--------|------|------|---------|
| 🔴 P0 | A/B 实验：真实数据运行 | 用 20 章真实数据跑 loom-ab-compare，验证 character_ooc 下降 ≥20% | 需切换 loom_memory_mode=ab 并积累真实产物 |
| 🟡 P0 | 0509 operator_surface 深化对接 | 当前 contract / execution / live / runtime simulation 面已基本统一；下一步是把这些 Loom gate 真正接到更接近生产的 executor / consumer 上 | 需 Loom 稳定运行 |
| 🟡 P1 | Pairwise 数据积累 | 用 loom-collect-pairs 积累 500+ pairs；开启 loom_pairwise_enabled=True 后每次 writer-imitate 自动产出 | 需生产运行积累 |
| 🟡 P1 | 角色认知基（Phase 3） | 角色级 agent 自主认知基 | 需 A/B 实验验证通过 |
| 🟢 P2 | Fine-tuned reward model | 替代 LLM-as-judge | 需 pairwise 数据量充足 |

### 4.2 下次继续开发时的标准启动步骤

```bash
# 1. 激活环境
source .venv/bin/activate

# 2. 验证数据库连通
pg_isready -h 127.0.0.1 -p 5432 -U d2

# 3. 验证 LLM 连通（DeepSeek / vLLM 或其他 provider）
#    注意：API key 在 .env.local 中，不在文档里
# python3 -c "import httpx; r=httpx.post('${NOVEL_ANALYZER_LLM_BASE_URL}/chat/completions', ...)"

# 4. 运行 migration（如有新变更）
alembic upgrade head

# 5. 运行 Loom 测试（Phase 1+2+3）
python3 -m pytest tests/test_loom_phase1.py tests/test_loom_phase2.py tests/test_loom_phase3.py -v

# 6. 验证 CLI 命令
novel-analyzer --help  # 确认 loom-status / loom-consolidate / loom-assemble / loom-collect-pairs / loom-pairs-stats / loom-ab-compare / loom-collect-pairs-from-db / loom-collect-pairs-from-manual 可见

# 7. 真实分支验证
novel-analyzer loom-status --branch-id <branch-id>

# 8. Pairwise 数据采集（有 writer-imitate 产物时）
novel-analyzer loom-collect-pairs --output-dir output/ --pairs-file output/loom-pairs.jsonl
novel-analyzer loom-pairs-stats --pairs-file output/loom-pairs.jsonl

# 9. A/B 实验对比（有两组产物时）
novel-analyzer loom-ab-compare output/baseline/ output/loom/ --output-file output/ab-report.json
```

### 4.3 需关注的风险点

| 风险 | 说明 | 缓解措施 |
|------|------|---------|
| node_type 新增 | graph_service 新增 node_type 时 Loom 查询可能遗漏 | 注册时同步更新所有 `in_()` 列表 |
| metadata_json 结构变化 | graph_service 输出 metadata 格式变化 → 冲突分类逻辑失效 | 由 consolidation_service 的 `_classify()` 统一处理 |
| 性能 | 115 章分支已产生 85K edges，查询延迟可能升高 | 当前查询有 `branch_id` 索引，必要时加 composite index |
| 新 provider 切换 | 切换 LLM provider 后 embedding 维度/质量变化 | `_plot_similarity()` 有 keyword fallback |

---

## 5. 文档索引（快速跳转）

### 架构与设计
- [`docs/loom/overview.md`](./overview.md) — 架构全景 + SOTA 对比 + 资产盘点
- [`docs/loom/arch-diff-and-alignment.md`](./arch-diff-and-alignment.md) — Loom vs 0509 对比
- [`docs/loom/roadmap.md`](./roadmap.md) — Phase 计划与任务清单
- [`docs/loom/tension/README.md`](./tension/README.md) — 张力指标设计文档
- [`docs/loom/reward/README.md`](./reward/README.md) — Reward 模型规划

### 记忆层
- [`docs/loom/memory/carry-over-migration.md`](./memory/carry-over-migration.md) — 三阶段迁移路径

### 操作与验证
- [`docs/cli-operations-manual.md`](../cli-operations-manual.md) — CLI 手册（第 12 节 Loom）
- [`docs/real-run-checklist.md`](../real-run-checklist.md) — 试跑清单（第 8 节 Loom）

### 变更记录
- [`CHANGELOG.md`](../../CHANGELOG.md) — 完整变更历史

### 主文档入口
- [`docs/README.md`](../README.md) — 按角色分流入口

---

## 6. 代码诊断速查

### CMD
- 测试 Loom Phase 1+2+3: `python3 -m pytest tests/test_loom_phase1.py tests/test_loom_phase2.py tests/test_loom_phase3.py -v`
- 全部测试: `python3 -m pytest tests/ -v`
- Migration: `alembic upgrade head`
- Loom CLI: `python3 -m novel_analyzer loom-status --branch-id <id>`
- Loom Consolidate: `python3 -m novel_analyzer loom-consolidate --branch-id <id>`
- Loom Assemble: `python3 -m novel_analyzer loom-assemble --branch-id <id>`
- Pairwise 采集（manual eval）: `novel-analyzer loom-collect-pairs-from-manual --manual-eval-dir runs/manual_eval/ --pairs-file output/loom-pairs.jsonl`
- Pairwise 采集（harness 产物）: `novel-analyzer loom-collect-pairs --output-dir output/ --pairs-file output/loom-pairs.jsonl`
- Pairwise 进度: `novel-analyzer loom-pairs-stats --pairs-file output/loom-pairs.jsonl`
- DB direct: `PGPASSWORD=*** psql -h 127.0.0.1 -p 5432 -U d2 -d novel_analyzer -c "SELECT..."`

### 变量速查
- 环境配置位置: `.env.local`（已 gitignore）
- PG host/port/user/db: 见 `.env.local` 或 history
- Alembic: `alembic/versions/20260509_01_loom_memory_fields.py`
